from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.invoicing.payment import PaymentCreate, PaymentResponse
from app.services.invoicing.payment_service import PaymentService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> PaymentService:
    return PaymentService(session)


@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    data: PaymentCreate,
    service: PaymentService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payment:create")),
) -> PaymentResponse:
    return await service.create_payment(tenant.organization_id, data)


@router.get("/invoices/{invoice_id}", response_model=list[PaymentResponse])
async def list_payments(
    invoice_id: str,
    service: PaymentService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payment:read")),
) -> list[PaymentResponse]:
    return await service.list_payments(tenant.organization_id, invoice_id)
