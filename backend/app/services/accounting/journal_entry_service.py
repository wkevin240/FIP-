from datetime import datetime, timezone

from app.core.enums.accounting import FiscalPeriodStatus, JournalEntryStatus
from app.domain.accounting.journal_entry.rules import JournalEntryRules
from app.models.accounting.account import Account
from app.models.accounting.journal_entry import JournalEntry
from app.repositories.accounting.fiscal_period_repository import FiscalPeriodRepository
from app.repositories.accounting.journal_entry_repository import JournalEntryRepository
from app.repositories.accounting.journal_repository import JournalRepository
from app.schemas.accounting.journal_entry import JournalEntryCreate
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class JournalEntryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.entry_repository = JournalEntryRepository(session)
        self.journal_repository = JournalRepository(session)
        self.period_repository = FiscalPeriodRepository(session)

    async def get_entry(
        self, organization_id: str, journal_entry_id: str
    ) -> JournalEntry:
        entry = await self.entry_repository.get_by_id(organization_id, journal_entry_id)
        if entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found"
            )
        return entry

    async def get_all_entries(
        self, organization_id: str, skip: int = 0, limit: int = 100
    ) -> list[JournalEntry]:
        return await self.entry_repository.list(organization_id, skip, min(limit, 100))

    async def create_entry(
        self, organization_id: str, data: JournalEntryCreate
    ) -> JournalEntry:
        journal = await self.journal_repository.get_by_id(
            organization_id, data.journal_id
        )
        if journal is None or not journal.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Active journal not found",
            )

        period = await self.period_repository.get_by_id(
            organization_id, data.fiscal_period_id
        )
        if period is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Fiscal period not found",
            )
        if period.status != FiscalPeriodStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Fiscal period is not open",
            )

        try:
            JournalEntryRules.validate_entry_date(
                data.entry_date, period.start_date, period.end_date
            )
            JournalEntryRules.validate_balanced_lines(data.lines)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc

        if await self.entry_repository.get_by_number(
            organization_id, data.journal_id, data.entry_number
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Entry number already exists in this journal",
            )

        await self._validate_active_accounts(organization_id, data)

        try:
            entry = await self.entry_repository.create(organization_id, data)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Entry number already exists in this journal",
            ) from exc

        return await self.get_entry(organization_id, entry.id)

    async def post_entry(
        self, organization_id: str, journal_entry_id: str
    ) -> JournalEntry:
        entry = await self.get_entry(organization_id, journal_entry_id)
        if entry.status != JournalEntryStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only draft entries can be posted",
            )

        period = await self.period_repository.get_by_id(
            organization_id, entry.fiscal_period_id
        )
        if period is None or period.status != FiscalPeriodStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Fiscal period is not open",
            )

        try:
            JournalEntryRules.validate_entry_date(
                entry.entry_date, period.start_date, period.end_date
            )
            JournalEntryRules.validate_balanced_lines(entry.lines)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc

        account_ids = {line.account_id for line in entry.lines}
        active_accounts = await self.session.scalars(
            select(Account.id).where(
                Account.organization_id == organization_id,
                Account.id.in_(account_ids),
                Account.is_active.is_(True),
            )
        )
        if len(set(active_accounts)) != len(account_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="All entry accounts must exist and be active",
            )

        entry.status = JournalEntryStatus.POSTED
        entry.posted_at = datetime.now(timezone.utc)
        await self.session.commit()
        return await self.get_entry(organization_id, entry.id)

    async def _validate_active_accounts(
        self, organization_id: str, data: JournalEntryCreate
    ) -> None:
        account_ids = {line.account_id for line in data.lines}
        active_accounts = await self.session.scalars(
            select(Account.id).where(
                Account.organization_id == organization_id,
                Account.id.in_(account_ids),
                Account.is_active.is_(True),
            )
        )
        if len(set(active_accounts)) != len(account_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="All entry accounts must exist and be active",
            )
