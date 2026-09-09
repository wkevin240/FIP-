from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.accounting.journal_entry import JournalEntry


class JournalEntryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, organization_id: str, entry_id: str) -> JournalEntry | None:
        result = await self.session.execute(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(JournalEntry.organization_id == organization_id, JournalEntry.id == entry_id)
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, organization_id: str, key: str) -> JournalEntry | None:
        result = await self.session.execute(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(JournalEntry.organization_id == organization_id, JournalEntry.idempotency_key == key)
        )
        return result.scalar_one_or_none()
