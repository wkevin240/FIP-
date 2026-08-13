from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BankTransactionCreate(BaseModel):
    bank_account_id: str
    transaction_date: date
    value_date: date | None = None
    amount: Decimal = Field(..., max_digits=18, decimal_places=2)
    description: str = Field(..., min_length=1, max_length=500)
    reference: str | None = Field(None, max_length=100)
    external_id: str = Field(..., min_length=1, max_length=100)


class BankTransactionResponse(BankTransactionCreate):
    id: str
    organization_id: str
    reconciled_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReconciliationCandidate(BaseModel):
    journal_entry_id: str
    entry_number: str
    entry_date: date
    description: str
    ledger_amount: Decimal
    amount_difference: Decimal
    date_difference_days: int


class ReconcileBankTransactionRequest(BaseModel):
    journal_entry_id: str


class BankReconciliationResponse(BaseModel):
    id: str
    organization_id: str
    bank_transaction_id: str
    journal_entry_id: str
    reconciled_by_user_id: str
    reconciled_at: datetime
    matched_amount: Decimal
    match_method: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
