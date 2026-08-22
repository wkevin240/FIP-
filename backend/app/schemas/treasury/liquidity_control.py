from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LiquidityAlertConfigurationCreate(BaseModel):
    alert_code: str
    enabled: bool = True
    threshold_amount: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    effective_from: date | None = None
    effective_to: date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class LiquidityAlertConfigurationResponse(LiquidityAlertConfigurationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str


class LiquidityAlert(BaseModel):
    code: str
    severity: str
    status: str
    explanation: str
    source_data: list[str]
    as_of: date
    horizon_end: date
    affected_amount: Decimal | None = None


class LiquidityControlResponse(BaseModel):
    organization_id: str
    as_of: date
    horizon_end: date
    status: str
    current_cash_position: Decimal
    available_cash: Decimal
    ar_outstanding: Decimal
    ap_outstanding: Decimal
    net_liquidity: Decimal
    forecast_cash_position: Decimal | None
    liquidity_gap: Decimal | None
    unresolved_banking_exposure: Decimal
    unallocated_customer_payments: Decimal | None
    unallocated_supplier_payments: Decimal | None
    current_period_blockers: list[str]
    sources: dict[str, str]
    alerts: list[LiquidityAlert]


class LiquidityAlertsResponse(BaseModel):
    organization_id: str
    as_of: date
    horizon_end: date
    status: str
    alerts: list[LiquidityAlert]
    blockers: list[str]
