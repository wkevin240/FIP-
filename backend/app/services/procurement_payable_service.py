from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.procurement import PurchaseInvoice, Supplier
from app.schemas.procurement_payables import (
    PayableInvoiceResponse,
    PayableStatementResponse,
    PayableSupplierBalanceResponse,
)

CENT = Decimal("0.01")


class PayableService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def statement(
        self,
        organization_id: str,
        as_of_date: date,
        supplier_id: str | None = None,
    ) -> PayableStatementResponse:
        if supplier_id:
            supplier = await self.session.scalar(
                select(Supplier.id).where(
                    Supplier.organization_id == organization_id,
                    Supplier.id == supplier_id,
                )
            )
            if supplier is None:
                raise HTTPException(status_code=404, detail="Supplier not found")
        query = (
            select(PurchaseInvoice, Supplier)
            .join(
                Supplier,
                (Supplier.organization_id == PurchaseInvoice.organization_id)
                & (Supplier.id == PurchaseInvoice.supplier_id),
            )
            .where(
                PurchaseInvoice.organization_id == organization_id,
                PurchaseInvoice.status.in_(("VALIDATED", "PARTIALLY_PAID", "PAID")),
                PurchaseInvoice.invoice_date <= as_of_date,
            )
            .order_by(
                Supplier.legal_name,
                PurchaseInvoice.invoice_date,
                PurchaseInvoice.invoice_number,
            )
        )
        if supplier_id:
            query = query.where(PurchaseInvoice.supplier_id == supplier_id)
        rows = await self.session.execute(query)
        groups: dict[str, list[PayableInvoiceResponse]] = defaultdict(list)
        suppliers: dict[str, Supplier] = {}
        for invoice, supplier in rows:
            outstanding = max(
                Decimal("0.00"),
                Decimal(invoice.total_amount) - Decimal(invoice.paid_amount),
            ).quantize(CENT)
            bucket, overdue = self._age(invoice.due_date, as_of_date, outstanding)
            row = PayableInvoiceResponse(
                invoice_id=invoice.id,
                invoice_number=invoice.invoice_number,
                supplier_id=supplier.id,
                supplier_name=supplier.legal_name,
                supplier_tax_id=supplier.tax_id,
                invoice_date=invoice.invoice_date,
                due_date=invoice.due_date,
                total_amount=Decimal(invoice.total_amount),
                paid_amount=Decimal(invoice.paid_amount),
                outstanding_amount=outstanding,
                age_bucket=bucket,
                overdue_amount=overdue,
            )
            groups[supplier.id].append(row)
            suppliers[supplier.id] = supplier
        supplier_balances = [
            PayableSupplierBalanceResponse(
                supplier_id=supplier_id_value,
                supplier_name=suppliers[supplier_id_value].legal_name,
                supplier_tax_id=suppliers[supplier_id_value].tax_id,
                outstanding_amount=sum(
                    (row.outstanding_amount for row in invoice_rows), Decimal("0.00")
                ).quantize(CENT),
                overdue_amount=sum(
                    (row.overdue_amount for row in invoice_rows), Decimal("0.00")
                ).quantize(CENT),
                invoices=invoice_rows,
            )
            for supplier_id_value, invoice_rows in groups.items()
        ]
        return PayableStatementResponse(
            organization_id=organization_id,
            as_of_date=as_of_date,
            supplier_id=supplier_id,
            total_invoiced=sum(
                (
                    row.total_amount
                    for balance in supplier_balances
                    for row in balance.invoices
                ),
                Decimal("0.00"),
            ).quantize(CENT),
            total_paid=sum(
                (
                    row.paid_amount
                    for balance in supplier_balances
                    for row in balance.invoices
                ),
                Decimal("0.00"),
            ).quantize(CENT),
            total_outstanding=sum(
                (balance.outstanding_amount for balance in supplier_balances),
                Decimal("0.00"),
            ).quantize(CENT),
            total_overdue=sum(
                (balance.overdue_amount for balance in supplier_balances),
                Decimal("0.00"),
            ).quantize(CENT),
            suppliers=supplier_balances,
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
