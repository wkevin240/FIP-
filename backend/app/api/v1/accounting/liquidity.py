from datetime import date
from typing import Annotated

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.liquidity import LiquidityPositionResponse
from app.services.accounting.liquidity_service import LiquidityService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> LiquidityService:
    return LiquidityService(session)


@router.get("/position", response_model=LiquidityPositionResponse)
async def get_liquidity_position(
    period_start: Annotated[date, Query()],
    as_of_date: Annotated[date, Query()],
    service: LiquidityService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_position:read")),
):
    return await service.calculate(tenant.organization_id, period_start, as_of_date)
