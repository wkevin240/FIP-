from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel


class VarianceComparison(StrEnum):
    PREVIOUS_PERIOD = "PREVIOUS_PERIOD"
    PREVIOUS_YEAR = "PREVIOUS_YEAR"
    BUDGET = "BUDGET"
    FORECAST = "FORECAST"


class FinancialVarianceMetric(BaseModel):
    metric: str
    actual: Decimal | None
    comparison: Decimal | None
    variance: Decimal | None
    variance_percentage: Decimal | None
    current_period_start: date
    current_period_end: date
    comparison_period_start: date | None
    comparison_period_end: date | None
    source_accounts: list[str]
    source_lines: list[str]
    comparison_source_accounts: list[str]
    comparison_source_lines: list[str]
    dimensions: list[str]
    status: str
    reason: str | None = None


class FinancialVarianceResponse(BaseModel):
    organization_id: str
    comparison: VarianceComparison
    current_period_start: date
    current_period_end: date
    comparison_period_start: date | None
    comparison_period_end: date | None
    status: str
    metrics: list[FinancialVarianceMetric]
    reason: str | None = None
