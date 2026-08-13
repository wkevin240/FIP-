from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.reporting import (
    BalanceSheetResponse,
    IncomeStatementResponse,
)
from app.services.accounting.reporting_service import ReportingService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> ReportingService:
    return ReportingService(session)


@router.get("/balance-sheet", response_model=BalanceSheetResponse)
async def get_balance_sheet(
    as_of_date: date = Query(...),
    service: ReportingService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("financial_report:read")),
) -> BalanceSheetResponse:
    return await service.balance_sheet(tenant.organization_id, as_of_date)


@router.get("/income-statement", response_model=IncomeStatementResponse)
async def get_income_statement(
    start_date: date = Query(...),
    end_date: date = Query(...),
    service: ReportingService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("financial_report:read")),
) -> IncomeStatementResponse:
    return await service.income_statement(tenant.organization_id, start_date, end_date)
