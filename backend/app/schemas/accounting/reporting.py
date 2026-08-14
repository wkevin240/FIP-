from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class FinancialStatementLine(BaseModel):
    account_id: str
    code: str
    name: str
    account_type: str
    balance: Decimal


class BalanceSheetResponse(BaseModel):
    as_of_date: date
    assets: list[FinancialStatementLine]
    liabilities: list[FinancialStatementLine]
    equity: list[FinancialStatementLine]
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    current_earnings: Decimal
    total_liabilities_and_equity: Decimal
    is_balanced: bool


class IncomeStatementResponse(BaseModel):
    start_date: date
    end_date: date
    revenues: list[FinancialStatementLine]
    expenses: list[FinancialStatementLine]
    total_revenue: Decimal
    total_expenses: Decimal
    net_income: Decimal


class TrialBalanceLine(BaseModel):
    account_id: str
    code: str
    name: str
    account_type: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


class TrialBalanceResponse(BaseModel):
    start_date: date | None
    end_date: date
    lines: list[TrialBalanceLine]
    total_debit: Decimal
    total_credit: Decimal
    is_balanced: bool


class GeneralLedgerLine(BaseModel):
    journal_entry_id: str
    entry_number: str
    entry_date: date
    line_number: int
    description: str
    debit: Decimal
    credit: Decimal
    running_balance: Decimal


class GeneralLedgerResponse(BaseModel):
    account_id: str
    start_date: date | None
    end_date: date | None
    skip: int
    limit: int
    lines: list[GeneralLedgerLine]


class ComparativeBalanceLine(BaseModel):
    account_id: str
    code: str
    name: str
    current_balance: Decimal
    previous_balance: Decimal
    year_to_date_balance: Decimal


class ComparativeBalanceResponse(BaseModel):
    current_start_date: date
    current_end_date: date
    previous_start_date: date
    previous_end_date: date
    lines: list[ComparativeBalanceLine]
