from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.analytical import (
    AnalyticalActualResponse,
    AnalyticalAllocationCreate,
    AnalyticalAllocationResponse,
    AnalyticalDimensionCreate,
    AnalyticalDimensionResponse,
    AnalyticalDimensionValueCreate,
    AnalyticalDimensionValueResponse,
)
from app.services.accounting.analytical_service import AnalyticalService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> AnalyticalService:
    return AnalyticalService(session)


@router.post(
    "/dimensions",
    response_model=AnalyticalDimensionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dimension(
    data: AnalyticalDimensionCreate,
    service: AnalyticalService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("analytical_dimension:create")),
) -> AnalyticalDimensionResponse:
    return await service.create_dimension(tenant.organization_id, tenant.user_id, data)


@router.post(
    "/dimensions/{dimension_id}/values",
    response_model=AnalyticalDimensionValueResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dimension_value(
    dimension_id: str,
    data: AnalyticalDimensionValueCreate,
    service: AnalyticalService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("analytical_value:create")),
) -> AnalyticalDimensionValueResponse:
    return await service.create_value(
        tenant.organization_id, tenant.user_id, dimension_id, data
    )


@router.post(
    "/allocations",
    response_model=AnalyticalAllocationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def allocate_posted_line(
    data: AnalyticalAllocationCreate,
    service: AnalyticalService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("analytical_allocation:create")),
) -> AnalyticalAllocationResponse:
    return await service.allocate_posted_line(
        tenant.organization_id, tenant.user_id, data
    )


@router.get("/actuals", response_model=list[AnalyticalActualResponse])
async def analytical_actuals(
    dimension_id: str | None = Query(default=None),
    dimension_value_id: str | None = Query(default=None),
    fiscal_period_id: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    service: AnalyticalService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("analytical_report:read")),
) -> list[AnalyticalActualResponse]:
    return await service.actuals(
        tenant.organization_id,
        dimension_id=dimension_id,
        dimension_value_id=dimension_value_id,
        fiscal_period_id=fiscal_period_id,
        account_id=account_id,
    )
