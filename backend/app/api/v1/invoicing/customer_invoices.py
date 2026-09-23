from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.core.validation import validate_pagination
from app.db.session import get_db
from app.models.customer_invoice import CustomerInvoiceStatus
from app.schemas.invoicing.customer_invoice import CustomerInvoiceCreate, CustomerInvoiceResponse, CustomerInvoiceUpdate
from app.services.invoicing.customer_invoice_service import CustomerInvoiceService

router = APIRouter()


def get_customer_invoice_service(db: AsyncSession = Depends(get_db)) -> CustomerInvoiceService:
    return CustomerInvoiceService(db)


@router.post("/", response_model=CustomerInvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_customer_invoice(
    invoice_in: CustomerInvoiceCreate,
    tenant: CurrentTenant = Depends(require_permission("customer_invoice:create")),
    service: CustomerInvoiceService = Depends(get_customer_invoice_service),
):
    return await service.create(tenant.organization_id, tenant.user_id, invoice_in)


@router.get("/", response_model=list[CustomerInvoiceResponse])
async def read_customer_invoices(
    skip: int = 0,
    limit: int = 100,
    customer_id: str | None = None,
    invoice_status: CustomerInvoiceStatus | None = None,
    due_before: date | None = None,
    tenant: CurrentTenant = Depends(require_permission("customer_invoice:read")),
    service: CustomerInvoiceService = Depends(get_customer_invoice_service),
):
    skip, limit = validate_pagination(skip, limit)
    return await service.list(
        tenant.organization_id,
        skip=skip,
        limit=limit,
        customer_id=customer_id,
        invoice_status=invoice_status,
        due_before=due_before,
    )


@router.get("/{invoice_id}", response_model=CustomerInvoiceResponse)
async def read_customer_invoice(
    invoice_id: str,
    tenant: CurrentTenant = Depends(require_permission("customer_invoice:read")),
    service: CustomerInvoiceService = Depends(get_customer_invoice_service),
):
    return await service.get(tenant.organization_id, invoice_id)


@router.patch("/{invoice_id}", response_model=CustomerInvoiceResponse)
async def update_customer_invoice(
    invoice_id: str,
    invoice_in: CustomerInvoiceUpdate,
    tenant: CurrentTenant = Depends(require_permission("customer_invoice:update")),
    service: CustomerInvoiceService = Depends(get_customer_invoice_service),
):
    return await service.update(tenant.organization_id, invoice_id, tenant.user_id, invoice_in)


@router.post("/{invoice_id}/issue", response_model=CustomerInvoiceResponse)
async def issue_customer_invoice(
    invoice_id: str,
    tenant: CurrentTenant = Depends(require_permission("customer_invoice:issue")),
    service: CustomerInvoiceService = Depends(get_customer_invoice_service),
):
    return await service.issue(tenant.organization_id, invoice_id, tenant.user_id)

