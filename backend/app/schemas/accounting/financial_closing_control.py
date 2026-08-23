from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ClosingControlBlocker(BaseModel):
    code: str
    module: str
    severity: str
    description: str
    source_ids: list[str] = Field(default_factory=list)
    amount: Decimal | None = None


class ClosingControlCheck(BaseModel):
    control_code: str
    status: str
    formula: str | None = None
    actual: Decimal | int | str | None = None
    expected: Decimal | int | str | None = None
    difference: Decimal | None = None
    source_ids: list[str] = Field(default_factory=list)
    blockers: list[ClosingControlBlocker] = Field(default_factory=list)


class FinancialClosingControlResponse(BaseModel):
    organization_id: str
    fiscal_year_id: str
    fiscal_period_id: str
    period_start: date
    period_end: date
    status: str
    controls: list[ClosingControlCheck] = Field(default_factory=list)
    blockers: list[ClosingControlBlocker] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
