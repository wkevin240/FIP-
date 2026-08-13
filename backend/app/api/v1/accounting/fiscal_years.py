from fastapi import APIRouter, Depends, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.fiscal_year import FiscalYearCreate, FiscalYearResponse
from app.services.accounting.fiscal_year_service import FiscalYearService

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> FiscalYearService:
    return FiscalYearService(db)


@router.post("/", response_model=FiscalYearResponse, status_code=status.HTTP_201_CREATED)
async def create(
    data: FiscalYearCreate,
    service: FiscalYearService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fiscal_year:create")),
):
    return await service.create_fiscal_year(tenant.organization_id, data)


@router.get("/", response_model=List[FiscalYearResponse])
async def get_all(
    service: FiscalYearService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fiscal_year:read")),
):
    return await service.get_all(tenant.organization_id)


@router.get("/{id}", response_model=FiscalYearResponse)
async def get_one(
    id: str,
    service: FiscalYearService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("fiscal_year:read")),
):
    return await service.get_by_id(tenant.organization_id, id)
