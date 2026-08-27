from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.invoicing.payment_control import (
    PaymentAllocationCreate,
    PaymentAllocationResponse,
    PaymentControlResponse,
    PaymentReconciliationResponse,
    SupplierPaymentAllocationCreate,
    SupplierPaymentAllocationResponse,
    SupplierPaymentControlResponse,
)
from app.services.invoicing.payment_control_service import PaymentControlService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def get_service(session: AsyncSession = Depends(get_db)) -> PaymentControlService:
    return PaymentControlService(session)


@router.post("/customer/allocations", response_model=PaymentAllocationResponse)
async def allocate_customer_payment(
    data: PaymentAllocationCreate,
    service: PaymentControlService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payment_allocation:create")),
):
    return await service.allocate_customer(tenant.organization_id, tenant.user_id, data)


@router.post("/supplier/allocations", response_model=SupplierPaymentAllocationResponse)
async def allocate_supplier_payment(
    data: SupplierPaymentAllocationCreate,
    service: PaymentControlService = Depends(get_service),
    tenant: CurrentTenant = Depends(
        require_permission("supplier_payment_allocation:create")
    ),
):
    return await service.allocate_supplier(tenant.organization_id, tenant.user_id, data)


@router.get("/customer/{payment_id}/control", response_model=PaymentControlResponse)
async def customer_payment_control(
    payment_id: str,
    service: PaymentControlService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payment:read")),
):
    return await service.customer_control(tenant.organization_id, payment_id)


@router.get(
    "/supplier/{payment_id}/control", response_model=SupplierPaymentControlResponse
)
async def supplier_payment_control(
    payment_id: str,
    service: PaymentControlService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("supplier_payment:read")),
):
    return await service.supplier_control(tenant.organization_id, payment_id)


@router.get("/reconciliation", response_model=PaymentReconciliationResponse)
async def payment_reconciliation(
    as_of: date = Query(default_factory=date.today),
    service: PaymentControlService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payment_reconciliation:read")),
):
    return await service.reconciliation(tenant.organization_id, as_of)
