from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.vat import (
    VATCalculationRequest,
    VATCalculationResponse,
    VATDeclarationCreate,
    VATDeclarationResponse,
    VATEntryCreate,
    VATEntryResponse,
    VATRateCreate,
    VATRateResponse,
    VATRateUpdate,
    VATSummaryResponse,
)
from app.services.accounting.vat_declaration_service import VATDeclarationService
from app.services.accounting.vat_service import VATService
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> VATService:
    return VATService(session)


async def get_declaration_service(
    session: AsyncSession = Depends(get_db),
) -> VATDeclarationService:
    return VATDeclarationService(session)


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


@router.post(
    "/declarations",
    response_model=VATDeclarationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_vat_declaration(
    data: VATDeclarationCreate,
    service: VATDeclarationService = Depends(get_declaration_service),
    tenant: CurrentTenant = Depends(require_permission("vat:create")),
) -> VATDeclarationResponse:
    return await service.create(tenant.organization_id, tenant.user_id, data)


@router.get("/declarations", response_model=list[VATDeclarationResponse])
async def list_vat_declarations(
    service: VATDeclarationService = Depends(get_declaration_service),
    tenant: CurrentTenant = Depends(require_permission("vat:read")),
) -> list[VATDeclarationResponse]:
    return await service.list(tenant.organization_id)


@router.post(
    "/declarations/{declaration_id}/submit", response_model=VATDeclarationResponse
)
async def submit_vat_declaration(
    declaration_id: str,
    service: VATDeclarationService = Depends(get_declaration_service),
    tenant: CurrentTenant = Depends(require_permission("vat:update")),
) -> VATDeclarationResponse:
    return await service.submit(tenant.organization_id, declaration_id, tenant.user_id)


@router.get("/declarations/{declaration_id}/export.json", response_class=Response)
async def export_vat_declaration(
    declaration_id: str,
    service: VATDeclarationService = Depends(get_declaration_service),
    tenant: CurrentTenant = Depends(require_permission("vat:read")),
) -> Response:
    content = await service.export_json(
        tenant.organization_id, declaration_id, tenant.user_id
    )
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=vat-declaration.json"},
    )


@router.get("/declaration", response_model=VATSummaryResponse)
async def get_vat_declaration(
    start_date: date = Query(...),
    end_date: date = Query(...),
    service: VATService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("vat:read")),
) -> VATSummaryResponse:
    return await service.summary(tenant.organization_id, start_date, end_date)
