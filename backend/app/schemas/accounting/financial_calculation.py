from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

CATEGORIES = ("REVENUE", "COGS", "OPERATING_EXPENSE", "OTHER_INCOME", "OTHER_EXPENSE")


class ProfitabilityMappingCreate(BaseModel):
    account_id: str
    category: str = Field(..., min_length=1, max_length=32)


class ProfitabilityMappingResponse(ProfitabilityMappingCreate):
    id: str
    organization_id: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class ProfitabilityMetric(BaseModel):
    code: str
    value: Decimal | None
    formula: str
    status: str
    period_start: date
    period_end: date
    account_ids: list[str]
    journal_entry_line_ids: list[str]
    dimensions: list[str]
    reason: str | None = None


class ProfitabilityResponse(BaseModel):
    organization_id: str
    period_start: date
    period_end: date
    dimension_id: str | None = None
    dimension_value_id: str | None = None
    status: str
    metrics: list[ProfitabilityMetric]
    source_line_count: int
    ledger_is_balanced: bool
    ledger_balance_difference: Decimal
