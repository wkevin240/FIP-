from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting.fiscal_period import FiscalPeriod
from app.schemas.accounting.fiscal_period import FiscalPeriodCreate, FiscalPeriodUpdate


class FiscalPeriodRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, organization_id: str, period_id: str) -> FiscalPeriod | None:
        return await self.session.scalar(select(FiscalPeriod).where(FiscalPeriod.organization_id == organization_id, FiscalPeriod.id == period_id))

    async def list_by_fiscal_year(self, organization_id: str, fiscal_year_id: str) -> list[FiscalPeriod]:
        result = await self.session.scalars(select(FiscalPeriod).where(FiscalPeriod.organization_id == organization_id, FiscalPeriod.fiscal_year_id == fiscal_year_id).order_by(FiscalPeriod.start_date))
        return list(result)

    async def create(self, organization_id: str, data: FiscalPeriodCreate) -> FiscalPeriod:
        period = FiscalPeriod(**data.model_dump(), organization_id=organization_id)
        self.session.add(period)
        await self.session.flush()
        return period

    async def update(self, period: FiscalPeriod, data: FiscalPeriodUpdate) -> FiscalPeriod:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(period, field, value)
        await self.session.flush()
        return period

    async def delete(self, period: FiscalPeriod) -> None:
        await self.session.delete(period)
        await self.session.flush()
