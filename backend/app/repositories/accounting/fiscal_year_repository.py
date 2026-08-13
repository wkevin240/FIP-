from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting.fiscal_year import FiscalYear
from app.schemas.accounting.fiscal_year import FiscalYearCreate, FiscalYearUpdate


class FiscalYearRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, organization_id: str, fiscal_year_id: str
    ) -> FiscalYear | None:
        return await self.session.scalar(
            select(FiscalYear).where(
                FiscalYear.organization_id == organization_id,
                FiscalYear.id == fiscal_year_id,
            )
        )

    async def list(self, organization_id: str) -> list[FiscalYear]:
        result = await self.session.scalars(
            select(FiscalYear)
            .where(FiscalYear.organization_id == organization_id)
            .order_by(FiscalYear.start_date)
        )
        return list(result)

    async def create(self, organization_id: str, data: FiscalYearCreate) -> FiscalYear:
        fiscal_year = FiscalYear(**data.model_dump(), organization_id=organization_id)
        self.session.add(fiscal_year)
        await self.session.flush()
        return fiscal_year

    async def update(
        self, fiscal_year: FiscalYear, data: FiscalYearUpdate
    ) -> FiscalYear:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(fiscal_year, field, value)
        await self.session.flush()
        return fiscal_year

    async def delete(self, fiscal_year: FiscalYear) -> None:
        await self.session.delete(fiscal_year)
        await self.session.flush()
