from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.models.treasury.liquidity_alert import LiquidityAlertConfiguration
from app.schemas.accounting.cash_forecast import CashForecastResponse
from app.schemas.treasury.banking_control import BankingControlExceptionResponse
from app.schemas.treasury.liquidity_control import (
    LiquidityAlertConfigurationCreate,
    LiquidityAlertConfigurationResponse,
    LiquidityAlertsResponse,
    LiquidityControlResponse,
)
from app.services.treasury.liquidity_control_service import LiquidityControlService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def get_service(session: AsyncSession = Depends(get_db)) -> LiquidityControlService:
    return LiquidityControlService(session)


@router.get("", response_model=LiquidityControlResponse)
async def get_liquidity_control(
    as_of: date = Query(default_factory=date.today),
    horizon_end: date | None = Query(default=None),
    service: LiquidityControlService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("liquidity_control:read")),
) -> LiquidityControlResponse:
    end = horizon_end or as_of
    return await service.control(tenant.organization_id, tenant.user_id, as_of, end)


@router.get("/alerts", response_model=LiquidityAlertsResponse)
async def get_liquidity_alerts(
    as_of: date = Query(default_factory=date.today),
    horizon_end: date | None = Query(default=None),
    service: LiquidityControlService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("liquidity_control:read")),
) -> LiquidityAlertsResponse:
    return await service.alerts(tenant.organization_id, as_of, horizon_end or as_of)


@router.get("/forecast", response_model=CashForecastResponse)
async def get_liquidity_forecast(
    period_start: date = Query(default_factory=date.today),
    period_end: date | None = Query(default=None),
    service: LiquidityControlService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("liquidity_control:read")),
) -> CashForecastResponse:
    return await service.forecast(
        tenant.organization_id, period_start, period_end or period_start
    )


@router.get("/exceptions", response_model=list[BankingControlExceptionResponse])
async def get_liquidity_exceptions(
    as_of: date = Query(default_factory=date.today),
    service: LiquidityControlService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("liquidity_control:read")),
) -> list[BankingControlExceptionResponse]:
    return await service.list_exceptions(tenant.organization_id, as_of)


@router.get("/configurations", response_model=list[LiquidityAlertConfigurationResponse])
async def list_liquidity_configurations(
    service: LiquidityControlService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("liquidity_alert_config:read")),
) -> list[LiquidityAlertConfigurationResponse]:
    return list(
        await service.session.scalars(
            select(LiquidityAlertConfiguration)
            .where(
                LiquidityAlertConfiguration.organization_id == tenant.organization_id
            )
            .order_by(LiquidityAlertConfiguration.alert_code)
        )
    )


@router.put(
    "/configurations/{alert_code}",
    response_model=LiquidityAlertConfigurationResponse,
    status_code=status.HTTP_200_OK,
)
async def upsert_liquidity_configuration(
    alert_code: str,
    data: LiquidityAlertConfigurationCreate,
    service: LiquidityControlService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("liquidity_alert_config:write")),
) -> LiquidityAlertConfigurationResponse:
    if data.alert_code != alert_code:
        data.alert_code = alert_code
    return await service.upsert_config(tenant.organization_id, tenant.user_id, data)
