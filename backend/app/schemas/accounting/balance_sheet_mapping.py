from datetime import date

from pydantic import BaseModel, Field, model_validator


class BalanceSheetMappingCreateRequest(BaseModel):
    account_id: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=16)
    rule_version: str = Field(min_length=1, max_length=64)
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_effective_range(self):
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be on or after effective_from")
        return self


class BalanceSheetMappingResponse(BaseModel):
    id: str
    organization_id: str
    account_id: str
    category: str
    rule_version: str
    effective_from: date
    effective_to: date | None
