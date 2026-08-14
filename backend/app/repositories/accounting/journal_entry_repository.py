from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.journal_entry_line import JournalEntryLine
from app.schemas.accounting.journal_entry import JournalEntryCreate


class JournalEntryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _with_lines(query):
        return query.options(selectinload(JournalEntry.lines))

    async def get_by_id(
        self, organization_id: str, journal_entry_id: str
    ) -> JournalEntry | None:
        return await self.session.scalar(
            self._with_lines(
                select(JournalEntry).where(
                    JournalEntry.organization_id == organization_id,
                    JournalEntry.id == journal_entry_id,
                )
            )
        )

    async def get_by_number(
        self, organization_id: str, journal_id: str, entry_number: str
    ) -> JournalEntry | None:
        return await self.session.scalar(
            select(JournalEntry).where(
                JournalEntry.organization_id == organization_id,
                JournalEntry.journal_id == journal_id,
                JournalEntry.entry_number == entry_number,
            )
        )

    async def list(
        self, organization_id: str, skip: int = 0, limit: int = 100
    ) -> list[JournalEntry]:
        result = await self.session.scalars(
            self._with_lines(
                select(JournalEntry)
                .where(JournalEntry.organization_id == organization_id)
                .order_by(
                    JournalEntry.entry_date.desc(), JournalEntry.entry_number.desc()
                )
                .offset(skip)
                .limit(limit)
            )
        )
        return list(result.unique())

    async def create(
        self, organization_id: str, data: JournalEntryCreate
    ) -> JournalEntry:
        entry_data = data.model_dump(exclude={"lines"})
        entry = JournalEntry(**entry_data, organization_id=organization_id)
        self.session.add(entry)
        await self.session.flush()

        for line_number, line_data in enumerate(data.lines, start=1):
            line = JournalEntryLine(
                organization_id=organization_id,
                journal_entry_id=entry.id,
                line_number=line_number,
                **line_data.model_dump(),
            )
            self.session.add(line)
        await self.session.flush()
        return entry
