from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BudgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    fiscal_year_id: str = Field(min_length=1)


class BudgetLineCreate(BaseModel):
    fiscal_period_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    amount: Decimal
    dimension_value_id: str | None = None


class BudgetLineResponse(BudgetLineCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str


class BudgetResponse(BudgetCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    status: str
    approved_at: datetime | None
    approved_by_user_id: str | None


class BudgetVarianceResponse(BaseModel):
    budget_id: str
    fiscal_period_id: str
    account_id: str
    budget_amount: Decimal
    actual_amount: Decimal
    variance_amount: Decimal

    @model_validator(mode="after")
    def verify_variance(self) -> "BudgetVarianceResponse":
        if self.variance_amount != self.budget_amount - self.actual_amount:
            raise ValueError("variance_amount must equal budget_amount - actual_amount")
        return self
