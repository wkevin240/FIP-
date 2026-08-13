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
