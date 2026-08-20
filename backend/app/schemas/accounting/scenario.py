from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScenarioCreate(BaseModel):
    fiscal_year_id: str = Field(min_length=1)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class ScenarioAssumptionCreate(BaseModel):
    fiscal_period_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    dimension_value_id: str | None = None
    amount: Decimal
    rationale: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_amount(self) -> "ScenarioAssumptionCreate":
        if self.amount == 0:
            raise ValueError("Scenario assumption amount must not be zero")
        return self


class ScenarioAssumptionResponse(ScenarioAssumptionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    scenario_id: str


class ScenarioResponse(ScenarioCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    status: str
    approved_at: datetime | None
    approved_by_user_id: str | None


class ScenarioStatusResponse(BaseModel):
    scenario_id: str
    status: str
    assumption_count: int
    ready: bool
