from app.api.dependencies import CurrentTenant, require_permission
from app.core.enums.invoicing import InvoiceStatus
from app.db.session import get_db
from app.schemas.invoicing.invoice import InvoiceCreate, InvoiceResponse, InvoiceUpdate
from app.services.invoicing.invoice_service import InvoiceService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> InvoiceService:
    return InvoiceService(session)


@router.post("/", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    data: InvoiceCreate,
    service: InvoiceService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("invoice:create")),
) -> InvoiceResponse:
    return await service.create_invoice(tenant.organization_id, data)


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
