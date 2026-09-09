from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting.account import Account
from app.schemas.accounting.account import AccountCreate, AccountUpdate


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, organization_id: str, account_id: str) -> Account | None:
        return await self.session.scalar(
            select(Account).where(
                Account.organization_id == organization_id,
                Account.id == account_id,
            )
        )

    async def get_by_code(self, organization_id: str, code: str) -> Account | None:
        return await self.session.scalar(
            select(Account).where(
                Account.organization_id == organization_id,
                Account.code == code,
            )
        )

    async def list(self, organization_id: str, skip: int = 0, limit: int = 100) -> list[Account]:
        result = await self.session.scalars(
            select(Account)
            .where(Account.organization_id == organization_id)
            .order_by(Account.code)
            .offset(skip)
            .limit(limit)
        )
        return list(result)

    async def has_children(self, organization_id: str, account_id: str) -> bool:
        count = await self.session.scalar(
            select(func.count(Account.id)).where(
                Account.organization_id == organization_id,
                Account.parent_id == account_id,
            )
        )
        return bool(count)

    async def create(
        self, organization_id: str, data: AccountCreate, level: int, path: str
    ) -> Account:
        account = Account(
            **data.model_dump(),
            organization_id=organization_id,
            level=level,
            path=path,
        )
        self.session.add(account)
        await self.session.flush()
        return account

    async def update(self, account: Account, data: AccountUpdate) -> Account:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(account, field, value)
        await self.session.flush()
        return account

    async def delete(self, account: Account) -> None:
        await self.session.delete(account)
        await self.session.flush()
