from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.fixed_assets.depreciation import (
    DepreciationPlanResponse,
    DepreciationScheduleLineResponse,
)
from app.services.fixed_assets.depreciation_service import DepreciationService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> DepreciationService:
    return DepreciationService(session)


@router.get("/assets/{asset_id}/plans", response_model=list[DepreciationPlanResponse])
async def list_plans(
    asset_id: str,
    service: DepreciationService = Depends(get_service),
    tenant: CurrentTenant = Depends(
        require_permission("fixed_asset_depreciation:read")
    ),
) -> list[DepreciationPlanResponse]:
    return await service.list_plans(tenant.organization_id, asset_id)


@router.get(
    "/plans/{plan_id}/schedule", response_model=list[DepreciationScheduleLineResponse]
)
async def list_schedule(
    plan_id: str,
    service: DepreciationService = Depends(get_service),
    tenant: CurrentTenant = Depends(
        require_permission("fixed_asset_depreciation:read")
    ),
) -> list[DepreciationScheduleLineResponse]:
    return await service.list_schedule(tenant.organization_id, plan_id)


@router.post(
    "/schedule-lines/{schedule_line_id}/post",
    response_model=DepreciationScheduleLineResponse,
)
async def post_schedule_line(
    schedule_line_id: str,
    fiscal_period_id: str = Query(...),
    service: DepreciationService = Depends(get_service),
    tenant: CurrentTenant = Depends(
        require_permission("fixed_asset_depreciation:post")
    ),
) -> DepreciationScheduleLineResponse:
    return await service.post_schedule_line(
        tenant.organization_id, tenant.user_id, schedule_line_id, fiscal_period_id
    )
