from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.vat import (
    VATCalculationRequest,
    VATCalculationResponse,
    VATEntryCreate,
    VATEntryResponse,
    VATRateCreate,
    VATRateResponse,
    VATRateUpdate,
    VATSummaryResponse,
)
from app.services.accounting.vat_service import VATService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> VATService:
    return VATService(session)


@router.post(
    "/rates", response_model=VATRateResponse, status_code=status.HTTP_201_CREATED
)
async def create_vat_rate(
    data: VATRateCreate,
    service: VATService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("vat:create")),
) -> VATRateResponse:
    return await service.create_rate(tenant.organization_id, data)


@router.patch("/rates/{rate_id}", response_model=VATRateResponse)
async def update_vat_rate(
    rate_id: str,
    data: VATRateUpdate,
    service: VATService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("vat:update")),
) -> VATRateResponse:
    return await service.update_rate(tenant.organization_id, rate_id, data)


@router.get("/rates", response_model=list[VATRateResponse])
async def list_vat_rates(
    service: VATService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("vat:read")),
) -> list[VATRateResponse]:
    return await service.list_rates(tenant.organization_id)


@router.post("/calculate", response_model=VATCalculationResponse)
async def calculate_vat(
    data: VATCalculationRequest,
    service: VATService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("vat:read")),
) -> VATCalculationResponse:
    return await service.calculate(tenant.organization_id, data)


@router.post(
    "/entries", response_model=VATEntryResponse, status_code=status.HTTP_201_CREATED
)
async def create_vat_entry(
    data: VATEntryCreate,
    service: VATService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("vat:create")),
) -> VATEntryResponse:
    return await service.create_entry(tenant.organization_id, data)


@router.get("/declaration", response_model=VATSummaryResponse)
async def get_vat_declaration(
    start_date: date = Query(...),
    end_date: date = Query(...),
    service: VATService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("vat:read")),
) -> VATSummaryResponse:
    return await service.summary(tenant.organization_id, start_date, end_date)
