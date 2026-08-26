from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class KPIMetricResponse(BaseModel):
    code: str
    name: str
    label: str
    value: Decimal | None = None
    unit: str
    formula: str
    period_start: date
    period_end: date
    status: str
    reason: str | None = None
    source_modules: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    numerator: Decimal | None = None
    denominator: Decimal | None = None
    days: Decimal | None = None
    blockers: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class KPIResponse(BaseModel):
    organization_id: str
    fiscal_period_id: str | None
    period_start: date
    period_end: date
    status: str
    metrics: list[KPIMetricResponse]
    source_modules: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
