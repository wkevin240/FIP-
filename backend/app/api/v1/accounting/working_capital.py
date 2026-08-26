from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.working_capital import WorkingCapitalResponse
from app.services.accounting.working_capital_service import WorkingCapitalService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> WorkingCapitalService:
    return WorkingCapitalService(session)


@router.get("/calculate", response_model=WorkingCapitalResponse)
async def calculate_working_capital(
    period_start: date = Query(...),
    as_of_date: date = Query(...),
    service: WorkingCapitalService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("working_capital:read")),
) -> WorkingCapitalResponse:
    return await service.calculate(tenant.organization_id, period_start, as_of_date)
