from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums.accounting import JournalEntryStatus
from app.models.accounting.account import Account
from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.journal_entry_line import JournalEntryLine


class ReportingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def account_movements(
        self,
        organization_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[tuple[Account, Decimal, Decimal]]:
        query = (
            select(
                Account,
                func.coalesce(func.sum(JournalEntryLine.debit), 0).label("debit"),
                func.coalesce(func.sum(JournalEntryLine.credit), 0).label("credit"),
            )
            .join(JournalEntryLine, JournalEntryLine.account_id == Account.id)
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                Account.organization_id == organization_id,
                JournalEntry.organization_id == organization_id,
                JournalEntry.status == JournalEntryStatus.POSTED,
            )
            .group_by(Account.id)
            .order_by(Account.code)
        )
        if start_date is not None:
            query = query.where(JournalEntry.entry_date >= start_date)
        if end_date is not None:
            query = query.where(JournalEntry.entry_date <= end_date)

        result = await self.session.execute(query)
        return [
            (account, Decimal(debit), Decimal(credit))
            for account, debit, credit in result.all()
        ]
