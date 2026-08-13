from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TreasuryBankAccountCreate(BaseModel):
    ledger_account_id: str
    bank_name: str = Field(..., min_length=1, max_length=128)
    account_name: str = Field(..., min_length=1, max_length=255)
    account_number: str = Field(..., min_length=1, max_length=64)
    currency: str = Field(default="XOF", min_length=3, max_length=3)
    opening_balance: Decimal = Field(
        default=Decimal("0.00"), max_digits=18, decimal_places=2
    )
    opening_date: date

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("Currency must be a three-letter alphabetic code")
        return normalized

    @field_validator("account_number")
    @classmethod
    def normalize_account_number(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Bank account number must not be blank")
        return normalized


class TreasuryBankAccountUpdate(BaseModel):
    bank_name: str | None = Field(default=None, min_length=1, max_length=128)
    account_name: str | None = Field(default=None, min_length=1, max_length=255)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("Currency must be a three-letter alphabetic code")
        return normalized


class TreasuryBankAccountResponse(BaseModel):
    id: str
    organization_id: str
    ledger_account_id: str
    bank_name: str
    account_name: str
    account_number: str
    currency: str
    opening_balance: Decimal
    opening_date: date
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TreasuryPositionResponse(BaseModel):
    treasury_bank_account_id: str
    ledger_account_id: str
    statement_balance: Decimal
    ledger_balance: Decimal
    reconciliation_gap: Decimal
    unreconciled_amount: Decimal
    unreconciled_transaction_count: int
