from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.fixed_assets.disposal import (
    FixedAssetDisposalCreate,
    FixedAssetDisposalResponse,
)
from app.services.fixed_assets.disposal_service import FixedAssetDisposalService
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> FixedAssetDisposalService:
    return FixedAssetDisposalService(session)


@router.post("/assets/{asset_id}/dispose", response_model=FixedAssetDisposalResponse)
async def dispose_asset(
    asset_id: str,
    data: FixedAssetDisposalCreate,
    service: FixedAssetDisposalService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fixed_asset_disposal:create")),
) -> FixedAssetDisposalResponse:
    return await service.dispose(tenant.organization_id, tenant.user_id, asset_id, data)
