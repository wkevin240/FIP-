from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.inventory.stock_balance import StockBalance
from app.models.invoicing.credit_note import CreditNote
from app.models.invoicing.invoice import Invoice
from app.models.invoicing.payment import Payment
from app.models.invoicing.payment_allocation import (
    PaymentAllocation,
    SupplierPaymentAllocation,
)
from app.models.procurement import PurchaseInvoice, SupplierPayment
from app.schemas.accounting.financial_calculation import ProfitabilityMetric
from app.schemas.accounting.kpi import KPIMetricResponse, KPIResponse
from app.services.accounting.financial_calculation_service import (
    FinancialCalculationService,
)
from app.services.treasury.accounting_treasury_reconciliation_service import (
    AccountingTreasuryReconciliationService,
)
from app.services.treasury.liquidity_control_service import LiquidityControlService
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

_CORE_CODES = (
    "REVENUE",
    "GROSS_PROFIT",
    "GROSS_MARGIN",
    "OPERATING_INCOME",
    "OPERATING_MARGIN",
    "NET_INCOME",
    "NET_MARGIN",
)


class KPIService:
    """Read-only operating KPIs consuming canonical module services and sources."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.calculation = FinancialCalculationService(session)
        self.liquidity = LiquidityControlService(session)
        self.reconciliation = AccountingTreasuryReconciliationService(session)

    async def _resolve_period(
        self,
        organization_id: str,
        fiscal_period_id: str | None,
        period_start: date | None,
        period_end: date | None,
    ) -> tuple[date, date]:
        if fiscal_period_id:
            period = await self.session.scalar(
                select(FiscalPeriod).where(
                    FiscalPeriod.organization_id == organization_id,
                    FiscalPeriod.id == fiscal_period_id,
                )
            )
            if period is None:
                raise HTTPException(status_code=404, detail="Fiscal period not found")
            if period_start is not None and period_start != period.start_date:
                raise HTTPException(
                    status_code=422,
                    detail="period_start does not match fiscal_period_id",
                )
            if period_end is not None and period_end != period.end_date:
                raise HTTPException(
                    status_code=422, detail="period_end does not match fiscal_period_id"
                )
            return period.start_date, period.end_date
        if period_start is None or period_end is None:
            raise HTTPException(
                status_code=422,
                detail="period_start and period_end are required without fiscal_period_id",
            )
        if period_start > period_end:
            raise HTTPException(
                status_code=422, detail="period_start must be before period_end"
            )
        return period_start, period_end

    @staticmethod
    def _metric(
        source: ProfitabilityMetric,
        *,
        value: Decimal | None = None,
        formula: str | None = None,
        unit: str = "amount",
        name: str | None = None,
    ) -> KPIMetricResponse:
        source_ids = list(source.journal_entry_line_ids)
        status = source.status
        reason = source.reason
        resolved_value = value if value is not None else source.value
        if status == "READY" and not source_ids:
            status = "NOT_READY"
            resolved_value = None
            reason = "No POSTED source lines exist in the requested scope"
        return KPIMetricResponse(
            code=source.code,
            name=name or source.code,
            label=name or source.code,
            value=resolved_value,
            unit=unit,
            formula=formula or source.formula,
            period_start=source.period_start,
            period_end=source.period_end,
            status=status,
            reason=reason,
            source_modules=["Accounting"],
            source_ids=source_ids,
            dimensions=list(source.dimensions),
        )

    async def _ar_snapshot(
        self, organization_id: str, as_of: date
    ) -> tuple[Decimal, Decimal, Decimal, Decimal, list[str], list[str], list[str]]:
        invoices = list(
            await self.session.scalars(
                select(Invoice).where(
                    Invoice.organization_id == organization_id,
                    Invoice.status.in_(("ISSUED", "PARTIALLY_PAID", "PAID")),
                    Invoice.invoice_date <= as_of,
                )
            )
        )
        invoice_ids = [invoice.id for invoice in invoices]
        allocations: dict[str, Decimal] = {}
        allocation_ids: list[str] = []
        if invoice_ids:
            allocation_rows = list(
                await self.session.scalars(
                    select(PaymentAllocation)
                    .join(Payment, Payment.id == PaymentAllocation.payment_id)
                    .where(
                        PaymentAllocation.organization_id == organization_id,
                        PaymentAllocation.invoice_id.in_(invoice_ids),
                        Payment.payment_date <= as_of,
                    )
                )
            )
            for allocation in allocation_rows:
                allocations[allocation.invoice_id] = allocations.get(
                    allocation.invoice_id, ZERO
                ) + Decimal(allocation.amount)
                allocation_ids.append(allocation.id)
        credits: dict[str, Decimal] = {}
        credit_ids: list[str] = []
        if invoice_ids:
            credit_rows = list(
                await self.session.scalars(
                    select(CreditNote).where(
                        CreditNote.organization_id == organization_id,
                        CreditNote.invoice_id.in_(invoice_ids),
                        CreditNote.credit_date <= as_of,
                    )
                )
            )
            for credit in credit_rows:
                credits[credit.invoice_id] = credits.get(
                    credit.invoice_id, ZERO
                ) + Decimal(credit.amount)
                credit_ids.append(credit.id)
        gross = sum((Decimal(invoice.total_amount) for invoice in invoices), ZERO)
        paid = sum(allocations.values(), ZERO)
        credited = sum(credits.values(), ZERO)
        outstanding = ZERO
        overdue = ZERO
        for invoice in invoices:
            balance = max(
                ZERO,
                Decimal(invoice.total_amount)
                - allocations.get(invoice.id, ZERO)
                - credits.get(invoice.id, ZERO),
            ).quantize(CENT)
            outstanding += balance
            if invoice.due_date is not None and invoice.due_date < as_of:
                overdue += balance
        source_ids = invoice_ids + allocation_ids + credit_ids
        return (
            gross.quantize(CENT),
            paid.quantize(CENT),
            credited.quantize(CENT),
            outstanding.quantize(CENT),
            overdue.quantize(CENT),
            source_ids,
            invoice_ids,
        )

    async def _ap_snapshot(
        self, organization_id: str, as_of: date
    ) -> tuple[Decimal, Decimal, Decimal, Decimal, list[str], list[str]]:
        invoices = list(
            await self.session.scalars(
                select(PurchaseInvoice).where(
                    PurchaseInvoice.organization_id == organization_id,
                    PurchaseInvoice.status.in_(("VALIDATED", "PARTIALLY_PAID", "PAID")),
                    PurchaseInvoice.invoice_date <= as_of,
                )
            )
        )
        invoice_ids = [invoice.id for invoice in invoices]
        allocations: dict[str, Decimal] = {}
        allocation_ids: list[str] = []
        if invoice_ids:
            rows = list(
                await self.session.scalars(
                    select(SupplierPaymentAllocation)
                    .join(
                        SupplierPayment,
                        SupplierPayment.id
                        == SupplierPaymentAllocation.supplier_payment_id,
                    )
                    .where(
                        SupplierPaymentAllocation.organization_id == organization_id,
                        SupplierPaymentAllocation.purchase_invoice_id.in_(invoice_ids),
                        SupplierPayment.payment_date <= as_of,
                    )
                )
            )
            for allocation in rows:
                allocations[allocation.purchase_invoice_id] = allocations.get(
                    allocation.purchase_invoice_id, ZERO
                ) + Decimal(allocation.allocated_amount)
                allocation_ids.append(allocation.id)
        gross = sum((Decimal(invoice.total_amount) for invoice in invoices), ZERO)
        paid = sum(allocations.values(), ZERO)
        outstanding = ZERO
        overdue = ZERO
        for invoice in invoices:
            balance = max(
                ZERO,
                Decimal(invoice.total_amount) - allocations.get(invoice.id, ZERO),
            ).quantize(CENT)
            outstanding += balance
            if invoice.due_date is not None and invoice.due_date < as_of:
                overdue += balance
        return (
            gross.quantize(CENT),
            paid.quantize(CENT),
            outstanding.quantize(CENT),
            overdue.quantize(CENT),
            invoice_ids + allocation_ids,
            invoice_ids,
        )

    @staticmethod
    def _operational_metric(
        *,
        code: str,
        label: str,
        value: Decimal | None,
        formula: str,
        start: date,
        end: date,
        status: str,
        reason: str | None,
        source_ids: list[str],
        source_modules: list[str],
        dimensions: list[str] | None = None,
        numerator: Decimal | None = None,
        denominator: Decimal | None = None,
        days: Decimal | None = None,
        blockers: list[str] | None = None,
        inputs: dict[str, Decimal | str | int] | None = None,
    ) -> KPIMetricResponse:
        return KPIMetricResponse(
            code=code,
            name=code,
            label=label,
            value=value.quantize(CENT, rounding=ROUND_HALF_UP)
            if value is not None
            else None,
            unit="amount" if code not in {"DSO", "DPO", "CASH_COVERAGE"} else "days",
            formula=formula,
            period_start=start,
            period_end=end,
            status=status,
            reason=reason,
            source_modules=source_modules,
            source_ids=source_ids,
            dimensions=dimensions or [],
            numerator=numerator,
            denominator=denominator,
            days=days,
            blockers=blockers or ([reason] if reason else []),
            inputs=inputs or {},
        )

    async def calculate(
        self,
        organization_id: str,
        fiscal_period_id: str | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
        as_of: date | None = None,
        dimension_id: str | None = None,
        dimension_value_id: str | None = None,
    ) -> KPIResponse:
        start, end = await self._resolve_period(
            organization_id, fiscal_period_id, period_start, period_end
        )
        snapshot_date = as_of or end
        if snapshot_date < start:
            raise HTTPException(
                status_code=422, detail="as_of must be on or after period_start"
            )
        effective_end = min(end, snapshot_date)
        profitability = await self.calculation.profitability(
            organization_id, start, effective_end, dimension_id, dimension_value_id
        )
        by_code = {metric.code: metric for metric in profitability.metrics}
        labels = {
            "REVENUE": "Produits",
            "GROSS_PROFIT": "Marge brute en valeur",
            "GROSS_MARGIN": "Marge brute",
            "OPERATING_INCOME": "Résultat d’exploitation",
            "OPERATING_MARGIN": "Marge opérationnelle",
            "NET_INCOME": "Résultat net",
            "NET_MARGIN": "Marge nette",
        }
        metrics: list[KPIMetricResponse] = []
        for code in _CORE_CODES:
            source = by_code.get(code)
            if source is None:
                continue
            if code.endswith("MARGIN"):
                metrics.append(
                    self._metric(
                        source,
                        value=(source.value * Decimal("100.00")).quantize(
                            CENT, rounding=ROUND_HALF_UP
                        )
                        if source.value is not None
                        else None,
                        formula=f"({source.formula}) × 100",
                        unit="percent",
                        name=labels[code],
                    )
                )
            else:
                metrics.append(self._metric(source, name=labels[code]))

        (
            _gross_ar,
            _paid_ar,
            _credited_ar,
            ar,
            _ar_overdue,
            ar_sources,
            ar_invoice_ids,
        ) = await self._ar_snapshot(organization_id, snapshot_date)
        (
            gross_ap,
            _paid_ap,
            ap,
            _ap_overdue,
            ap_sources,
            ap_invoice_ids,
        ) = await self._ap_snapshot(organization_id, snapshot_date)
        ar_status = "READY" if ar_invoice_ids else "NOT_READY"
        ar_reason = (
            None
            if ar_invoice_ids
            else "No issued customer invoice source exists as of the requested date"
        )
        metrics.append(
            self._operational_metric(
                code="AR_OUTSTANDING",
                label="Créances clients",
                value=ar,
                formula="gross receivable - canonical allocations - issued credits",
                start=start,
                end=effective_end,
                status=ar_status,
                reason=ar_reason,
                source_ids=ar_sources,
                source_modules=["Invoicing", "ReceivableService"],
                inputs={
                    "gross_receivable": _gross_ar,
                    "paid": _paid_ar,
                    "credited": _credited_ar,
                    "outstanding": ar,
                    "overdue": _ar_overdue,
                    "as_of": snapshot_date.isoformat(),
                },
            )
        )
        metrics.append(
            self._operational_metric(
                code="AP_OUTSTANDING",
                label="Dettes fournisseurs",
                value=ap,
                formula="gross payable - canonical supplier allocations",
                start=start,
                end=effective_end,
                status="READY" if ap_invoice_ids else "NOT_READY",
                reason=None
                if ap_invoice_ids
                else "No validated supplier invoice source exists as of the requested date",
                source_ids=ap_sources,
                source_modules=["Procurement", "PaymentControlService"],
                inputs={
                    "gross_payable": gross_ap,
                    "paid": _paid_ap,
                    "outstanding": ap,
                    "overdue": _ap_overdue,
                    "as_of": snapshot_date.isoformat(),
                },
            )
        )

        days = Decimal((effective_end - start).days + 1)
        revenue_source = by_code.get("REVENUE")
        revenue = (
            revenue_source.value
            if revenue_source and revenue_source.status == "READY"
            else None
        )
        opening_ar = await self._ar_snapshot(organization_id, start - timedelta(days=1))
        opening_ap = await self._ap_snapshot(organization_id, start - timedelta(days=1))
        average_ar = (
            ((opening_ar[3] + ar) / Decimal("2.00")).quantize(CENT)
            if ar_invoice_ids and opening_ar[6] or ar_invoice_ids
            else None
        )
        average_ap = (
            ((opening_ap[2] + ap) / Decimal("2.00")).quantize(CENT)
            if ap_invoice_ids and opening_ap[5] or ap_invoice_ids
            else None
        )
        if average_ar is not None and revenue is not None and revenue > ZERO:
            dso_value = (average_ar / revenue * days).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
            metrics.append(
                self._operational_metric(
                    code="DSO",
                    label="Délai moyen de recouvrement",
                    value=dso_value,
                    formula="average AR / credit revenue × days",
                    start=start,
                    end=effective_end,
                    status="READY",
                    reason=None,
                    source_ids=opening_ar[5]
                    + ar_sources
                    + revenue_source.journal_entry_line_ids,
                    source_modules=["Invoicing", "Accounting"],
                    numerator=average_ar,
                    denominator=revenue,
                    days=days,
                )
            )
        else:
            reason = (
                "Revenue denominator is absent or zero"
                if revenue is None or revenue <= ZERO
                else "AR source is unavailable for the requested period"
            )
            metrics.append(
                self._operational_metric(
                    code="DSO",
                    label="Délai moyen de recouvrement",
                    value=None,
                    formula="average AR / credit revenue × days",
                    start=start,
                    end=effective_end,
                    status="NOT_READY",
                    reason=reason,
                    source_ids=[],
                    source_modules=["Invoicing", "Accounting"],
                    numerator=average_ar,
                    denominator=revenue,
                    days=days,
                )
            )
        purchases = gross_ap
        if average_ap is not None and purchases > ZERO:
            dpo_value = (average_ap / purchases * days).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
            metrics.append(
                self._operational_metric(
                    code="DPO",
                    label="Délai moyen de paiement fournisseur",
                    value=dpo_value,
                    formula="average AP / validated supplier invoice total × days",
                    start=start,
                    end=effective_end,
                    status="READY",
                    reason=None,
                    source_ids=opening_ap[4] + ap_sources,
                    source_modules=["Procurement", "Accounting"],
                    numerator=average_ap,
                    denominator=purchases,
                    days=days,
                )
            )
        else:
            metrics.append(
                self._operational_metric(
                    code="DPO",
                    label="Délai moyen de paiement fournisseur",
                    value=None,
                    formula="average AP / validated supplier invoice total × days",
                    start=start,
                    end=effective_end,
                    status="NOT_READY",
                    reason="Validated supplier invoice total denominator is absent or zero",
                    source_ids=[],
                    source_modules=["Procurement"],
                )
            )

        stock_value = None
        stock_ids: list[str] = []
        today = datetime.now(timezone.utc).date()
        if snapshot_date >= today:
            balances = list(
                await self.session.scalars(
                    select(StockBalance).where(
                        StockBalance.organization_id == organization_id
                    )
                )
            )
            if balances:
                stock_value = sum(
                    (Decimal(row.total_value) for row in balances), ZERO
                ).quantize(CENT)
                stock_ids = [row.id for row in balances]
        if stock_value is not None and ar_status == "READY" and ap_invoice_ids:
            wc = ar + stock_value - ap
            metrics.append(
                self._operational_metric(
                    code="WORKING_CAPITAL",
                    label="Fonds de roulement",
                    value=wc,
                    formula="AR Outstanding + Inventory - AP Outstanding",
                    start=start,
                    end=effective_end,
                    status="READY",
                    reason=None,
                    source_ids=ar_sources + stock_ids + ap_sources,
                    source_modules=["Invoicing", "Inventory", "Procurement"],
                )
            )
            metrics.append(
                self._operational_metric(
                    code="NET_WORKING_CAPITAL",
                    label="Besoin en fonds de roulement net",
                    value=wc,
                    formula="AR Outstanding + Inventory - AP Outstanding",
                    start=start,
                    end=effective_end,
                    status="READY",
                    reason=None,
                    source_ids=ar_sources + stock_ids + ap_sources,
                    source_modules=["Invoicing", "Inventory", "Procurement"],
                )
            )
        else:
            reason = (
                "Inventory source is unavailable for the requested as_of date"
                if stock_value is None
                else "AR or AP source is unavailable"
            )
            for code, label in (
                ("WORKING_CAPITAL", "Fonds de roulement"),
                ("NET_WORKING_CAPITAL", "Besoin en fonds de roulement net"),
            ):
                metrics.append(
                    self._operational_metric(
                        code=code,
                        label=label,
                        value=None,
                        formula="AR Outstanding + Inventory - AP Outstanding",
                        start=start,
                        end=effective_end,
                        status="NOT_READY",
                        reason=reason,
                        source_ids=[],
                        source_modules=["Invoicing", "Inventory", "Procurement"],
                    )
                )

        liquidity = await self.liquidity.control(
            organization_id, None, snapshot_date, snapshot_date
        )
        liquidity_status = "READY" if liquidity.status == "READY" else "INCOMPLETE"
        liquidity_reason = (
            None
            if liquidity_status == "READY"
            else "; ".join(liquidity.current_period_blockers)
            or "Liquidity source is not fully reconciled"
        )
        metrics.append(
            self._operational_metric(
                code="LIQUIDITY",
                label="Liquidité nette",
                value=liquidity.net_liquidity if liquidity_status == "READY" else None,
                formula="Cash + AR Outstanding - AP Outstanding",
                start=start,
                end=effective_end,
                status=liquidity_status,
                reason=liquidity_reason,
                source_ids=[],
                source_modules=["LiquidityControlService", "Treasury"],
            )
        )
        reconciliation = await self.reconciliation.report(
            organization_id, snapshot_date
        )
        reconciliation_reason = (
            "; ".join(reconciliation.blockers) if reconciliation.blockers else None
        )
        metrics.append(
            self._operational_metric(
                code="RECONCILIATION",
                label="Réconciliation paiements, banque et Accounting",
                value=None,
                formula="Payment ↔ BankTransaction ↔ POSTED Accounting posting",
                start=start,
                end=effective_end,
                status=reconciliation.status,
                reason=reconciliation_reason,
                source_ids=[],
                source_modules=["AccountingTreasuryReconciliationService"],
                inputs={
                    "bank_transactions": reconciliation.bank_transactions,
                    "payments": reconciliation.payments,
                    "matched_payments": reconciliation.matched_payments,
                    "unmatched_payments": reconciliation.unmatched_payments,
                    "missing_postings": reconciliation.missing_postings,
                    "unresolved_bank_transactions": reconciliation.unresolved_bank_transactions,
                    "amount_differences": reconciliation.amount_differences,
                    "as_of": snapshot_date.isoformat(),
                },
            )
        )
        metrics.append(
            self._operational_metric(
                code="CASH_COVERAGE",
                label="Couverture de trésorerie",
                value=None,
                formula="Cash coverage definition not configured",
                start=start,
                end=effective_end,
                status="NOT_READY",
                reason="CASH_COVERAGE_DEFINITION_NOT_CONFIGURED",
                source_ids=[],
                source_modules=["LiquidityControlService"],
            )
        )

        core = [metric for metric in metrics if metric.code in _CORE_CODES]
        blockers = sorted(
            {
                metric.reason
                for metric in metrics
                if metric.reason and metric.status != "READY"
            }
        )
        if not core or not any(metric.status == "READY" for metric in core):
            overall = (
                "INCOMPLETE"
                if any(metric.status == "INCOMPLETE" for metric in core)
                else "NOT_READY"
            )
        elif all(metric.status == "READY" for metric in metrics):
            overall = "READY"
        else:
            overall = "INCOMPLETE"
        return KPIResponse(
            organization_id=organization_id,
            fiscal_period_id=fiscal_period_id,
            period_start=start,
            period_end=effective_end,
            status=overall,
            metrics=metrics,
            source_modules=[
                "FinancialCalculationService",
                "ReceivableService",
                "PaymentControlService",
                "LiquidityControlService",
            ],
            blockers=blockers,
        )
