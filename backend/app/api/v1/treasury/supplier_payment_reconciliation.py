from typing import Annotated

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.treasury.supplier_payment_reconciliation import (
    SupplierPaymentReconciliationPreview,
)
from app.services.treasury.supplier_payment_reconciliation_service import (
    SupplierPaymentReconciliationService,
)
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> SupplierPaymentReconciliationService:
    return SupplierPaymentReconciliationService(session)


@router.get(
    "/bank-transactions/{bank_transaction_id}/supplier-payments",
    response_model=SupplierPaymentReconciliationPreview,
)
async def preview_supplier_payment_reconciliation(
    bank_transaction_id: str,
    date_window_days: Annotated[int, Query(ge=0, le=90)] = 5,
    service: SupplierPaymentReconciliationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_reconciliation:read")),
):
    return await service.preview(
        tenant.organization_id,
        bank_transaction_id,
        date_window_days,
    )
