from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.models.accounting.budget import Budget, BudgetLine
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.profitability_mapping import ProfitabilityAccountMapping
from app.schemas.accounting.financial_calculation import ProfitabilityMetric
from app.schemas.accounting.financial_variance import (
    FinancialVarianceMetric,
    FinancialVarianceResponse,
    VarianceComparison,
)
from app.services.accounting.financial_calculation_service import (
    FinancialCalculationService,
)
from app.services.accounting.forecast_service import ForecastService
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

CENT = Decimal("0.01")
_REVENUE_CATEGORIES = {"REVENUE", "OTHER_INCOME"}
_EXPENSE_CATEGORIES = {"COGS", "OPERATING_EXPENSE", "OTHER_EXPENSE"}


class FinancialVarianceService:
    """Single comparison layer over the central ledger and approved FP&A sources."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.calculation = FinancialCalculationService(session)
        self.forecast = ForecastService(session)

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

    @staticmethod
    def _normalise_source_amount(category: str, amount: Decimal) -> Decimal:
        # ForecastService already returns business-facing forecast amounts.
        # Category is retained in the signature to keep the source contract explicit.
        del category
        return Decimal(amount)

    async def _budget_metrics(
        self,
        organization_id: str,
        budget_id: str | None,
        period_start: date,
        period_end: date,
        dimension_value_id: str | None,
        mappings: list[ProfitabilityAccountMapping],
    ) -> tuple[dict[str, Decimal], dict[str, list[str]], str | None]:
        if not budget_id:
            return {}, {}, "BUDGET_NOT_AVAILABLE"
        budget = await self.session.scalar(
            select(Budget).where(
                Budget.organization_id == organization_id, Budget.id == budget_id
            )
        )
        if budget is None or budget.status not in {"APPROVED", "LOCKED"}:
            return {}, {}, "BUDGET_NOT_AVAILABLE"
        mapping_by_account = {
            mapping.account_id: mapping.category for mapping in mappings
        }
        rows = await self.session.execute(
            select(BudgetLine)
            .join(FiscalPeriod, FiscalPeriod.id == BudgetLine.fiscal_period_id)
            .where(
                BudgetLine.organization_id == organization_id,
                BudgetLine.budget_id == budget.id,
                FiscalPeriod.organization_id == organization_id,
                FiscalPeriod.start_date >= period_start,
                FiscalPeriod.end_date <= period_end,
                (
                    BudgetLine.dimension_value_id == dimension_value_id
                    if dimension_value_id
                    else BudgetLine.dimension_value_id.is_(None)
                ),
            )
        )
        values: dict[str, Decimal] = {}
        sources: dict[str, list[str]] = {}
        for line in rows.scalars():
            category = mapping_by_account.get(line.account_id)
            if category is None:
                continue
            values[category] = values.get(category, Decimal("0.00")) + Decimal(
                line.amount
            )
            sources.setdefault(category, []).append(line.id)
        if not values:
            return {}, {}, "BUDGET_NOT_AVAILABLE"
        return values, sources, None

    async def _forecast_metrics(
        self,
        organization_id: str,
        budget_id: str | None,
        scenario_id: str | None,
        mappings: list[ProfitabilityAccountMapping],
    ) -> tuple[dict[str, Decimal], dict[str, list[str]], str | None]:
        if not budget_id or not scenario_id:
            return {}, {}, "FORECAST_NOT_AVAILABLE"
        forecast = await self.forecast.calculate(
            organization_id, budget_id, scenario_id
        )
        if forecast.status != "READY":
            return {}, {}, "FORECAST_NOT_AVAILABLE"
        mapping_by_account = {
            mapping.account_id: mapping.category for mapping in mappings
        }
        values: dict[str, Decimal] = {}
        sources: dict[str, list[str]] = {}
        for line in forecast.lines:
            category = mapping_by_account.get(line.account_id)
            if category is None:
                continue
            value = self._normalise_source_amount(category, line.forecast_amount)
            values[category] = values.get(category, Decimal("0.00")) + value
            sources.setdefault(category, []).append(
                f"{line.fiscal_period_id}:{line.account_id}:{line.dimension_value_id or 'none'}"
            )
        if not values:
            return {}, {}, "FORECAST_NOT_AVAILABLE"
        return values, sources, None

    async def calculate(
        self,
        organization_id: str,
        current_start: date,
        current_end: date,
        comparison: VarianceComparison,
        dimension_id: str | None = None,
        dimension_value_id: str | None = None,
        budget_id: str | None = None,
        scenario_id: str | None = None,
    ) -> FinancialVarianceResponse:
        if current_start > current_end:
            raise HTTPException(
                status_code=422, detail="period_start must be before period_end"
            )
        mappings = await self.calculation.list_mappings(organization_id)
        current = await self.calculation.profitability(
            organization_id,
            current_start,
            current_end,
            dimension_id,
            dimension_value_id,
        )
        comparison_period_start: date | None = None
        comparison_period_end: date | None = None
        comparison_values: dict[str, Decimal] | None = None
        comparison_sources: dict[str, list[str]] = {}
        source_reason: str | None = None
        if comparison == VarianceComparison.PREVIOUS_PERIOD:
            comparison_period_start, comparison_period_end = self._previous_period(
                current_start, current_end
            )
            prior = await self.calculation.profitability(
                organization_id,
                comparison_period_start,
                comparison_period_end,
                dimension_id,
                dimension_value_id,
            )
            comparison_metrics = self._metric_map(prior.metrics)
            comparison_values = {
                code: metric.value
                for code, metric in comparison_metrics.items()
                if metric.value is not None
            }
            comparison_sources = {
                code: metric.journal_entry_line_ids
                for code, metric in comparison_metrics.items()
            }
            if prior.status == "INCOMPLETE":
                source_reason = "LEDGER_OUT_OF_BALANCE"
        elif comparison == VarianceComparison.PREVIOUS_YEAR:
            try:
                comparison_period_start = current_start.replace(
                    year=current_start.year - 1
                )
                comparison_period_end = current_end.replace(year=current_end.year - 1)
            except ValueError as exc:
                raise HTTPException(
                    status_code=422, detail="Invalid previous-year period"
                ) from exc
            prior = await self.calculation.profitability(
                organization_id,
                comparison_period_start,
                comparison_period_end,
                dimension_id,
                dimension_value_id,
            )
            comparison_metrics = self._metric_map(prior.metrics)
            comparison_values = {
                code: metric.value
                for code, metric in comparison_metrics.items()
                if metric.value is not None
            }
            comparison_sources = {
                code: metric.journal_entry_line_ids
                for code, metric in comparison_metrics.items()
            }
            if prior.status == "INCOMPLETE":
                source_reason = "LEDGER_OUT_OF_BALANCE"
        elif comparison == VarianceComparison.BUDGET:
            (
                comparison_values,
                comparison_sources,
                source_reason,
            ) = await self._budget_metrics(
                organization_id,
                budget_id,
                current_start,
                current_end,
                dimension_value_id,
                mappings,
            )
        else:
            (
                comparison_values,
                comparison_sources,
                source_reason,
            ) = await self._forecast_metrics(
                organization_id, budget_id, scenario_id, mappings
            )

        current_metrics = self._metric_map(current.metrics)
        metrics: list[FinancialVarianceMetric] = []
        for code, actual_metric in current_metrics.items():
            actual = actual_metric.value
            comparison_value = (
                comparison_values.get(code) if comparison_values else None
            )
            if actual is None or comparison_value is None:
                variance = None
                percentage = None
                metric_status = (
                    "INCOMPLETE" if current.status == "INCOMPLETE" else "NOT_READY"
                )
                reason = (
                    source_reason
                    or "Actual and comparison metric must both be available"
                )
            elif (
                current.status == "INCOMPLETE"
                or source_reason == "LEDGER_OUT_OF_BALANCE"
            ):
                variance = None
                percentage = None
                metric_status = "INCOMPLETE"
                reason = "LEDGER_OUT_OF_BALANCE"
            else:
                variance = (actual - comparison_value).quantize(
                    CENT, rounding=ROUND_HALF_UP
                )
                percentage = (
                    None
                    if comparison_value == Decimal("0.00")
                    else (variance / abs(comparison_value)).quantize(
                        CENT, rounding=ROUND_HALF_UP
                    )
                )
                metric_status = "READY"
                reason = (
                    "Comparison value is zero; percentage is undefined"
                    if comparison_value == Decimal("0.00")
                    else None
                )
            metrics.append(
                FinancialVarianceMetric(
                    metric=code,
                    comparison_type=comparison,
                    actual=actual,
                    comparison=comparison_value,
                    variance=variance,
                    variance_percentage=percentage,
                    current_period_start=current_start,
                    current_period_end=current_end,
                    comparison_period_start=comparison_period_start,
                    comparison_period_end=comparison_period_end,
                    source_accounts=actual_metric.account_ids,
                    source_lines=actual_metric.journal_entry_line_ids,
                    status=metric_status,
                    reason=reason,
                    source_journal_entry_lines=actual_metric.journal_entry_line_ids,
                    comparison_source_lines=comparison_sources.get(code, []),
                    source_budget_lines=comparison_sources.get(code, [])
                    if comparison == VarianceComparison.BUDGET
                    else [],
                    source_forecast_data=comparison_sources.get(code, [])
                    if comparison == VarianceComparison.FORECAST
                    else [],
                    comparison_source_accounts=[],
                    comparison_source_budget_lines=comparison_sources.get(code, [])
                    if comparison == VarianceComparison.BUDGET
                    else [],
                    comparison_source_forecast_data=comparison_sources.get(code, [])
                    if comparison == VarianceComparison.FORECAST
                    else [],
                    dimensions=actual_metric.dimensions,
                )
            )
        if current.status == "INCOMPLETE" or source_reason == "LEDGER_OUT_OF_BALANCE":
            status = "INCOMPLETE"
            reason = "LEDGER_OUT_OF_BALANCE"
        elif source_reason:
            status = "NOT_READY"
            reason = source_reason
        else:
            status = "READY"
            reason = None
        return FinancialVarianceResponse(
            organization_id=organization_id,
            comparison=comparison,
            current_period_start=current_start,
            current_period_end=current_end,
            comparison_period_start=comparison_period_start,
            comparison_period_end=comparison_period_end,
            status=status,
            metrics=metrics,
            reason=reason,
        )
