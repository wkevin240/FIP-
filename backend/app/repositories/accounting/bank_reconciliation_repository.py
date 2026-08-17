from datetime import date
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums.accounting import JournalEntryStatus
from app.models.accounting.bank_reconciliation import BankReconciliation
from app.models.accounting.bank_reconciliation_allocation import (
    BankReconciliationAllocation,
    BankReconciliationBatch,
)
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
            .options(
                selectinload(BankTransaction.reconciliation),
                selectinload(BankTransaction.allocations),
            )
            .where(
                BankTransaction.organization_id == organization_id,
                BankTransaction.id == transaction_id,
            )
        )
        if for_update:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def get_transactions_for_allocation(
        self, organization_id: str, transaction_ids: set[str]
    ) -> dict[str, BankTransaction]:
        if not transaction_ids:
            return {}
        result = await self.session.scalars(
            select(BankTransaction)
            .options(
                selectinload(BankTransaction.reconciliation),
                selectinload(BankTransaction.allocations),
            )
            .where(
                BankTransaction.organization_id == organization_id,
                BankTransaction.id.in_(sorted(transaction_ids)),
            )
            .order_by(BankTransaction.id)
        )
        transactions = list(result.unique())
        return {transaction.id: transaction for transaction in transactions}

    async def lock_allocation_resources(self, resources: set[str]) -> None:
        if self.session.bind.dialect.name != "postgresql":
            return
        for resource in sorted(resources):
            await self.session.execute(
                text(
                    "SELECT pg_advisory_xact_lock("
                    "hashtext('fip-bank-reconciliation'), hashtext(:resource))"
                ),
                {"resource": resource},
            )

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
            .options(
                selectinload(BankTransaction.reconciliation),
                selectinload(BankTransaction.allocations),
            )
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
            .outerjoin(
                BankReconciliationAllocation,
                BankReconciliationAllocation.journal_entry_id == JournalEntry.id,
            )
            .where(
                JournalEntry.organization_id == organization_id,
                JournalEntry.status == JournalEntryStatus.POSTED,
                JournalEntry.entry_date >= start_date,
                JournalEntry.entry_date <= end_date,
                BankReconciliation.id.is_(None),
                BankReconciliationAllocation.id.is_(None),
            )
            .order_by(JournalEntry.entry_date, JournalEntry.entry_number)
        )
        return list(result.unique())

    async def get_entry(
        self, organization_id: str, entry_id: str, for_update: bool = False
    ) -> JournalEntry | None:
        query = (
            select(JournalEntry)
            .options(
                selectinload(JournalEntry.lines),
                selectinload(JournalEntry.bank_reconciliation),
                selectinload(JournalEntry.bank_allocations).selectinload(
                    BankReconciliationAllocation.bank_transaction
                ),
            )
            .where(
                JournalEntry.organization_id == organization_id,
                JournalEntry.id == entry_id,
                JournalEntry.status == JournalEntryStatus.POSTED,
            )
        )
        if for_update:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def get_entries_for_allocation(
        self, organization_id: str, entry_ids: set[str]
    ) -> dict[str, JournalEntry]:
        if not entry_ids:
            return {}
        result = await self.session.scalars(
            select(JournalEntry)
            .options(
                selectinload(JournalEntry.lines),
                selectinload(JournalEntry.bank_reconciliation),
                selectinload(JournalEntry.bank_allocations).selectinload(
                    BankReconciliationAllocation.bank_transaction
                ),
            )
            .where(
                JournalEntry.organization_id == organization_id,
                JournalEntry.id.in_(sorted(entry_ids)),
                JournalEntry.status == JournalEntryStatus.POSTED,
            )
            .order_by(JournalEntry.id)
        )
        entries = list(result.unique())
        return {entry.id: entry for entry in entries}

    async def allocation_total_for_transaction(
        self, organization_id: str, transaction_id: str
    ):
        return Decimal(
            await self.session.scalar(
                select(
                    func.coalesce(
                        func.sum(BankReconciliationAllocation.matched_amount), 0
                    )
                ).where(
                    BankReconciliationAllocation.organization_id == organization_id,
                    BankReconciliationAllocation.bank_transaction_id == transaction_id,
                )
            )
        )

    async def allocation_total_for_entry(
        self, organization_id: str, bank_account_id: str, entry_id: str
    ):
        return Decimal(
            await self.session.scalar(
                select(
                    func.coalesce(
                        func.sum(BankReconciliationAllocation.matched_amount), 0
                    )
                )
                .join(
                    BankTransaction,
                    (
                        BankTransaction.organization_id
                        == BankReconciliationAllocation.organization_id
                    )
                    & (
                        BankTransaction.id
                        == BankReconciliationAllocation.bank_transaction_id
                    ),
                )
                .where(
                    BankReconciliationAllocation.organization_id == organization_id,
                    BankReconciliationAllocation.journal_entry_id == entry_id,
                    BankTransaction.bank_account_id == bank_account_id,
                )
            )
        )

    async def has_allocations_for_transaction(
        self, organization_id: str, transaction_id: str
    ) -> bool:
        return bool(
            await self.session.scalar(
                select(func.count(BankReconciliationAllocation.id)).where(
                    BankReconciliationAllocation.organization_id == organization_id,
                    BankReconciliationAllocation.bank_transaction_id == transaction_id,
                )
            )
        )

    async def has_allocations_for_entry(
        self, organization_id: str, entry_id: str
    ) -> bool:
        return bool(
            await self.session.scalar(
                select(func.count(BankReconciliationAllocation.id)).where(
                    BankReconciliationAllocation.organization_id == organization_id,
                    BankReconciliationAllocation.journal_entry_id == entry_id,
                )
            )
        )

    async def get_batch_by_key(
        self, organization_id: str, idempotency_key: str
    ) -> BankReconciliationBatch | None:
        return await self.session.scalar(
            select(BankReconciliationBatch)
            .options(selectinload(BankReconciliationBatch.allocations))
            .where(
                BankReconciliationBatch.organization_id == organization_id,
                BankReconciliationBatch.idempotency_key == idempotency_key,
            )
        )

    async def get_batch(
        self, organization_id: str, batch_id: str
    ) -> BankReconciliationBatch | None:
        return await self.session.scalar(
            select(BankReconciliationBatch)
            .options(selectinload(BankReconciliationBatch.allocations))
            .where(
                BankReconciliationBatch.organization_id == organization_id,
                BankReconciliationBatch.id == batch_id,
            )
        )

    async def create_reconciliation(
        self, reconciliation: BankReconciliation
    ) -> BankReconciliation:
        self.session.add(reconciliation)
        await self.session.flush()
        return reconciliation

    async def create_batch(
        self, batch: BankReconciliationBatch
    ) -> BankReconciliationBatch:
        self.session.add(batch)
        await self.session.flush()
        return batch

    async def create_allocations(
        self, allocations: list[BankReconciliationAllocation]
    ) -> None:
        self.session.add_all(allocations)
        await self.session.flush()
