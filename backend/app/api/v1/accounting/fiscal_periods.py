from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.fiscal_period import FiscalPeriodCreate, FiscalPeriodResponse
from app.services.accounting.fiscal_period_service import FiscalPeriodService

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> FiscalPeriodService:
    return FiscalPeriodService(db)


@router.post("/", response_model=FiscalPeriodResponse, status_code=status.HTTP_201_CREATED)
async def create(
    data: FiscalPeriodCreate,
    tenant: CurrentTenant = Depends(require_permission("fiscal_period:create")),
    service: FiscalPeriodService = Depends(get_service),
):
    return await service.create_fiscal_period(tenant.organization_id, data)


@router.get("/by-year/{year_id}", response_model=list[FiscalPeriodResponse])
async def get_by_year(
    year_id: str,
    tenant: CurrentTenant = Depends(require_permission("fiscal_period:read")),
    service: FiscalPeriodService = Depends(get_service),
):
    return await service.get_by_fiscal_year(tenant.organization_id, year_id)


@router.post("/{period_id}/close", response_model=FiscalPeriodResponse)
async def close(
    period_id: str,
    tenant: CurrentTenant = Depends(require_permission("fiscal_period:close")),
    service: FiscalPeriodService = Depends(get_service),
):
    return await service.close_period(tenant.organization_id, period_id)
