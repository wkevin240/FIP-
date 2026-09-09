from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting.account import Account
from app.repositories.accounting.account_repository import AccountRepository
from app.schemas.accounting.account import AccountCreate, AccountUpdate


class AccountService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AccountRepository(session)

    async def get_account(self, organization_id: str, account_id: str) -> Account:
        account = await self.repository.get_by_id(organization_id, account_id)
        if account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
        return account

    async def get_all_accounts(self, organization_id: str, skip: int = 0, limit: int = 100) -> list[Account]:
        return await self.repository.list(organization_id, skip, limit)

    async def create_account(self, organization_id: str, data: AccountCreate) -> Account:
        if await self.repository.get_by_code(organization_id, data.code):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account code already exists")

        parent = await self._related_account(organization_id, data.parent_id, "Parent account not found")
        await self._related_account(
            organization_id, data.collective_account_id, "Collective account not found"
        )

        level = parent.level + 1 if parent else 1
        path = f"{parent.path}{data.code}/" if parent else f"/{data.code}/"
        account = await self.repository.create(organization_id, data, level, path)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def update_account(
        self, organization_id: str, account_id: str, data: AccountUpdate
    ) -> Account:
        account = await self.get_account(organization_id, account_id)

        if data.parent_id is not None:
            if data.parent_id == account.id:
                raise HTTPException(status_code=422, detail="Account cannot be its own parent")
            parent = await self._related_account(organization_id, data.parent_id, "Parent account not found")
            if parent and parent.path.startswith(account.path):
                raise HTTPException(status_code=422, detail="Account cannot become a descendant of itself")

        if data.collective_account_id is not None:
            await self._related_account(
                organization_id, data.collective_account_id, "Collective account not found"
            )

        await self.repository.update(account, data)
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def delete_account(self, organization_id: str, account_id: str) -> None:
        account = await self.get_account(organization_id, account_id)
        if await self.repository.has_children(organization_id, account.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Account with child accounts cannot be deleted",
            )
        await self.repository.delete(account)
        await self.session.commit()

    async def _related_account(
        self, organization_id: str, account_id: str | None, message: str
    ) -> Account | None:
        if account_id is None:
            return None
        account = await self.repository.get_by_id(organization_id, account_id)
        if account is None:
            raise HTTPException(status_code=422, detail=message)
        return account
