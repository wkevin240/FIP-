from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnalyticalDimensionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)


class AnalyticalDimensionResponse(AnalyticalDimensionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    is_active: str


class AnalyticalDimensionValueCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)


class AnalyticalDimensionValueResponse(AnalyticalDimensionValueCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    dimension_id: str
    is_active: str


class AnalyticalAllocationCreate(BaseModel):
    journal_entry_line_id: str = Field(min_length=1)
    dimension_id: str = Field(min_length=1)
    dimension_value_id: str = Field(min_length=1)
    amount: Decimal
    idempotency_key: str = Field(min_length=1, max_length=128)


class AnalyticalAllocationResponse(AnalyticalAllocationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str


class AnalyticalActualResponse(BaseModel):
    dimension_id: str
    dimension_value_id: str
    account_id: str
    fiscal_period_id: str
    allocated_amount: Decimal
    ledger_amount: Decimal
    variance_to_ledger: Decimal
    budget_amount: Decimal | None = None
    budget_variance: Decimal | None = None

    @model_validator(mode="after")
    def verify_reconciliation(self) -> "AnalyticalActualResponse":
        if self.variance_to_ledger != self.allocated_amount - self.ledger_amount:
            raise ValueError(
                "variance_to_ledger must equal allocated_amount - ledger_amount"
            )
        return self
