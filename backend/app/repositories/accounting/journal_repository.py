from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting.journal import Journal
from app.schemas.accounting.journal import JournalCreate


class JournalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, organization_id: str, journal_id: str) -> Journal | None:
        return await self.session.scalar(
            select(Journal).where(
                Journal.organization_id == organization_id, Journal.id == journal_id
            )
        )

    async def get_by_code(self, organization_id: str, code: str) -> Journal | None:
        return await self.session.scalar(
            select(Journal).where(
                Journal.organization_id == organization_id, Journal.code == code
            )
        )

    async def list(
        self, organization_id: str, skip: int = 0, limit: int = 100
    ) -> list[Journal]:
        result = await self.session.scalars(
            select(Journal)
            .where(Journal.organization_id == organization_id)
            .order_by(Journal.code)
            .offset(skip)
            .limit(limit)
        )
        return list(result)

    async def create(self, organization_id: str, data: JournalCreate) -> Journal:
        journal = Journal(**data.model_dump(), organization_id=organization_id)
        self.session.add(journal)
        await self.session.flush()
        return journal
