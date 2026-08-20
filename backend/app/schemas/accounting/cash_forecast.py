from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CashForecastLine(BaseModel):
    forecast_date: date
    actual_bank_movement: Decimal
    expected_ar_inflow: Decimal
    expected_ap_outflow: Decimal
    projected_net_movement: Decimal
    projected_closing_cash: Decimal


class CashForecastResponse(BaseModel):
    organization_id: str
    period_start: date
    period_end: date
    status: str
    opening_cash: Decimal
    actual_cash_movement: Decimal
    expected_ar_inflows: Decimal
    expected_ap_outflows: Decimal
    projected_closing_cash: Decimal
    forecast_source_status: str
    lines: list[CashForecastLine]
    blockers: list[str]

    model_config = ConfigDict(from_attributes=True)
