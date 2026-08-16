from typing import Annotated

from app.api.dependencies import CurrentTenant, require_permission
from app.core.enums.invoicing import InvoiceStatus
from app.db.session import get_db
from app.schemas.invoicing.accounting import (
    InvoiceAccountingPostingResponse,
    InvoiceAccountingProfileCreate,
    InvoiceAccountingProfileResponse,
)
from app.schemas.invoicing.invoice import InvoiceCreate, InvoiceResponse, InvoiceUpdate
from app.services.invoicing.invoice_accounting_service import InvoiceAccountingService
from app.services.invoicing.invoice_service import InvoiceService
from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> InvoiceService:
    return InvoiceService(session)


async def get_accounting_service(
    session: AsyncSession = Depends(get_db),
) -> InvoiceAccountingService:
    return InvoiceAccountingService(session)


@router.post("/", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    data: InvoiceCreate,
    service: InvoiceService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("invoice:create")),
) -> InvoiceResponse:
    return await service.create_invoice(tenant.organization_id, data)


@router.get("/accounting-profile", response_model=InvoiceAccountingProfileResponse)
async def get_invoice_accounting_profile(
    service: InvoiceAccountingService = Depends(get_accounting_service),
    tenant: CurrentTenant = Depends(require_permission("invoice:read")),
) -> InvoiceAccountingProfileResponse:
    return await service.get_profile(tenant.organization_id)


@router.post(
    "/accounting-profile",
    response_model=InvoiceAccountingProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def configure_invoice_accounting_profile(
    data: InvoiceAccountingProfileCreate,
    service: InvoiceAccountingService = Depends(get_accounting_service),
    tenant: CurrentTenant = Depends(require_permission("invoice:accounting:configure")),
) -> InvoiceAccountingProfileResponse:
    return await service.configure_profile(tenant.organization_id, tenant.user_id, data)


@router.get("/", response_model=list[InvoiceResponse])
async def list_invoices(
    status_value: InvoiceStatus | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: InvoiceService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("invoice:read")),
) -> list[InvoiceResponse]:
    return await service.list_invoices(
        tenant.organization_id, status_value, offset, limit
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    service: InvoiceService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("invoice:read")),
) -> InvoiceResponse:
    return await service.get_invoice(tenant.organization_id, invoice_id)


@router.patch("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: str,
    data: InvoiceUpdate,
    service: InvoiceService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("invoice:update")),
) -> InvoiceResponse:
    return await service.update_invoice(tenant.organization_id, invoice_id, data)


@router.post("/{invoice_id}/issue", response_model=InvoiceResponse)
async def issue_invoice(
    invoice_id: str,
    service: InvoiceService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("invoice:issue")),
) -> InvoiceResponse:
    return await service.issue_invoice(tenant.organization_id, invoice_id)


@router.post(
    "/{invoice_id}/post-accounting",
    response_model=InvoiceAccountingPostingResponse,
)
async def post_invoice_to_accounting(
    invoice_id: str,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
    service: InvoiceAccountingService = Depends(get_accounting_service),
    tenant: CurrentTenant = Depends(require_permission("invoice:post")),
) -> InvoiceAccountingPostingResponse:
    return await service.post_invoice(
        tenant.organization_id,
        tenant.user_id,
        invoice_id,
        idempotency_key,
    )
