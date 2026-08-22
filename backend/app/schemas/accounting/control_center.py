from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class FinancialControlCenterResponse(BaseModel):
    organization_id: str
    as_of_date: date
    status: str
    posted_debit_total: Decimal
    posted_credit_total: Decimal
    draft_entry_count: int
    open_period_count: int
    unresolved_banking_exception_count: int
    unreconciled_bank_transaction_count: int
    blockers: list[str]

    model_config = ConfigDict(from_attributes=True)
