from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.ledger import TrialBalanceRow
from app.services.accounting.ledger_service import LedgerService

router = APIRouter()


def get_ledger_service(db: AsyncSession = Depends(get_db)) -> LedgerService:
    return LedgerService(db)


@router.get("/trial-balance", response_model=list[TrialBalanceRow])
async def trial_balance(
    tenant: CurrentTenant = Depends(require_permission("ledger:read")),
    service: LedgerService = Depends(get_ledger_service),
):
    return await service.trial_balance(tenant.organization_id)


@router.get("/accounts/{account_id}/balance")
async def account_balance(
    account_id: str,
    tenant: CurrentTenant = Depends(require_permission("ledger:read")),
    service: LedgerService = Depends(get_ledger_service),
):
    return {"account_id": account_id, "balance": await service.account_balance(tenant.organization_id, account_id)}


@router.get("/accounts/{account_id}/movements")
async def account_movements(
    account_id: str,
    tenant: CurrentTenant = Depends(require_permission("ledger:read")),
    service: LedgerService = Depends(get_ledger_service),
):
    return await service.general_ledger(tenant.organization_id, account_id)
