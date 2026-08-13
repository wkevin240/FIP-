from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums.accounting import JournalEntryStatus
from app.models.accounting.bank_reconciliation import BankReconciliation
from app.models.accounting.bank_transaction import BankTransaction
from app.models.accounting.journal_entry import JournalEntry
from app.schemas.accounting.bank_reconciliation import BankTransactionCreate


class BankReconciliationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_transaction(
        self, organization_id: str, transaction_id: str, for_update: bool = False
    ) -> BankTransaction | None:
        query = (
            select(BankTransaction)
            .options(selectinload(BankTransaction.reconciliation))
            .where(
                BankTransaction.organization_id == organization_id,
                BankTransaction.id == transaction_id,
            )
        )
        if for_update:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def get_transaction_by_external_id(
        self, organization_id: str, bank_account_id: str, external_id: str
    ) -> BankTransaction | None:
        return await self.session.scalar(
            select(BankTransaction).where(
                BankTransaction.organization_id == organization_id,
                BankTransaction.bank_account_id == bank_account_id,
                BankTransaction.external_id == external_id,
            )
        )

    async def list_transactions(
        self, organization_id: str, bank_account_id: str, reconciled: bool | None
    ) -> list[BankTransaction]:
        query = (
            select(BankTransaction)
            .options(selectinload(BankTransaction.reconciliation))
            .where(
                BankTransaction.organization_id == organization_id,
                BankTransaction.bank_account_id == bank_account_id,
            )
            .order_by(BankTransaction.transaction_date, BankTransaction.id)
        )
        if reconciled is True:
            query = query.where(BankTransaction.reconciled_at.is_not(None))
        elif reconciled is False:
            query = query.where(BankTransaction.reconciled_at.is_(None))
        result = await self.session.scalars(query)
        return list(result.unique())

    async def create_transaction(
        self, organization_id: str, data: BankTransactionCreate
    ) -> BankTransaction:
        transaction = BankTransaction(
            **data.model_dump(), organization_id=organization_id
        )
        self.session.add(transaction)
        await self.session.flush()
        return transaction

    async def candidate_entries(
        self,
        organization_id: str,
        bank_account_id: str,
        start_date: date,
        end_date: date,
    ) -> list[JournalEntry]:
        result = await self.session.scalars(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .outerjoin(
                BankReconciliation,
                BankReconciliation.journal_entry_id == JournalEntry.id,
            )
            .where(
                JournalEntry.organization_id == organization_id,
                JournalEntry.status == JournalEntryStatus.POSTED,
                JournalEntry.entry_date >= start_date,
                JournalEntry.entry_date <= end_date,
                BankReconciliation.id.is_(None),
            )
            .order_by(JournalEntry.entry_date, JournalEntry.entry_number)
        )
        return list(result.unique())

    async def get_entry(
        self, organization_id: str, entry_id: str, for_update: bool = False
    ) -> JournalEntry | None:
        query = (
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(
                JournalEntry.organization_id == organization_id,
                JournalEntry.id == entry_id,
                JournalEntry.status == JournalEntryStatus.POSTED,
            )
        )
        if for_update:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def create_reconciliation(
        self, reconciliation: BankReconciliation
    ) -> BankReconciliation:
        self.session.add(reconciliation)
        await self.session.flush()
        return reconciliation
