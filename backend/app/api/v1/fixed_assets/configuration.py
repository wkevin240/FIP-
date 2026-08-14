from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.fixed_assets.configuration import (
    FixedAssetAccountingProfileCreate,
    FixedAssetAccountingProfileResponse,
    FixedAssetCategoryCreate,
    FixedAssetCategoryResponse,
)
from app.services.fixed_assets.configuration_service import (
    FixedAssetConfigurationService,
)
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> FixedAssetConfigurationService:
    return FixedAssetConfigurationService(session)


@router.post(
    "/accounting-profiles",
    response_model=FixedAssetAccountingProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    data: FixedAssetAccountingProfileCreate,
    service: FixedAssetConfigurationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fixed_asset_category:create")),
) -> FixedAssetAccountingProfileResponse:
    return await service.create_profile(tenant.organization_id, tenant.user_id, data)


@router.post(
    "/categories",
    response_model=FixedAssetCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    data: FixedAssetCategoryCreate,
    service: FixedAssetConfigurationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fixed_asset_category:create")),
) -> FixedAssetCategoryResponse:
    return await service.create_category(tenant.organization_id, tenant.user_id, data)


@router.get("/categories", response_model=list[FixedAssetCategoryResponse])
async def list_categories(
    active_only: bool = Query(False),
    service: FixedAssetConfigurationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fixed_asset_category:read")),
) -> list[FixedAssetCategoryResponse]:
    return await service.list_categories(tenant.organization_id, active_only)
