from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.treasury.reconciliation import (
    TreasuryReconcileRequest,
    TreasuryReconciliationResponse,
)
from app.services.treasury.reconciliation_service import TreasuryReconciliationService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> TreasuryReconciliationService:
    return TreasuryReconciliationService(session)


@router.post(
    "/bank-accounts/{treasury_bank_account_id}/transactions/{transaction_id}/match",
    response_model=TreasuryReconciliationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def reconcile_transaction(
    treasury_bank_account_id: str,
    transaction_id: str,
    data: TreasuryReconcileRequest,
    service: TreasuryReconciliationService = Depends(get_service),
    tenant: CurrentTenant = Depends(
        require_permission("treasury_reconciliation:match")
    ),
) -> TreasuryReconciliationResponse:
    return await service.reconcile(
        tenant.organization_id,
        treasury_bank_account_id,
        transaction_id,
        data.journal_entry_id,
        tenant.user_id,
    )
