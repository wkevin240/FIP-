from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.accounting.fiscal_year.rules import FiscalYearRules
from app.models.accounting.fiscal_year import FiscalYear
from app.repositories.accounting.fiscal_year_repository import FiscalYearRepository
from app.schemas.accounting.fiscal_year import FiscalYearCreate, FiscalYearUpdate


class FiscalYearService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = FiscalYearRepository(session)

    async def create_fiscal_year(self, organization_id: str, data: FiscalYearCreate) -> FiscalYear:
        FiscalYearRules.validate_dates(data.start_date, data.end_date)
        existing = await self.repository.list(organization_id)
        FiscalYearRules.check_overlap(data.start_date, data.end_date, [
            {"name": item.name, "start_date": item.start_date, "end_date": item.end_date} for item in existing
        ])
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
