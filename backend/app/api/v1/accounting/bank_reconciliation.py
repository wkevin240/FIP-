from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.bank_reconciliation import (
    BankReconciliationResponse,
    BankTransactionCreate,
    BankTransactionResponse,
    ReconcileBankTransactionRequest,
    ReconciliationCandidate,
)
from app.services.accounting.bank_reconciliation_service import (
    BankReconciliationService,
)
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> BankReconciliationService:
    return BankReconciliationService(session)


@router.post(
    "/transactions",
    response_model=BankTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bank_transaction(
    data: BankTransactionCreate,
    service: BankReconciliationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("bank_reconciliation:create")),
) -> BankTransactionResponse:
    return await service.create_transaction(tenant.organization_id, data)


@router.get("/transactions", response_model=list[BankTransactionResponse])
async def list_bank_transactions(
    bank_account_id: str,
    reconciled: bool | None = Query(None),
    service: BankReconciliationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("bank_reconciliation:read")),
) -> list[BankTransactionResponse]:
    return await service.list_transactions(
        tenant.organization_id, bank_account_id, reconciled
    )


@router.get(
    "/transactions/{transaction_id}/candidates",
    response_model=list[ReconciliationCandidate],
)
async def get_reconciliation_candidates(
    transaction_id: str,
    date_window_days: int = Query(7, ge=0, le=90),
    service: BankReconciliationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("bank_reconciliation:read")),
) -> list[ReconciliationCandidate]:
    return await service.candidate_entries(
        tenant.organization_id, transaction_id, date_window_days
    )


@router.post(
    "/transactions/{transaction_id}/match",
    response_model=BankReconciliationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def reconcile_bank_transaction(
    transaction_id: str,
    data: ReconcileBankTransactionRequest,
    service: BankReconciliationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("bank_reconciliation:match")),
) -> BankReconciliationResponse:
    return await service.reconcile(
        tenant.organization_id, transaction_id, data.journal_entry_id, tenant.user_id
    )
