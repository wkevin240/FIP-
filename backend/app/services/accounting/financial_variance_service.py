from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.schemas.accounting.financial_calculation import ProfitabilityMetric
from app.schemas.accounting.financial_variance import (
    FinancialVarianceMetric,
    FinancialVarianceResponse,
    VarianceComparison,
)
from app.services.accounting.financial_calculation_service import (
    FinancialCalculationService,
)
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")


class FinancialVarianceService:
    """Explainable variances built on FinancialCalculationService actuals."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.calculation = FinancialCalculationService(session)

    @staticmethod
    def _previous_period(start: date, end: date) -> tuple[date, date]:
        days = (end - start).days + 1
        previous_end = start - timedelta(days=1)
        return previous_end - timedelta(days=days - 1), previous_end

    @staticmethod
    def _metric_map(
        metrics: list[ProfitabilityMetric],
    ) -> dict[str, ProfitabilityMetric]:
        return {metric.code: metric for metric in metrics}

    async def calculate(
        self,
        organization_id: str,
        current_start: date,
        current_end: date,
        comparison: VarianceComparison,
        dimension_id: str | None = None,
        dimension_value_id: str | None = None,
    ) -> FinancialVarianceResponse:
        if current_start > current_end:
            raise HTTPException(
                status_code=422, detail="period_start must be before period_end"
            )

        if comparison in {VarianceComparison.BUDGET, VarianceComparison.FORECAST}:
            return FinancialVarianceResponse(
                organization_id=organization_id,
                comparison=comparison,
                current_period_start=current_start,
                current_period_end=current_end,
                comparison_period_start=None,
                comparison_period_end=None,
                status="NOT_READY",
                metrics=[],
                reason="An approved budget or forecast source is required for this comparison",
            )

        if comparison == VarianceComparison.PREVIOUS_PERIOD:
            comparison_start, comparison_end = self._previous_period(
                current_start, current_end
            )
        else:
            try:
                comparison_start = current_start.replace(year=current_start.year - 1)
                comparison_end = current_end.replace(year=current_end.year - 1)
            except ValueError as exc:
                raise HTTPException(
                    status_code=422, detail="Invalid previous-year period"
                ) from exc

        current = await self.calculation.profitability(
            organization_id,
            current_start,
            current_end,
            dimension_id=dimension_id,
            dimension_value_id=dimension_value_id,
        )
        prior = await self.calculation.profitability(
            organization_id,
            comparison_start,
            comparison_end,
            dimension_id=dimension_id,
            dimension_value_id=dimension_value_id,
        )
        current_metrics = self._metric_map(current.metrics)
        prior_metrics = self._metric_map(prior.metrics)
        metrics: list[FinancialVarianceMetric] = []
        for code in current_metrics:
            actual_metric = current_metrics[code]
            prior_metric = prior_metrics.get(code)
            actual = actual_metric.value
            comparison_value = prior_metric.value if prior_metric else None
            if actual is None or comparison_value is None:
                variance = None
                percentage = None
                metric_status = "NOT_READY"
                reason = "Actual and comparison metric must both be available"
            elif current.status == "INCOMPLETE" or prior.status == "INCOMPLETE":
                variance = None
                percentage = None
                metric_status = "INCOMPLETE"
                reason = "A source ledger is not balanced for the requested scope"
            else:
                variance = (actual - comparison_value).quantize(
                    CENT, rounding=ROUND_HALF_UP
                )
                if comparison_value == Decimal("0.00"):
                    percentage = None
                    metric_status = "READY"
                    reason = "Comparison value is zero; percentage is undefined"
                else:
                    percentage = (variance / abs(comparison_value)).quantize(
                        CENT, rounding=ROUND_HALF_UP
                    )
                    metric_status = "READY"
                    reason = None
            metrics.append(
                FinancialVarianceMetric(
                    metric=code,
                    actual=actual,
                    comparison=comparison_value,
                    variance=variance,
                    variance_percentage=percentage,
                    current_period_start=current_start,
                    current_period_end=current_end,
                    comparison_period_start=comparison_start,
                    comparison_period_end=comparison_end,
                    source_accounts=actual_metric.account_ids,
                    source_lines=actual_metric.journal_entry_line_ids,
                    comparison_source_accounts=prior_metric.account_ids
                    if prior_metric
                    else [],
                    comparison_source_lines=prior_metric.journal_entry_line_ids
                    if prior_metric
                    else [],
                    dimensions=actual_metric.dimensions,
                    status=metric_status,
                    reason=reason,
                )
            )
        status = "READY"
        reason = None
        if current.status == "INCOMPLETE" or prior.status == "INCOMPLETE":
            status = "INCOMPLETE"
            reason = "A requested POSTED ledger scope is unbalanced"
        elif current.status == "NOT_READY" or prior.status == "NOT_READY":
            status = "NOT_READY"
            reason = (
                "Required explicit profitability mappings or source metrics are missing"
            )
        return FinancialVarianceResponse(
            organization_id=organization_id,
            comparison=comparison,
            current_period_start=current_start,
            current_period_end=current_end,
            comparison_period_start=comparison_start,
            comparison_period_end=comparison_end,
            status=status,
            metrics=metrics,
            reason=reason,
        )
