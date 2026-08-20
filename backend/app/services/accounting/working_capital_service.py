from datetime import date
from decimal import Decimal

from app.models.inventory.stock_balance import StockBalance
from app.models.invoicing.invoice import Invoice
from app.models.procurement import PurchaseInvoice
from app.schemas.accounting.working_capital import (
    WorkingCapitalMetric,
    WorkingCapitalResponse,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")
DAYS = Decimal(365)


class WorkingCapitalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def calculate(
        self, organization_id: str, period_start: date, as_of_date: date
    ) -> WorkingCapitalResponse:
        self._validate_dates(period_start, as_of_date)
        ar_rows = await self.session.execute(
            select(
                Invoice.total_amount, Invoice.paid_amount, Invoice.credited_amount
            ).where(
                Invoice.organization_id == organization_id,
                Invoice.invoice_date >= period_start,
                Invoice.invoice_date <= as_of_date,
                Invoice.status.in_(("ISSUED", "PARTIALLY_PAID", "PAID")),
            )
        )
        ar_total = Decimal("0.00")
        ar_revenue = Decimal("0.00")
        for total, paid, credited in ar_rows:
            ar_total += Decimal(total)
            ar_revenue += Decimal(total)
        ar_paid_rows = await self.session.execute(
            select(func.coalesce(func.sum(Invoice.paid_amount), 0)).where(
                Invoice.organization_id == organization_id,
                Invoice.invoice_date >= period_start,
                Invoice.invoice_date <= as_of_date,
                Invoice.status.in_(("ISSUED", "PARTIALLY_PAID", "PAID")),
            )
        )
        ar_paid = Decimal(ar_paid_rows.scalar_one() or 0)
        ar_credited_rows = await self.session.execute(
            select(func.coalesce(func.sum(Invoice.credited_amount), 0)).where(
                Invoice.organization_id == organization_id,
                Invoice.invoice_date >= period_start,
                Invoice.invoice_date <= as_of_date,
                Invoice.status.in_(("ISSUED", "PARTIALLY_PAID", "PAID")),
            )
        )
        ar_credited = Decimal(ar_credited_rows.scalar_one() or 0)
        accounts_receivable = max(
            Decimal("0.00"), ar_total - ar_paid - ar_credited
        ).quantize(CENT)

        ap_rows = await self.session.execute(
            select(PurchaseInvoice.total_amount, PurchaseInvoice.paid_amount).where(
                PurchaseInvoice.organization_id == organization_id,
                PurchaseInvoice.invoice_date >= period_start,
                PurchaseInvoice.invoice_date <= as_of_date,
                PurchaseInvoice.status.in_(("VALIDATED", "PARTIALLY_PAID", "PAID")),
            )
        )
        ap_total = Decimal("0.00")
        ap_paid = Decimal("0.00")
        for total, paid in ap_rows:
            ap_total += Decimal(total)
            ap_paid += Decimal(paid)
        accounts_payable = max(Decimal("0.00"), ap_total - ap_paid).quantize(CENT)

        inventory_result = await self.session.scalar(
            select(func.coalesce(func.sum(StockBalance.total_value), 0)).where(
                StockBalance.organization_id == organization_id
            )
        )
        inventory_value = Decimal(inventory_result or 0).quantize(CENT)
        operating_working_capital = (
            accounts_receivable + inventory_value - accounts_payable
        ).quantize(CENT)
        dso = self._days_metric(
            "DSO", accounts_receivable, ar_revenue, "customer invoices"
        )
        dpo = self._days_metric("DPO", accounts_payable, ap_total, "supplier invoices")
        dio = WorkingCapitalMetric(
            code="DIO",
            value=None,
            status="NOT_READY",
            source="inventory balances",
            explanation="COGS mapping is not configured for the organization; inventory days cannot be calculated safely.",
        )
        ccc = WorkingCapitalMetric(
            code="CCC",
            value=None,
            status="NOT_READY",
            source="DSO + DIO - DPO",
            explanation="CCC remains NOT_READY because DIO requires a real organization-level COGS mapping.",
        )
        return WorkingCapitalResponse(
            organization_id=organization_id,
            period_start=period_start,
            as_of_date=as_of_date,
            accounts_receivable=accounts_receivable,
            inventory_value=inventory_value,
            accounts_payable=accounts_payable,
            operating_working_capital=operating_working_capital,
            dso=dso,
            dpo=dpo,
            dio=dio,
            cash_conversion_cycle=ccc,
        )

    @staticmethod
    def _validate_dates(period_start: date, as_of_date: date) -> None:
        if period_start > as_of_date:
            raise ValueError("period_start must not be after as_of_date")

    @staticmethod
    def _days_metric(
        code: str, numerator: Decimal, denominator: Decimal, source: str
    ) -> WorkingCapitalMetric:
        if denominator <= 0:
            return WorkingCapitalMetric(
                code=code,
                value=None,
                status="NOT_READY",
                source=source,
                explanation=f"No positive {source} denominator exists for the selected period.",
            )
        return WorkingCapitalMetric(
            code=code,
            value=(numerator / denominator * DAYS).quantize(CENT),
            status="READY",
            source=source,
        )
