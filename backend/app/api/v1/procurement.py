from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.procurement import (
    AccountingPostingResponse,
    ProcurementAccountingProfileCreate,
    ProcurementAccountingProfileResponse,
    PurchaseInvoiceCreate,
    PurchaseInvoiceResponse,
    SupplierCreate,
    SupplierPaymentCreate,
    SupplierPaymentResponse,
    SupplierResponse,
)
from app.services.procurement_service import ProcurementService

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> ProcurementService:
    return ProcurementService(session)


@router.post(
    "/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED
)
async def create_supplier(
    data: SupplierCreate,
    service: ProcurementService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("supplier:create")),
):
    return await service.create_supplier(tenant.organization_id, tenant.user_id, data)


@router.post(
    "/accounting-profile",
    response_model=ProcurementAccountingProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def configure_profile(
    data: ProcurementAccountingProfileCreate,
    service: ProcurementService = Depends(get_service),
    tenant: CurrentTenant = Depends(
        require_permission("procurement:accounting:configure")
    ),
):
    return await service.configure_profile(tenant.organization_id, tenant.user_id, data)


@router.post(
    "/invoices",
    response_model=PurchaseInvoiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invoice(
    data: PurchaseInvoiceCreate,
    service: ProcurementService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("purchase_invoice:create")),
):
    return await service.create_invoice(tenant.organization_id, tenant.user_id, data)


@router.post("/invoices/{invoice_id}/validate", response_model=PurchaseInvoiceResponse)
async def validate_invoice(
    invoice_id: str,
    service: ProcurementService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("purchase_invoice:validate")),
):
    return await service.validate_invoice(
        tenant.organization_id, tenant.user_id, invoice_id
    )


@router.post(
    "/invoices/{invoice_id}/post-accounting", response_model=AccountingPostingResponse
)
async def post_invoice(
    invoice_id: str,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
    service: ProcurementService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("purchase_invoice:post")),
):
    return await service.post_invoice(
        tenant.organization_id, tenant.user_id, invoice_id, idempotency_key
    )


@router.post(
    "/payments",
    response_model=SupplierPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment(
    data: SupplierPaymentCreate,
    service: ProcurementService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("supplier_payment:create")),
):
    return await service.create_payment(tenant.organization_id, tenant.user_id, data)


@router.post(
    "/payments/{payment_id}/post-accounting", response_model=AccountingPostingResponse
)
async def post_payment(
    payment_id: str,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
    service: ProcurementService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("supplier_payment:post")),
):
    return await service.post_payment(
        tenant.organization_id, tenant.user_id, payment_id, idempotency_key
    )
