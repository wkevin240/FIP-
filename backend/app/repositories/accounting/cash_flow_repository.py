from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums.accounting import JournalEntryStatus
from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.journal_entry_line import JournalEntryLine


class CashFlowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def cash_balance(
        self, organization_id: str, cash_account_ids: set[str], end_date: date
    ) -> Decimal:
        if not cash_account_ids:
            return Decimal("0.00")
        value = await self.session.scalar(
            select(
                func.coalesce(
                    func.sum(JournalEntryLine.debit - JournalEntryLine.credit), 0
                )
            )
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                JournalEntry.organization_id == organization_id,
                JournalEntryLine.organization_id == organization_id,
                JournalEntryLine.account_id.in_(cash_account_ids),
                JournalEntry.status == JournalEntryStatus.POSTED,
                JournalEntry.entry_date <= end_date,
            )
        )
        return Decimal(value or 0)

    async def posted_entries_with_cash_activity(
        self,
        organization_id: str,
        cash_account_ids: set[str],
        start_date: date,
        end_date: date,
    ) -> list[JournalEntry]:
        if not cash_account_ids:
            return []
        result = await self.session.scalars(
            select(JournalEntry)
            .join(
                JournalEntryLine, JournalEntryLine.journal_entry_id == JournalEntry.id
            )
            .options(selectinload(JournalEntry.lines))
            .where(
                JournalEntry.organization_id == organization_id,
                JournalEntryLine.organization_id == organization_id,
                JournalEntryLine.account_id.in_(cash_account_ids),
                JournalEntry.status == JournalEntryStatus.POSTED,
                JournalEntry.entry_date >= start_date,
                JournalEntry.entry_date <= end_date,
            )
            .order_by(JournalEntry.entry_date, JournalEntry.entry_number)
            .distinct()
        )
        return list(result)
