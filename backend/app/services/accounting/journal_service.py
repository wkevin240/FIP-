from app.models.accounting.journal import Journal
from app.repositories.accounting.journal_repository import JournalRepository
from app.schemas.accounting.journal import JournalCreate
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class JournalService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = JournalRepository(session)

    async def get_journal(self, organization_id: str, journal_id: str) -> Journal:
        journal = await self.repository.get_by_id(organization_id, journal_id)
        if journal is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Journal not found"
            )
        return journal

    async def get_all_journals(
        self, organization_id: str, skip: int = 0, limit: int = 100
    ) -> list[Journal]:
        return await self.repository.list(organization_id, skip, min(limit, 100))

    async def create_journal(
        self, organization_id: str, data: JournalCreate
    ) -> Journal:
        if await self.repository.get_by_code(organization_id, data.code):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Journal code already exists",
            )

        try:
            journal = await self.repository.create(organization_id, data)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Journal code already exists",
            ) from exc

        await self.session.refresh(journal)
        return journal
