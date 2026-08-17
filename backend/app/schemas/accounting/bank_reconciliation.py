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


class AutomaticReconciliationRequest(BaseModel):
    bank_account_id: str
    date_window_days: int = Field(default=7, ge=0, le=90)


class AutomaticReconciliationSuggestion(BaseModel):
    bank_transaction_id: str
    external_id: str
    status: str
    candidate: ReconciliationCandidate | None = None
    reason: str | None = None


class AutomaticReconciliationPreviewResponse(BaseModel):
    bank_account_id: str
    date_window_days: int
    suggestions: list[AutomaticReconciliationSuggestion]


class AutomaticReconciliationApplyResponse(BaseModel):
    bank_account_id: str
    reconciliations: list[BankReconciliationResponse]
    suggestions: list[AutomaticReconciliationSuggestion]


class ReconciliationAllocationCreate(BaseModel):
    bank_transaction_id: str
    journal_entry_id: str
    matched_amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)


class ReconcileBankTransactionsRequest(BaseModel):
    bank_account_id: str
    allocations: list[ReconciliationAllocationCreate] = Field(..., min_length=1)


class BankReconciliationAllocationResponse(BaseModel):
    id: str
    organization_id: str
    batch_id: str
    bank_transaction_id: str
    journal_entry_id: str
    matched_amount: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BankReconciliationBatchResponse(BaseModel):
    id: str
    organization_id: str
    bank_account_id: str
    reconciled_by_user_id: str
    reconciled_at: datetime
    idempotency_key: str
    request_fingerprint: str
    match_method: str
    allocated_total: Decimal
    allocations: list[BankReconciliationAllocationResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
