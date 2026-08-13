from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.fixed_assets.asset import (
    FixedAssetAcquireRequest,
    FixedAssetCommissionRequest,
    FixedAssetComponentCreate,
    FixedAssetComponentResponse,
    FixedAssetCreate,
    FixedAssetResponse,
    FixedAssetUpdate,
)
from app.services.fixed_assets.asset_service import FixedAssetService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> FixedAssetService:
    return FixedAssetService(session)


@router.post(
    "/", response_model=FixedAssetResponse, status_code=status.HTTP_201_CREATED
)
async def create_asset(
    data: FixedAssetCreate,
    service: FixedAssetService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fixed_asset:create")),
) -> FixedAssetResponse:
    return await service.create_asset(tenant.organization_id, tenant.user_id, data)


@router.get("/", response_model=list[FixedAssetResponse])
async def list_assets(
    status_value: str | None = Query(None, alias="status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: FixedAssetService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fixed_asset:read")),
) -> list[FixedAssetResponse]:
    return await service.list_assets(
        tenant.organization_id, status_value, offset, limit
    )


@router.get("/{asset_id}", response_model=FixedAssetResponse)
async def get_asset(
    asset_id: str,
    service: FixedAssetService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fixed_asset:read")),
) -> FixedAssetResponse:
    return await service.get_asset(tenant.organization_id, asset_id)


@router.patch("/{asset_id}", response_model=FixedAssetResponse)
async def update_asset(
    asset_id: str,
    data: FixedAssetUpdate,
    service: FixedAssetService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fixed_asset:update")),
) -> FixedAssetResponse:
    return await service.update_asset(
        tenant.organization_id, tenant.user_id, asset_id, data
    )


@router.post(
    "/{asset_id}/components",
    response_model=FixedAssetComponentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_component(
    asset_id: str,
    data: FixedAssetComponentCreate,
    service: FixedAssetService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fixed_asset:update")),
) -> FixedAssetComponentResponse:
    return await service.create_component(
        tenant.organization_id, tenant.user_id, asset_id, data
    )


@router.post("/{asset_id}/acquire", response_model=FixedAssetResponse)
async def acquire_asset(
    asset_id: str,
    data: FixedAssetAcquireRequest,
    service: FixedAssetService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fixed_asset:acquire")),
) -> FixedAssetResponse:
    return await service.acquire_asset(
        tenant.organization_id, tenant.user_id, asset_id, data
    )


@router.post("/{asset_id}/commission", response_model=FixedAssetResponse)
async def commission_asset(
    asset_id: str,
    data: FixedAssetCommissionRequest,
    service: FixedAssetService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fixed_asset:commission")),
) -> FixedAssetResponse:
    return await service.commission_asset(
        tenant.organization_id, tenant.user_id, asset_id, data
    )
