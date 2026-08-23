from decimal import Decimal

from pydantic import BaseModel


class ClosingReadinessResponse(BaseModel):
    organization_id: str
    fiscal_year_id: str
    fiscal_year_status: str
    fiscal_period_count: int
    open_period_count: int
    locked_period_count: int
    draft_journal_entry_count: int
    unresolved_banking_exception_count: int
    unclosed_statement_count: int
    missing_period_closing_count: int
    total_posted_debit: Decimal
    total_posted_credit: Decimal
    status: str
    blockers: list[str]
