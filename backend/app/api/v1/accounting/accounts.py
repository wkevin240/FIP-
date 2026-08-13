from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.account import AccountCreate, AccountResponse, AccountUpdate
from app.services.accounting.account_service import AccountService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


def get_account_service(db: AsyncSession = Depends(get_db)) -> AccountService:
    return AccountService(db)


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    account_in: AccountCreate,
    service: AccountService = Depends(get_account_service),
    tenant: CurrentTenant = Depends(require_permission("account:create")),
):
    return await service.create_account(tenant.organization_id, account_in)


@router.get("/", response_model=list[AccountResponse])
async def read_accounts(
    skip: int = 0,
    limit: int = 100,
    service: AccountService = Depends(get_account_service),
    tenant: CurrentTenant = Depends(require_permission("account:read")),
):
    return await service.get_all_accounts(
        tenant.organization_id, skip=skip, limit=limit
    )


@router.get("/{account_id}", response_model=AccountResponse)
async def read_account(
    account_id: str,
    service: AccountService = Depends(get_account_service),
    tenant: CurrentTenant = Depends(require_permission("account:read")),
):
    return await service.get_account(tenant.organization_id, account_id)


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: str,
    account_in: AccountUpdate,
    service: AccountService = Depends(get_account_service),
    tenant: CurrentTenant = Depends(require_permission("account:update")),
):
    return await service.update_account(tenant.organization_id, account_id, account_in)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: str,
    service: AccountService = Depends(get_account_service),
    tenant: CurrentTenant = Depends(require_permission("account:update")),
):
    await service.delete_account(tenant.organization_id, account_id)
