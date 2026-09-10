from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums.accounting import FiscalYearStatus
from app.domain.accounting.fiscal_year.rules import FiscalYearRules
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.journal_entry import JournalEntry, JournalEntryStatus
from app.repositories.accounting.fiscal_year_repository import FiscalYearRepository
from app.schemas.accounting.fiscal_year import FiscalYearCreate


class FiscalYearService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = FiscalYearRepository(session)

    async def create_fiscal_year(self, organization_id: str, data: FiscalYearCreate) -> FiscalYear:
        FiscalYearRules.validate_dates(data.start_date, data.end_date)
        existing = await self.repository.list(organization_id)
        FiscalYearRules.check_overlap(
            data.start_date,
            data.end_date,
            [
                {"name": item.name, "start_date": item.start_date, "end_date": item.end_date}
                for item in existing
            ],
        )
        fiscal_year = await self.repository.create(organization_id, data)
        await self.session.commit()
        await self.session.refresh(fiscal_year)
        return fiscal_year

    async def get_by_id(self, organization_id: str, fiscal_year_id: str) -> FiscalYear:
        fiscal_year = await self.repository.get_by_id(organization_id, fiscal_year_id)
        if fiscal_year is None:
            raise HTTPException(status_code=404, detail="Fiscal year not found")
        return fiscal_year

    async def get_all(self, organization_id: str) -> list[FiscalYear]:
        return await self.repository.list(organization_id)

    async def close_fiscal_year(self, organization_id: str, fiscal_year_id: str) -> FiscalYear:
        fiscal_year = await self.session.scalar(
            select(FiscalYear)
            .where(
                FiscalYear.organization_id == organization_id,
                FiscalYear.id == fiscal_year_id,
            )
            .with_for_update()
        )
        if fiscal_year is None:
            raise HTTPException(status_code=404, detail="Fiscal year not found")
        if fiscal_year.status != FiscalYearStatus.OPEN:
            raise HTTPException(status_code=409, detail="Only an open fiscal year can be closed")

        period_statuses = list(
            await self.session.scalars(
                select(FiscalPeriod.status)
                .where(
                    FiscalPeriod.organization_id == organization_id,
                    FiscalPeriod.fiscal_year_id == fiscal_year_id,
                )
                .with_for_update()
            )
        )
        try:
            FiscalYearRules.validate_periods_closed(period_statuses)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        draft_entry = await self.session.scalar(
            select(JournalEntry.id)
            .where(
                JournalEntry.organization_id == organization_id,
                JournalEntry.fiscal_period_id.in_(
                    select(FiscalPeriod.id).where(
                        FiscalPeriod.organization_id == organization_id,
                        FiscalPeriod.fiscal_year_id == fiscal_year_id,
                    )
                ),
                JournalEntry.status == JournalEntryStatus.DRAFT,
            )
            .limit(1)
        )
        if draft_entry is not None:
            raise HTTPException(status_code=409, detail="Fiscal year contains unposted journal entries")

        fiscal_year.status = FiscalYearStatus.CLOSED
        await self.session.commit()
        await self.session.refresh(fiscal_year)
        return fiscal_year
