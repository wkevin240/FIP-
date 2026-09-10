from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class LedgerPostingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    journal_entry_id: str
    journal_entry_line_id: str
    fiscal_period_id: str
    posting_date: str
    line_number: int
    description: str | None
    debit: Decimal
    credit: Decimal


class TrialBalanceRow(BaseModel):
    account_id: str
    code: str
    name: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


class GeneralLedgerRow(BaseModel):
    id: str
    account_id: str
    journal_entry_id: str
    journal_entry_line_id: str
    fiscal_period_id: str
    posting_date: date
    line_number: int
    description: str | None
    debit: Decimal
    credit: Decimal
    balance: Decimal


class GeneralLedgerResponse(BaseModel):
    account_id: str
    fiscal_period_id: str | None
    start_date: date | None
    end_date: date | None
    opening_balance: Decimal
    closing_balance: Decimal
    movements: list[GeneralLedgerRow]


class PostingReconciliationResponse(BaseModel):
    organization_id: str
    fiscal_period_id: str | None
    start_date: date | None
    end_date: date | None
    expected_journal_lines: int
    actual_ledger_postings: int
    missing_postings: list[str]
    orphan_postings: list[str]
    mismatched_postings: list[str]
    is_reconciled: bool
