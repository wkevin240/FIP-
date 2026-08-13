from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting.closing import PeriodClosing


class ClosingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_period(
        self, organization_id: str, fiscal_period_id: str
    ) -> PeriodClosing | None:
        return await self.session.scalar(
            select(PeriodClosing).where(
                PeriodClosing.organization_id == organization_id,
                PeriodClosing.fiscal_period_id == fiscal_period_id,
            )
        )

    async def create(self, closing: PeriodClosing) -> PeriodClosing:
        self.session.add(closing)
        await self.session.flush()
        return closing
