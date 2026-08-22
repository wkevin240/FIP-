from datetime import datetime, timezone
from decimal import Decimal

from app.core.enums.invoicing import InvoiceStatus
from app.domain.invoicing.invoice.rules import InvoiceRules
from app.models.invoicing.payment import Payment
from app.models.invoicing.payment_allocation import PaymentAllocation
from app.repositories.invoicing.invoice_repository import InvoiceRepository
from app.repositories.invoicing.payment_repository import PaymentRepository
from app.schemas.invoicing.payment import PaymentCreate
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class PaymentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.payments = PaymentRepository(session)
        self.invoices = InvoiceRepository(session)
        self.audit = AuditService(session)

    async def create_payment(
        self, organization_id: str, data: PaymentCreate, actor_id: str | None = None
    ) -> Payment:
        if (
            data.external_reference is not None
            and await self.payments.get_by_external_reference(
                organization_id, data.external_reference
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment external reference already exists",
            )
        try:
            invoice = None
            if data.invoice_id:
                invoice = await self.invoices.get_for_update(
                    organization_id, data.invoice_id
                )
                if invoice is None:
                    raise HTTPException(status_code=404, detail="Invoice not found")
                self._validate_invoice_payment(invoice, data)
                try:
                    status_value, paid_amount, credited_amount = (
                        InvoiceRules.apply_payment(
                            Decimal(invoice.total_amount),
                            Decimal(invoice.paid_amount),
                            Decimal(invoice.credited_amount),
                            data.amount,
                        )
                    )
                except ValueError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=str(exc),
                    ) from exc
            payment = await self.payments.create(
                organization_id,
                data,
                datetime.now(timezone.utc).replace(tzinfo=None),
            )
            await self.audit.record(
                organization_id,
                actor_id,
                "PAYMENT_RECEIVED",
                "Payment",
                payment.id,
                new_value={"amount": str(data.amount), "invoice_id": data.invoice_id},
                transaction_id=payment.id,
                request_id=data.external_reference,
            )
            if invoice is not None:
                invoice.status = status_value
                invoice.paid_amount = paid_amount
                invoice.credited_amount = credited_amount
                self.session.add(
                    PaymentAllocation(
                        organization_id=organization_id,
                        payment_id=payment.id,
                        invoice_id=invoice.id,
                        amount=data.amount,
                        allocated_at=datetime.now(timezone.utc).isoformat(),
                        idempotency_key=f"payment:{payment.id}:initial",
                        allocated_by_user_id=actor_id,
                    )
                )
                await self.session.flush()
            await self.session.commit()
        except HTTPException:
            await self.session.rollback()
            raise
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment external reference or allocation already exists",
            ) from exc
        await self.session.refresh(payment)
        return payment

    @staticmethod
    def _validate_invoice_payment(invoice, data: PaymentCreate) -> None:
        if invoice.status not in {InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only issued invoices with an outstanding amount can receive payments",
            )
        if data.payment_date < invoice.invoice_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Payment date must not precede invoice date",
            )

    async def list_payments(
        self, organization_id: str, invoice_id: str
    ) -> list[Payment]:
        return await self.payments.list_by_invoice(organization_id, invoice_id)
