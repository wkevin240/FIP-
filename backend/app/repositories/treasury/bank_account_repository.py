from app.models.treasury.bank_account import TreasuryBankAccount
from app.schemas.treasury.bank_account import (
    TreasuryBankAccountCreate,
    TreasuryBankAccountUpdate,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TreasuryBankAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        organization_id: str,
        treasury_bank_account_id: str,
        for_update: bool = False,
    ) -> TreasuryBankAccount | None:
        statement = select(TreasuryBankAccount).where(
            TreasuryBankAccount.organization_id == organization_id,
            TreasuryBankAccount.id == treasury_bank_account_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def get_by_ledger_account(
        self, organization_id: str, ledger_account_id: str
    ) -> TreasuryBankAccount | None:
        return await self.session.scalar(
            select(TreasuryBankAccount).where(
                TreasuryBankAccount.organization_id == organization_id,
                TreasuryBankAccount.ledger_account_id == ledger_account_id,
            )
        )

    async def get_by_account_number(
        self, organization_id: str, account_number: str
    ) -> TreasuryBankAccount | None:
        return await self.session.scalar(
            select(TreasuryBankAccount).where(
                TreasuryBankAccount.organization_id == organization_id,
                TreasuryBankAccount.account_number == account_number,
            )
        )

    async def list(
        self, organization_id: str, active_only: bool, offset: int, limit: int
    ) -> list[TreasuryBankAccount]:
        statement = select(TreasuryBankAccount).where(
            TreasuryBankAccount.organization_id == organization_id
        )
        if active_only:
            statement = statement.where(TreasuryBankAccount.is_active.is_(True))
        result = await self.session.scalars(
            statement.order_by(
                TreasuryBankAccount.bank_name, TreasuryBankAccount.account_name
            )
            .offset(offset)
            .limit(limit)
        )
        return list(result)

    async def create(
        self, organization_id: str, data: TreasuryBankAccountCreate
    ) -> TreasuryBankAccount:
        bank_account = TreasuryBankAccount(
            **data.model_dump(), organization_id=organization_id
        )
        self.session.add(bank_account)
        await self.session.flush()
        return bank_account

    async def update(
        self, bank_account: TreasuryBankAccount, data: TreasuryBankAccountUpdate
    ) -> TreasuryBankAccount:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(bank_account, field, value)
        await self.session.flush()
        return bank_account
