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
