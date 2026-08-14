from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.reporting import (
    BalanceSheetResponse,
    ComparativeBalanceResponse,
    GeneralLedgerResponse,
    IncomeStatementResponse,
    TrialBalanceResponse,
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


@router.get("/trial-balance", response_model=TrialBalanceResponse)
async def get_trial_balance(
    end_date: date = Query(...),
    start_date: date | None = Query(None),
    service: ReportingService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("trial_balance:read")),
) -> TrialBalanceResponse:
    return await service.trial_balance(tenant.organization_id, end_date, start_date)


@router.get("/general-ledger/{account_id}", response_model=GeneralLedgerResponse)
async def get_general_ledger(
    account_id: str,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: ReportingService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("general_ledger:read")),
) -> GeneralLedgerResponse:
    return await service.general_ledger(
        tenant.organization_id, account_id, start_date, end_date, skip, limit
    )


@router.get("/comparative-balance", response_model=ComparativeBalanceResponse)
async def get_comparative_balance(
    current_start_date: date = Query(...),
    current_end_date: date = Query(...),
    previous_start_date: date = Query(...),
    previous_end_date: date = Query(...),
    service: ReportingService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("comparative_balance:read")),
) -> ComparativeBalanceResponse:
    return await service.comparative_balance(
        tenant.organization_id,
        current_start_date,
        current_end_date,
        previous_start_date,
        previous_end_date,
    )
