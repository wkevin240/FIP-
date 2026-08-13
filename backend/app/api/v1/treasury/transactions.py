from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.treasury.reconciliation import TreasuryReconciliationCandidate
from app.schemas.treasury.transaction import (
    TreasuryBankTransactionCreate,
    TreasuryBankTransactionResponse,
)
from app.services.treasury.transaction_service import TreasuryTransactionService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> TreasuryTransactionService:
    return TreasuryTransactionService(session)


@router.post(
    "/",
    response_model=TreasuryBankTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transaction(
    data: TreasuryBankTransactionCreate,
    service: TreasuryTransactionService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_transaction:create")),
) -> TreasuryBankTransactionResponse:
    return await service.create_transaction(tenant.organization_id, data)


@router.get(
    "/bank-accounts/{treasury_bank_account_id}",
    response_model=list[TreasuryBankTransactionResponse],
)
async def list_transactions(
    treasury_bank_account_id: str,
    reconciled: bool | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: TreasuryTransactionService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_transaction:read")),
) -> list[TreasuryBankTransactionResponse]:
    return await service.list_transactions(
        tenant.organization_id,
        treasury_bank_account_id,
        reconciled,
        offset,
        limit,
    )


@router.get(
    "/bank-accounts/{treasury_bank_account_id}/{transaction_id}/candidates",
    response_model=list[TreasuryReconciliationCandidate],
)
async def candidate_entries(
    treasury_bank_account_id: str,
    transaction_id: str,
    date_window_days: int = Query(7, ge=0, le=90),
    service: TreasuryTransactionService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_reconciliation:read")),
) -> list[TreasuryReconciliationCandidate]:
    return await service.candidate_entries(
        tenant.organization_id,
        treasury_bank_account_id,
        transaction_id,
        date_window_days,
    )
