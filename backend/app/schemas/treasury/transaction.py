from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TreasuryBankTransactionCreate(BaseModel):
    treasury_bank_account_id: str
    transaction_date: date
    value_date: date | None = None
    amount: Decimal = Field(..., max_digits=18, decimal_places=2)
    description: str = Field(..., min_length=1, max_length=500)
    reference: str | None = Field(default=None, max_length=100)
    external_id: str = Field(..., min_length=1, max_length=100)

    @field_validator("amount")
    @classmethod
    def validate_non_zero_amount(cls, value: Decimal) -> Decimal:
        if value == 0:
            raise ValueError("Bank transaction amount must not be zero")
        return value


class TreasuryBankTransactionResponse(BaseModel):
    id: str
    organization_id: str
    bank_account_id: str
    transaction_date: date
    value_date: date | None
    amount: Decimal
    description: str
    reference: str | None
    external_id: str
    reconciled_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
