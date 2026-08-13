from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.treasury.bank_account import (
    TreasuryBankAccountCreate,
    TreasuryBankAccountResponse,
    TreasuryBankAccountUpdate,
    TreasuryPositionResponse,
)
from app.services.treasury.bank_account_service import TreasuryBankAccountService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> TreasuryBankAccountService:
    return TreasuryBankAccountService(session)


@router.post(
    "/", response_model=TreasuryBankAccountResponse, status_code=status.HTTP_201_CREATED
)
async def create_bank_account(
    data: TreasuryBankAccountCreate,
    service: TreasuryBankAccountService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_bank_account:create")),
) -> TreasuryBankAccountResponse:
    return await service.create_bank_account(tenant.organization_id, data)


@router.get("/", response_model=list[TreasuryBankAccountResponse])
async def list_bank_accounts(
    active_only: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: TreasuryBankAccountService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_bank_account:read")),
) -> list[TreasuryBankAccountResponse]:
    return await service.list_bank_accounts(
        tenant.organization_id, active_only, offset, limit
    )


@router.get("/{treasury_bank_account_id}", response_model=TreasuryBankAccountResponse)
async def get_bank_account(
    treasury_bank_account_id: str,
    service: TreasuryBankAccountService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_bank_account:read")),
) -> TreasuryBankAccountResponse:
    return await service.get_bank_account(
        tenant.organization_id, treasury_bank_account_id
    )


@router.patch("/{treasury_bank_account_id}", response_model=TreasuryBankAccountResponse)
async def update_bank_account(
    treasury_bank_account_id: str,
    data: TreasuryBankAccountUpdate,
    service: TreasuryBankAccountService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_bank_account:update")),
) -> TreasuryBankAccountResponse:
    return await service.update_bank_account(
        tenant.organization_id, treasury_bank_account_id, data
    )


@router.get(
    "/{treasury_bank_account_id}/position", response_model=TreasuryPositionResponse
)
async def get_position(
    treasury_bank_account_id: str,
    service: TreasuryBankAccountService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("treasury_position:read")),
) -> TreasuryPositionResponse:
    position = await service.get_position(
        tenant.organization_id, treasury_bank_account_id
    )
    bank_account = await service.get_bank_account(
        tenant.organization_id, treasury_bank_account_id
    )
    return TreasuryPositionResponse(
        treasury_bank_account_id=bank_account.id,
        ledger_account_id=bank_account.ledger_account_id,
        **position.__dict__,
    )
