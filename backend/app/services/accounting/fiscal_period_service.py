from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.accounting.fiscal_year.rules import FiscalPeriodRules
from app.models.accounting.fiscal_period import FiscalPeriod
from app.repositories.accounting.fiscal_period_repository import FiscalPeriodRepository
from app.repositories.accounting.fiscal_year_repository import FiscalYearRepository
from app.schemas.accounting.fiscal_period import FiscalPeriodCreate, FiscalPeriodUpdate


class FiscalPeriodService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = FiscalPeriodRepository(session)
        self.year_repository = FiscalYearRepository(session)

    async def create_fiscal_period(self, organization_id: str, data: FiscalPeriodCreate) -> FiscalPeriod:
        try:
            FiscalPeriodRules.validate_dates(data.start_date, data.end_date)
            fiscal_year = await self.year_repository.get_by_id(organization_id, data.fiscal_year_id)
            if fiscal_year is None:
                raise HTTPException(status_code=404, detail="Fiscal year not found")
            FiscalPeriodRules.validate_within_year(
                data.start_date,
                data.end_date,
                fiscal_year.start_date,
                fiscal_year.end_date,
            )
            existing_periods = await self.repository.list_by_fiscal_year(organization_id, data.fiscal_year_id)
            FiscalPeriodRules.check_overlap(
                data.start_date,
                data.end_date,
                [
                    {"name": period.name, "start_date": period.start_date, "end_date": period.end_date}
                    for period in existing_periods
                ],
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        period = await self.repository.create(organization_id, data)
        await self.session.commit()
        await self.session.refresh(period)
        return period

    async def get_by_id(self, organization_id: str, period_id: str) -> FiscalPeriod:
        period = await self.repository.get_by_id(organization_id, period_id)
        if period is None:
            raise HTTPException(status_code=404, detail="Fiscal period not found")
        return period

    async def get_by_fiscal_year(self, organization_id: str, fiscal_year_id: str) -> list[FiscalPeriod]:
        if await self.year_repository.get_by_id(organization_id, fiscal_year_id) is None:
            raise HTTPException(status_code=404, detail="Fiscal year not found")
        return await self.repository.list_by_fiscal_year(organization_id, fiscal_year_id)
