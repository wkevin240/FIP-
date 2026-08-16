from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.fiscal_year import FiscalYearCreate, FiscalYearResponse
from app.schemas.accounting.fiscal_year_closing import (
    FiscalYearClosingPreviewResponse,
    FiscalYearClosingResponse,
)
from app.services.accounting.fiscal_year_closing_service import FiscalYearClosingService
from app.services.accounting.fiscal_year_service import FiscalYearService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> FiscalYearService:
    return FiscalYearService(db)


def get_closing_service(
    db: AsyncSession = Depends(get_db),
) -> FiscalYearClosingService:
    return FiscalYearClosingService(db)


@router.post(
    "/", response_model=FiscalYearResponse, status_code=status.HTTP_201_CREATED
)
async def create(
    data: FiscalYearCreate,
    service: FiscalYearService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fiscal_year:create")),
):
    return await service.create_fiscal_year(tenant.organization_id, data)


@router.get("/", response_model=list[FiscalYearResponse])
async def get_all(
    service: FiscalYearService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fiscal_year:read")),
):
    return await service.get_all(tenant.organization_id)


@router.get("/{id}/closing-preview", response_model=FiscalYearClosingPreviewResponse)
async def preview_closing(
    id: str,
    service: FiscalYearClosingService = Depends(get_closing_service),
    tenant: CurrentTenant = Depends(require_permission("fiscal_year:read")),
) -> FiscalYearClosingPreviewResponse:
    return await service.preview(tenant.organization_id, id)


@router.post("/{id}/close", response_model=FiscalYearClosingResponse)
async def close_fiscal_year(
    id: str,
    service: FiscalYearClosingService = Depends(get_closing_service),
    tenant: CurrentTenant = Depends(require_permission("fiscal_year:update")),
) -> FiscalYearClosingResponse:
    return await service.close(tenant.organization_id, id, tenant.user_id)


@router.get("/{id}", response_model=FiscalYearResponse)
async def get_one(
    id: str,
    service: FiscalYearService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fiscal_year:read")),
):
    return await service.get_by_id(tenant.organization_id, id)
