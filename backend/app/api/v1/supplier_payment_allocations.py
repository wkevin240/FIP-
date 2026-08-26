from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.procurement import (
    SupplierPaymentAllocationCreate,
    SupplierPaymentAllocationResponse,
    SupplierPaymentReconciliationResponse,
)
from app.services.supplier_payment_allocation_service import (
    SupplierPaymentAllocationService,
)

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> SupplierPaymentAllocationService:
    return SupplierPaymentAllocationService(session)


@router.post(
    "/payments/{payment_id}/allocations",
    response_model=SupplierPaymentAllocationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def allocate_payment(
    payment_id: str,
    data: SupplierPaymentAllocationCreate,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
    service: SupplierPaymentAllocationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("supplier_payment:allocate")),
):
    return await service.allocate(
        tenant.organization_id,
        tenant.user_id,
        payment_id,
        data,
        idempotency_key,
    )


@router.delete(
    "/allocations/{allocation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deallocate_payment(
    allocation_id: str,
    service: SupplierPaymentAllocationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("supplier_payment:reallocate")),
):
    await service.deallocate(tenant.organization_id, tenant.user_id, allocation_id)


@router.get(
    "/payments/{payment_id}/reconciliation",
    response_model=SupplierPaymentReconciliationResponse,
)
async def payment_reconciliation(
    payment_id: str,
    service: SupplierPaymentAllocationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("supplier_payment:read")),
):
    return await service.reconcile(tenant.organization_id, payment_id)
