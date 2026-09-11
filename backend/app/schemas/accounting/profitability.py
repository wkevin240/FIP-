from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CalculationSourceResponse(BaseModel):
    record_type: str
    record_id: str
    module: str


class ProfitabilityResultResponse(BaseModel):
    code: str
    formula: str
    rule_version: str
    status: str
    value: Decimal | None
    reason: str | None
    sources: list[CalculationSourceResponse]


class ProfitabilityReportResponse(BaseModel):
    organization_id: str
    fiscal_period_id: str | None
    start_date: date
    end_date: date
    rule_version: str
    results: list[ProfitabilityResultResponse]


class ProfitabilityMappingCreateRequest(BaseModel):
    account_id: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=64)
    rule_version: str = Field(min_length=1, max_length=64)
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_effective_range(self):
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be on or after effective_from")
        return self


class ProfitabilityMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    account_id: str
    category: str
    rule_version: str
    effective_from: date
    effective_to: date | None
