from datetime import date
from typing import Annotated

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.cash_forecast import CashForecastResponse
from app.services.accounting.cash_forecast_service import CashForecastService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> CashForecastService:
    return CashForecastService(session)


@router.get("/projection", response_model=CashForecastResponse)
async def get_cash_forecast(
    period_start: Annotated[date, Query()],
    period_end: Annotated[date, Query()],
    service: CashForecastService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("cash_forecast:read")),
):
    return await service.calculate(tenant.organization_id, period_start, period_end)
