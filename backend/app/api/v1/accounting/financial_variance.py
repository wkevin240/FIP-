from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.financial_variance import (
    FinancialVarianceResponse,
    VarianceComparison,
)
from app.services.accounting.financial_variance_service import FinancialVarianceService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> FinancialVarianceService:
    return FinancialVarianceService(session)


@router.get("/variance", response_model=FinancialVarianceResponse)
async def calculate_variance(
    period_start: date = Query(...),
    period_end: date = Query(...),
    comparison: VarianceComparison = Query(...),
    dimension_id: str | None = Query(None),
    dimension_value_id: str | None = Query(None),
    budget_id: str | None = Query(None),
    scenario_id: str | None = Query(None),
    service: FinancialVarianceService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("professional_reporting:read")),
) -> FinancialVarianceResponse:
    return await service.calculate(
        tenant.organization_id,
        period_start,
        period_end,
        comparison,
        dimension_id=dimension_id,
        dimension_value_id=dimension_value_id,
        budget_id=budget_id,
        scenario_id=scenario_id,
    )
