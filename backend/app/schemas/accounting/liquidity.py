from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class LiquidityAccountPosition(BaseModel):
    treasury_bank_account_id: str
    account_name: str
    currency: str
    opening_balance: Decimal
    movement_total: Decimal
    closing_balance: Decimal
    inflows: Decimal
    outflows: Decimal
    transaction_count: int


class LiquidityPositionResponse(BaseModel):
    organization_id: str
    period_start: date
    as_of_date: date
    status: str
    available_cash: Decimal
    receivables_outstanding: Decimal
    payables_outstanding: Decimal
    net_liquidity: Decimal
    forecast_cash_status: str
    bank_accounts: list[LiquidityAccountPosition]
    blockers: list[str]

    model_config = ConfigDict(from_attributes=True)
