from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.core.validation import validate_pagination
from app.db.session import get_db
from app.schemas.supplier_invoice import SupplierInvoiceCreate, SupplierInvoiceResponse, SupplierInvoiceUpdate
from app.services.supplier_invoice_service import SupplierInvoiceService

router = APIRouter()


def get_supplier_invoice_service(db: AsyncSession = Depends(get_db)) -> SupplierInvoiceService:
    return SupplierInvoiceService(db)


@router.post("/", response_model=SupplierInvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier_invoice(
    invoice_in: SupplierInvoiceCreate,
    tenant: CurrentTenant = Depends(require_permission("supplier_invoice:create")),
    service: SupplierInvoiceService = Depends(get_supplier_invoice_service),
):
    return await service.create(tenant.organization_id, tenant.user_id, invoice_in)


@router.get("/", response_model=list[SupplierInvoiceResponse])
async def read_supplier_invoices(
    skip: int = 0,
    limit: int = 100,
    status_value: str | None = None,
    supplier_id: str | None = None,
    tenant: CurrentTenant = Depends(require_permission("supplier_invoice:read")),
    service: SupplierInvoiceService = Depends(get_supplier_invoice_service),
):
    skip, limit = validate_pagination(skip, limit)
    return await service.list(
        tenant.organization_id,
        skip=skip,
        limit=limit,
        status_value=status_value,
        supplier_id=supplier_id,
    )


@router.get("/{invoice_id}", response_model=SupplierInvoiceResponse)
async def read_supplier_invoice(
    invoice_id: str,
    tenant: CurrentTenant = Depends(require_permission("supplier_invoice:read")),
    service: SupplierInvoiceService = Depends(get_supplier_invoice_service),
):
    return await service.get(tenant.organization_id, invoice_id)


@router.patch("/{invoice_id}", response_model=SupplierInvoiceResponse)
async def update_supplier_invoice(
    invoice_id: str,
    invoice_in: SupplierInvoiceUpdate,
    tenant: CurrentTenant = Depends(require_permission("supplier_invoice:update")),
    service: SupplierInvoiceService = Depends(get_supplier_invoice_service),
):
    return await service.update(tenant.organization_id, invoice_id, tenant.user_id, invoice_in)


@router.post("/{invoice_id}/approve", response_model=SupplierInvoiceResponse)
async def approve_supplier_invoice(
    invoice_id: str,
    tenant: CurrentTenant = Depends(require_permission("supplier_invoice:approve")),
    service: SupplierInvoiceService = Depends(get_supplier_invoice_service),
):
    return await service.approve(tenant.organization_id, invoice_id, tenant.user_id)


@router.post("/{invoice_id}/cancel", response_model=SupplierInvoiceResponse)
async def cancel_supplier_invoice(
    invoice_id: str,
    tenant: CurrentTenant = Depends(require_permission("supplier_invoice:cancel")),
    service: SupplierInvoiceService = Depends(get_supplier_invoice_service),
):
    return await service.cancel(tenant.organization_id, invoice_id, tenant.user_id)
