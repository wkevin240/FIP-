from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.audit_context import AuditContext
from app.models.customer import Customer
from app.models.customer_invoice import CustomerInvoice, CustomerInvoiceStatus
from app.repositories.audit.audit_log_repository import AuditLogRepository
from app.repositories.invoicing.customer_invoice_repository import CustomerInvoiceRepository
from app.schemas.invoicing.customer_invoice import CustomerInvoiceCreate, CustomerInvoiceUpdate


class CustomerInvoiceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = CustomerInvoiceRepository(session)
        self.audit_repository = AuditLogRepository(session)

    @staticmethod
    def _audit_payload(invoice: CustomerInvoice) -> dict:
        return {
            "invoice_id": invoice.id,
            "customer_id": invoice.customer_id,
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date.isoformat(),
            "due_date": invoice.due_date.isoformat(),
            "currency_code": invoice.currency_code,
            "subtotal": str(invoice.subtotal),
            "tax_amount": str(invoice.tax_amount),
            "total_amount": str(invoice.total_amount),
            "status": invoice.status.value,
            "issued_at": invoice.issued_at.isoformat() if invoice.issued_at else None,
            "issued_by": invoice.issued_by,
        }

    async def get(self, organization_id: str, invoice_id: str) -> CustomerInvoice:
        invoice = await self.repository.get(organization_id, invoice_id)
        if invoice is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer invoice not found")
        return invoice

    async def list(
        self,
        organization_id: str,
        *,
        skip: int,
        limit: int,
        customer_id: str | None = None,
        invoice_status: CustomerInvoiceStatus | None = None,
        due_before: date | None = None,
    ) -> list[CustomerInvoice]:
        return await self.repository.list(
            organization_id,
            skip=skip,
            limit=limit,
            customer_id=customer_id,
            status=invoice_status,
            due_before=due_before,
        )

    async def create(self, organization_id: str, actor_id: str, data: CustomerInvoiceCreate) -> CustomerInvoice:
        customer = await self.session.scalar(
            select(Customer).where(
                Customer.organization_id == organization_id,
                Customer.id == data.customer_id,
            )
        )
        if customer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        if not customer.is_active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot invoice an inactive customer")

        invoice = CustomerInvoice(
            organization_id=organization_id,
            customer_id=data.customer_id,
            invoice_number=data.invoice_number,
            invoice_date=data.invoice_date,
            due_date=data.due_date,
            currency_code=data.currency_code,
            subtotal=data.subtotal,
            tax_amount=data.tax_amount,
            total_amount=data.total_amount,
            status=CustomerInvoiceStatus.DRAFT,
            created_by=actor_id,
            updated_by=actor_id,
        )
        self.repository.add(invoice)
        await self._persist_with_audit(invoice, organization_id, actor_id, "CUSTOMER_INVOICE_CREATED")
        await self.session.refresh(invoice)
        return invoice

    async def update(
        self,
        organization_id: str,
        invoice_id: str,
        actor_id: str,
        data: CustomerInvoiceUpdate,
    ) -> CustomerInvoice:
        invoice = await self.repository.get_for_update(organization_id, invoice_id)
        if invoice is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer invoice not found")
        if invoice.status != CustomerInvoiceStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft invoices can be updated")

        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return invoice
        if any(value is None for value in changes.values()):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invoice fields cannot be cleared")

        candidate = {
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date,
            "due_date": invoice.due_date,
            "currency_code": invoice.currency_code,
            "subtotal": Decimal(invoice.subtotal),
            "tax_amount": Decimal(invoice.tax_amount),
            "total_amount": Decimal(invoice.total_amount),
        }
        candidate.update(changes)
        if candidate["due_date"] < candidate["invoice_date"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="due_date must be on or after invoice_date")
        if candidate["subtotal"] + candidate["tax_amount"] != candidate["total_amount"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="total_amount must equal subtotal plus tax_amount")

        for field, value in changes.items():
            setattr(invoice, field, value)
        invoice.updated_by = actor_id
        await self._persist_with_audit(invoice, organization_id, actor_id, "CUSTOMER_INVOICE_UPDATED")
        await self.session.refresh(invoice)
        return invoice

    async def issue(self, organization_id: str, invoice_id: str, actor_id: str) -> CustomerInvoice:
        invoice = await self.repository.get_for_update(organization_id, invoice_id)
        if invoice is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer invoice not found")
        if invoice.status != CustomerInvoiceStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft invoices can be issued")
        if invoice.created_by == actor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invoice creator cannot issue the same invoice")

        invoice.status = CustomerInvoiceStatus.ISSUED
        invoice.issued_by = actor_id
        invoice.issued_at = datetime.now(timezone.utc)
        invoice.updated_by = actor_id
        await self._persist_with_audit(invoice, organization_id, actor_id, "CUSTOMER_INVOICE_ISSUED")
        await self.session.refresh(invoice)
        return invoice

    async def _persist_with_audit(
        self,
        invoice: CustomerInvoice,
        organization_id: str,
        actor_id: str,
        action: str,
    ) -> None:
        try:
            await self.session.flush()
            await self.audit_repository.append(
                AuditContext(organization_id=organization_id, actor_id=actor_id, action=action),
                entity_type="customer_invoice",
                entity_id=invoice.id,
                payload=self._audit_payload(invoice),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Customer invoice conflicts with existing data") from exc
        except Exception:
            await self.session.rollback()
            raise

