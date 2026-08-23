from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.invoicing.payment import (
    PaymentAllocationCreate,
    PaymentAllocationResponse,
    PaymentCreate,
    PaymentResponse,
)
from app.schemas.invoicing.settlement_accounting import (
    PaymentPostingCreate,
    PaymentPostingResponse,
)
from app.services.invoicing.payment_service import PaymentService
from app.services.invoicing.receivable_service import ReceivableService
from app.services.invoicing.settlement_accounting_service import (
    SettlementAccountingService,
)
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> PaymentService:
    return PaymentService(session)


async def get_receivable_service(
    session: AsyncSession = Depends(get_db),
) -> ReceivableService:
    return ReceivableService(session)


async def get_accounting_service(
    session: AsyncSession = Depends(get_db),
) -> SettlementAccountingService:
    return SettlementAccountingService(session)


@router.post("/{payment_id}/post-accounting", response_model=PaymentPostingResponse)
async def post_payment_to_accounting(
    payment_id: str,
    data: PaymentPostingCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1),
    service: SettlementAccountingService = Depends(get_accounting_service),
    tenant: CurrentTenant = Depends(require_permission("payment:post")),
) -> PaymentPostingResponse:
    return await service.post_payment(
        tenant.organization_id, tenant.user_id, payment_id, idempotency_key, data
    )


@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    data: PaymentCreate,
    service: PaymentService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payment:create")),
) -> PaymentResponse:
    return await service.create_payment(tenant.organization_id, data, tenant.user_id)


@router.post("/{payment_id}/allocations", response_model=PaymentAllocationResponse)
async def allocate_payment(
    payment_id: str,
    data: PaymentAllocationCreate,
    service: ReceivableService = Depends(get_receivable_service),
    tenant: CurrentTenant = Depends(require_permission("payment:allocate")),
) -> PaymentAllocationResponse:
    return await service.allocate_payment(
        tenant.organization_id, tenant.user_id, payment_id, data
    )


@router.get("/invoices/{invoice_id}", response_model=list[PaymentResponse])
async def list_payments(
    invoice_id: str,
    service: PaymentService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payment:read")),
) -> list[PaymentResponse]:
    return await service.list_payments(tenant.organization_id, invoice_id)
