from decimal import Decimal

from app.domain.treasury.position.rules import TreasuryPosition, TreasuryPositionRules
from app.models.accounting.account import Account
from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.journal_entry_line import JournalEntryLine
from app.models.treasury.bank_account import TreasuryBankAccount
from app.repositories.treasury.bank_account_repository import (
    TreasuryBankAccountRepository,
)
from app.repositories.treasury.bank_transaction_repository import (
    TreasuryBankTransactionRepository,
)
from app.schemas.treasury.bank_account import (
    TreasuryBankAccountCreate,
    TreasuryBankAccountUpdate,
)
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class TreasuryBankAccountService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.bank_accounts = TreasuryBankAccountRepository(session)
        self.transactions = TreasuryBankTransactionRepository(session)

    async def get_bank_account(
        self, organization_id: str, treasury_bank_account_id: str
    ) -> TreasuryBankAccount:
        bank_account = await self.bank_accounts.get_by_id(
            organization_id, treasury_bank_account_id
        )
        if bank_account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Treasury bank account not found",
            )
        return bank_account

    async def list_bank_accounts(
        self,
        organization_id: str,
        active_only: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> list[TreasuryBankAccount]:
        return await self.bank_accounts.list(
            organization_id,
            active_only,
            max(offset, 0),
            min(max(limit, 1), 100),
        )

    async def create_bank_account(
        self, organization_id: str, data: TreasuryBankAccountCreate
    ) -> TreasuryBankAccount:
        await self._validate_ledger_account(organization_id, data.ledger_account_id)
        if await self.bank_accounts.get_by_ledger_account(
            organization_id, data.ledger_account_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Treasury profile already exists for this ledger account",
            )
        if await self.bank_accounts.get_by_account_number(
            organization_id, data.account_number
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Treasury bank account number already exists",
            )
        try:
            bank_account = await self.bank_accounts.create(organization_id, data)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Treasury bank account profile conflicts with an existing profile",
            ) from exc
        await self.session.refresh(bank_account)
        return bank_account

    async def update_bank_account(
        self,
        organization_id: str,
        treasury_bank_account_id: str,
        data: TreasuryBankAccountUpdate,
    ) -> TreasuryBankAccount:
        bank_account = await self.get_bank_account(
            organization_id, treasury_bank_account_id
        )
        await self.bank_accounts.update(bank_account, data)
        await self.session.commit()
        return await self.get_bank_account(organization_id, bank_account.id)

    async def get_position(
        self, organization_id: str, treasury_bank_account_id: str
    ) -> TreasuryPosition:
        bank_account = await self.get_bank_account(
            organization_id, treasury_bank_account_id
        )
        (
            transaction_total,
            unreconciled_total,
            unreconciled_count,
        ) = await self.transactions.totals(
            organization_id,
            bank_account.ledger_account_id,
            bank_account.opening_date,
        )
        ledger_movements = await self.session.scalar(
            select(
                func.coalesce(
                    func.sum(JournalEntryLine.debit - JournalEntryLine.credit), 0
                )
            )
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                JournalEntry.organization_id == organization_id,
                JournalEntryLine.account_id == bank_account.ledger_account_id,
                JournalEntry.status == "POSTED",
                JournalEntry.entry_date >= bank_account.opening_date,
            )
        )
        return TreasuryPositionRules.calculate(
            Decimal(bank_account.opening_balance),
            [transaction_total],
            Decimal(bank_account.opening_balance) + Decimal(ledger_movements),
            unreconciled_total,
            unreconciled_count,
        )

    async def _validate_ledger_account(
        self, organization_id: str, ledger_account_id: str
    ) -> None:
        account = await self.session.scalar(
            select(Account).where(
                Account.organization_id == organization_id,
                Account.id == ledger_account_id,
                Account.is_active.is_(True),
            )
        )
        if account is None or account.account_type != "ASSET":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Active asset ledger account required for treasury bank profile",
            )
