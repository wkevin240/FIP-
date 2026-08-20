from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.forecast import ForecastResponse
from app.services.accounting.forecast_service import ForecastService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> ForecastService:
    return ForecastService(session)


@router.get("", response_model=ForecastResponse)
async def calculate_forecast(
    budget_id: str = Query(min_length=1),
    scenario_id: str = Query(min_length=1),
    service: ForecastService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("forecast:read")),
) -> ForecastResponse:
    return await service.calculate(tenant.organization_id, budget_id, scenario_id)
