from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TreasuryReconciliationCandidate(BaseModel):
    journal_entry_id: str
    entry_number: str
    entry_date: date
    description: str
    ledger_amount: Decimal
    amount_difference: Decimal
    date_difference_days: int


class TreasuryReconcileRequest(BaseModel):
    journal_entry_id: str


class TreasuryReconciliationResponse(BaseModel):
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


class AccountingTreasuryReconciliationResponse(BaseModel):
    organization_id: str
    as_of: date
    status: str
    bank_transactions: int
    payments: int
    matched_payments: int
    unmatched_payments: int
    missing_postings: int
    unresolved_bank_transactions: int
    amount_differences: Decimal
    blockers: list[str]
