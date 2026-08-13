from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.closing import (
    PeriodClosingResponse,
    PeriodClosingSummaryResponse,
)
from app.services.accounting.closing_service import ClosingService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> ClosingService:
    return ClosingService(session)


@router.get(
    "/periods/{fiscal_period_id}/preview", response_model=PeriodClosingSummaryResponse
)
async def preview_period_closing(
    fiscal_period_id: str,
    service: ClosingService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fiscal_period:read")),
) -> PeriodClosingSummaryResponse:
    return await service.preview_closing(tenant.organization_id, fiscal_period_id)


@router.get("/periods/{fiscal_period_id}", response_model=PeriodClosingResponse)
async def get_period_closing(
    fiscal_period_id: str,
    service: ClosingService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fiscal_period:read")),
) -> PeriodClosingResponse:
    return await service.get_closing(tenant.organization_id, fiscal_period_id)


@router.post(
    "/periods/{fiscal_period_id}",
    response_model=PeriodClosingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def close_period(
    fiscal_period_id: str,
    service: ClosingService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fiscal_period:close")),
) -> PeriodClosingResponse:
    return await service.close_period(
        tenant.organization_id, fiscal_period_id, tenant.user_id
    )
