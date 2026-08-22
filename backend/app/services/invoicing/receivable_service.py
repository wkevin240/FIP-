from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

from app.models.invoicing.invoice import Invoice
from app.models.invoicing.payment import Payment
from app.models.invoicing.payment_allocation import PaymentAllocation
from app.schemas.invoicing.payment import (
    PaymentAllocationCreate,
    ReceivableCustomerBalanceResponse,
    ReceivableInvoiceResponse,
    ReceivableStatementResponse,
)
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")


class ReceivableService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def allocate_payment(
        self,
        organization_id: str,
        actor_id: str,
        payment_id: str,
        data: PaymentAllocationCreate,
    ) -> PaymentAllocation:
        existing = await self.session.scalar(
            select(PaymentAllocation).where(
                PaymentAllocation.organization_id == organization_id,
                PaymentAllocation.idempotency_key == data.idempotency_key,
            )
        )
        if existing is not None:
            return existing
        payment = await self.session.scalar(
            select(Payment)
            .where(Payment.organization_id == organization_id, Payment.id == payment_id)
            .with_for_update()
        )
        invoice = await self.session.scalar(
            select(Invoice)
            .where(
                Invoice.organization_id == organization_id,
                Invoice.id == data.invoice_id,
            )
            .with_for_update()
        )
        if payment is None or invoice is None:
            raise HTTPException(status_code=404, detail="Payment or invoice not found")
        if invoice.status in {"DRAFT", "CANCELLED"}:
            raise HTTPException(status_code=422, detail="Invoice is not allocatable")
        if data.amount > Decimal(payment.amount):
            raise HTTPException(
                status_code=422, detail="Allocation exceeds payment amount"
            )
        allocated = Decimal(
            await self.session.scalar(
                select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
                    PaymentAllocation.organization_id == organization_id,
                    PaymentAllocation.payment_id == payment.id,
                )
            )
            or 0
        )
        if allocated + data.amount > Decimal(payment.amount):
            raise HTTPException(
                status_code=422, detail="Allocation exceeds unapplied payment balance"
            )
        outstanding = (
            Decimal(invoice.total_amount)
            - Decimal(invoice.paid_amount)
            - Decimal(invoice.credited_amount)
        )
        if data.amount > outstanding:
            raise HTTPException(
                status_code=422, detail="Allocation exceeds invoice outstanding balance"
            )
        allocation = PaymentAllocation(
            organization_id=organization_id,
            payment_id=payment.id,
            invoice_id=invoice.id,
            amount=data.amount,
            allocated_at=datetime.now(timezone.utc).isoformat(),
            idempotency_key=data.idempotency_key,
            allocated_by_user_id=actor_id,
        )
        self.session.add(allocation)
        invoice.paid_amount = (Decimal(invoice.paid_amount) + data.amount).quantize(
            CENT
        )
        invoice.status = (
            "PAID"
            if invoice.paid_amount + Decimal(invoice.credited_amount)
            >= Decimal(invoice.total_amount)
            else "PARTIALLY_PAID"
        )
        if payment.invoice_id is None:
            payment.invoice_id = invoice.id
        await self.session.flush()
        try:
            await self.audit.record(
                organization_id,
                actor_id,
                "PAYMENT_ALLOCATED_TO_INVOICE",
                "PaymentAllocation",
                allocation.id,
                new_value={
                    "payment_id": payment.id,
                    "invoice_id": invoice.id,
                    "amount": str(data.amount),
                },
                transaction_id=allocation.id,
                request_id=data.idempotency_key,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.session.scalar(
                select(PaymentAllocation).where(
                    PaymentAllocation.organization_id == organization_id,
                    PaymentAllocation.idempotency_key == data.idempotency_key,
                )
            )
            if existing is not None:
                return existing
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment allocation already exists",
            ) from exc
        await self.session.refresh(allocation)
        return allocation

    async def statement(
        self,
        organization_id: str,
        as_of_date: date,
        customer_key: str | None = None,
    ) -> ReceivableStatementResponse:
        query = (
            select(Invoice)
            .where(
                Invoice.organization_id == organization_id,
                Invoice.status.in_(("ISSUED", "PARTIALLY_PAID", "PAID")),
                Invoice.invoice_date <= as_of_date,
            )
            .order_by(
                Invoice.customer_name, Invoice.invoice_date, Invoice.invoice_number
            )
        )
        invoices = list(await self.session.scalars(query))
        groups: dict[str, list[ReceivableInvoiceResponse]] = defaultdict(list)
        names: dict[str, tuple[str, str | None]] = {}
        for invoice in invoices:
            key = invoice.customer_tax_id or invoice.customer_name.strip().casefold()
            if customer_key and key != customer_key:
                continue
            outstanding = max(
                Decimal("0.00"),
                Decimal(invoice.total_amount)
                - Decimal(invoice.paid_amount)
                - Decimal(invoice.credited_amount),
            ).quantize(CENT)
            bucket, overdue = self._age(invoice.due_date, as_of_date, outstanding)
            row = ReceivableInvoiceResponse(
                invoice_id=invoice.id,
                invoice_number=invoice.invoice_number,
                customer_name=invoice.customer_name,
                customer_tax_id=invoice.customer_tax_id,
                invoice_date=invoice.invoice_date,
                due_date=invoice.due_date,
                total_amount=Decimal(invoice.total_amount),
                paid_amount=Decimal(invoice.paid_amount),
                credited_amount=Decimal(invoice.credited_amount),
                outstanding_amount=outstanding,
                age_bucket=bucket,
                overdue_amount=overdue,
            )
            groups[key].append(row)
            names[key] = (invoice.customer_name, invoice.customer_tax_id)
        customers = []
        for key, rows in groups.items():
            customers.append(
                ReceivableCustomerBalanceResponse(
                    customer_key=key,
                    customer_name=names[key][0],
                    customer_tax_id=names[key][1],
                    outstanding_amount=sum(
                        (row.outstanding_amount for row in rows), Decimal("0.00")
                    ).quantize(CENT),
                    overdue_amount=sum(
                        (row.overdue_amount for row in rows), Decimal("0.00")
                    ).quantize(CENT),
                    invoices=rows,
                )
            )
        return ReceivableStatementResponse(
            organization_id=organization_id,
            as_of_date=as_of_date,
            customer_key=customer_key,
            total_invoiced=sum(
                (
                    row.total_amount
                    for customer in customers
                    for row in customer.invoices
                ),
                Decimal("0.00"),
            ).quantize(CENT),
            total_paid=sum(
                (
                    row.paid_amount
                    for customer in customers
                    for row in customer.invoices
                ),
                Decimal("0.00"),
            ).quantize(CENT),
            total_credited=sum(
                (
                    row.credited_amount
                    for customer in customers
                    for row in customer.invoices
                ),
                Decimal("0.00"),
            ).quantize(CENT),
            total_outstanding=sum(
                (customer.outstanding_amount for customer in customers), Decimal("0.00")
            ).quantize(CENT),
            total_overdue=sum(
                (customer.overdue_amount for customer in customers), Decimal("0.00")
            ).quantize(CENT),
            customers=customers,
        )

    @staticmethod
    def _age(
        due_date: date | None, as_of_date: date, outstanding: Decimal
    ) -> tuple[str | None, Decimal]:
        if outstanding <= 0:
            return None, Decimal("0.00")
        if due_date is None or due_date >= as_of_date:
            return "CURRENT", Decimal("0.00")
        days = (as_of_date - due_date).days
        bucket = (
            "1-30"
            if days <= 30
            else "31-60"
            if days <= 60
            else "61-90"
            if days <= 90
            else "90+"
        )
        return bucket, outstanding
