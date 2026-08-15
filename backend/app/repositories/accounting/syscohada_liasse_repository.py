from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums.accounting import JournalEntryStatus
from app.models.accounting.journal_entry import JournalEntry


class SyscohadaLiasseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def posted_entry_count(
        self, organization_id: str, start_date: date, end_date: date
    ) -> int:
        result = await self.session.scalar(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.organization_id == organization_id,
                JournalEntry.status == JournalEntryStatus.POSTED,
                JournalEntry.entry_date >= start_date,
                JournalEntry.entry_date <= end_date,
            )
        )
        return int(result or 0)
