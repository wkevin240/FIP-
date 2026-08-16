from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums.accounting import JournalEntryStatus
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.journal_entry import JournalEntry


class FiscalYearClosingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_fiscal_year(
        self, organization_id: str, fiscal_year_id: str, for_update: bool = False
    ) -> FiscalYear | None:
        query = select(FiscalYear).where(
            FiscalYear.organization_id == organization_id,
            FiscalYear.id == fiscal_year_id,
        )
        if for_update:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def periods(
        self, organization_id: str, fiscal_year_id: str
    ) -> list[FiscalPeriod]:
        return list(
            await self.session.scalars(
                select(FiscalPeriod)
                .where(
                    FiscalPeriod.organization_id == organization_id,
                    FiscalPeriod.fiscal_year_id == fiscal_year_id,
                )
                .order_by(FiscalPeriod.start_date)
            )
        )

    async def draft_entry_count(self, organization_id: str, fiscal_year_id: str) -> int:
        result = await self.session.scalar(
            select(func.count(JournalEntry.id))
            .join(FiscalPeriod, FiscalPeriod.id == JournalEntry.fiscal_period_id)
            .where(
                JournalEntry.organization_id == organization_id,
                FiscalPeriod.organization_id == organization_id,
                FiscalPeriod.fiscal_year_id == fiscal_year_id,
                JournalEntry.status == JournalEntryStatus.DRAFT,
            )
        )
        return int(result or 0)
