from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.models.accounting.fiscal_period import FiscalPeriod
from app.schemas.accounting.financial_calculation import ProfitabilityMetric
from app.schemas.accounting.kpi import KPIMetricResponse, KPIResponse
from app.services.accounting.financial_calculation_service import (
    FinancialCalculationService,
)
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")

_CORE_CODES = (
    "REVENUE",
    "GROSS_PROFIT",
    "GROSS_MARGIN",
    "OPERATING_INCOME",
    "OPERATING_MARGIN",
    "NET_INCOME",
    "NET_MARGIN",
)

_UNAVAILABLE = {
    "DSO": (
        "Délai moyen de recouvrement",
        "days",
        "AR Outstanding / Revenue × days",
        "Customer receivables and collection-period mappings are not configured",
    ),
    "DPO": (
        "Délai moyen de paiement fournisseur",
        "days",
        "AP Outstanding / Purchases × days",
        "Supplier payables and reliable purchases denominator are not configured",
    ),
    "WORKING_CAPITAL": (
        "Fonds de roulement",
        "amount",
        "AR Outstanding + Inventory - AP Outstanding",
        "AR, Inventory and AP source services are not available in one reconciled scope",
    ),
    "NET_WORKING_CAPITAL": (
        "Besoin en fonds de roulement net",
        "amount",
        "AR Outstanding + Inventory - AP Outstanding",
        "AR, Inventory and AP source services are not available in one reconciled scope",
    ),
    "LIQUIDITY": (
        "Liquidité nette",
        "amount",
        "Cash + AR Outstanding - AP Outstanding",
        "Cash, AR and AP are not available in one reconciled scope",
    ),
    "CASH_COVERAGE": (
        "Couverture de trésorerie",
        "days",
        "Cash / average daily operating outflow",
        "Cash and a reliable operating-outflow denominator are not configured",
    ),
    "AR_OUTSTANDING": (
        "Créances clients",
        "amount",
        "Validated receivables - allocated payments",
        "A reconciled AR source is not exposed by the current central calculation contract",
    ),
    "AP_OUTSTANDING": (
        "Dettes fournisseurs",
        "amount",
        "Validated payables - allocated payments",
        "A reconciled AP source is not exposed by the current central calculation contract",
    ),
}


class KPIService:
    """Read-only management KPIs consuming the central financial calculation engine."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.calculation = FinancialCalculationService(session)

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
                    status_code=422,
                    detail="period_end does not match fiscal_period_id",
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

    async def calculate(
        self,
        organization_id: str,
        fiscal_period_id: str | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
        dimension_id: str | None = None,
        dimension_value_id: str | None = None,
    ) -> KPIResponse:
        resolved_start, resolved_end = await self._resolve_period(
            organization_id, fiscal_period_id, period_start, period_end
        )
        profitability = await self.calculation.profitability(
            organization_id,
            resolved_start,
            resolved_end,
            dimension_id,
            dimension_value_id,
        )
        by_code = {metric.code: metric for metric in profitability.metrics}
        metrics: list[KPIMetricResponse] = []
        labels = {
            "REVENUE": "Produits",
            "GROSS_PROFIT": "Marge brute en valeur",
            "GROSS_MARGIN": "Marge brute",
            "OPERATING_INCOME": "Résultat d’exploitation",
            "OPERATING_MARGIN": "Marge opérationnelle",
            "NET_INCOME": "Résultat net",
            "NET_MARGIN": "Marge nette",
        }
        for code in _CORE_CODES:
            source = by_code.get(code)
            if source is None:
                continue
            if code.endswith("MARGIN"):
                metric = self._metric(
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
            else:
                metric = self._metric(source, name=labels[code])
            metrics.append(metric)

        for code, (label, unit, formula, reason) in _UNAVAILABLE.items():
            metrics.append(
                KPIMetricResponse(
                    code=code,
                    name=code,
                    label=label,
                    value=None,
                    unit=unit,
                    formula=formula,
                    period_start=resolved_start,
                    period_end=resolved_end,
                    status="NOT_READY",
                    reason=reason,
                    source_modules=[],
                    source_ids=[],
                    dimensions=[],
                    blockers=[reason],
                )
            )

        core = [metric for metric in metrics if metric.code in _CORE_CODES]
        blockers = sorted(
            {
                metric.reason
                for metric in metrics
                if metric.reason is not None and metric.status != "READY"
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
            period_start=resolved_start,
            period_end=resolved_end,
            status=overall,
            metrics=metrics,
            source_modules=["Accounting", "FinancialCalculationService"],
            blockers=blockers,
        )
