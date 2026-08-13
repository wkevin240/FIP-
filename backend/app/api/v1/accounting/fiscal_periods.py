from fastapi import APIRouter, Depends, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.accounting.fiscal_period import FiscalPeriodCreate, FiscalPeriodResponse
from app.services.accounting.fiscal_period_service import FiscalPeriodService

router = APIRouter()

def get_service(db: AsyncSession = Depends(get_db)) -> FiscalPeriodService:
    return FiscalPeriodService(db)

@router.post("/", response_model=FiscalPeriodResponse, status_code=status.HTTP_201_CREATED)
async def create(data: FiscalPeriodCreate, service: FiscalPeriodService = Depends(get_service)):
    return await service.create_fiscal_period(data)

@router.get("/by-year/{year_id}", response_model=List[FiscalPeriodResponse])
async def get_by_year(year_id: str, service: FiscalPeriodService = Depends(get_service)):
    return await service.get_by_fiscal_year(year_id)
