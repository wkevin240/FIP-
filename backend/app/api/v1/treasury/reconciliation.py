from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.treasury.reconciliation import (
    AccountingTreasuryReconciliationResponse,
    TreasuryReconcileRequest,
    TreasuryReconciliationResponse,
)
from app.services.treasury.accounting_treasury_reconciliation_service import (
    AccountingTreasuryReconciliationService,
)
from app.services.treasury.reconciliation_service import TreasuryReconciliationService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> TreasuryReconciliationService:
    return TreasuryReconciliationService(session)


async def get_accounting_treasury_service(
    session: AsyncSession = Depends(get_db),
) -> AccountingTreasuryReconciliationService:
    return AccountingTreasuryReconciliationService(session)


@router.get(
    "/accounting-treasury",
    response_model=AccountingTreasuryReconciliationResponse,
)
async def accounting_treasury_reconciliation(
    as_of: date = Query(...),
    service: AccountingTreasuryReconciliationService = Depends(
        get_accounting_treasury_service
    ),
    tenant: CurrentTenant = Depends(require_permission("treasury_reconciliation:read")),
) -> AccountingTreasuryReconciliationResponse:
    return await service.report(tenant.organization_id, as_of)


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
