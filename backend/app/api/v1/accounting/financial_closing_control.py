from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.financial_closing_control import (
    FinancialClosingControlResponse,
)
from app.services.accounting.financial_closing_control_service import (
    FinancialClosingControlService,
)
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> FinancialClosingControlService:
    return FinancialClosingControlService(session)


@router.get(
    "/{fiscal_year_id}/periods/{fiscal_period_id}",
    response_model=FinancialClosingControlResponse,
)
async def assess_financial_closing_control(
    fiscal_year_id: str,
    fiscal_period_id: str,
    service: FinancialClosingControlService = Depends(get_service),
    tenant: CurrentTenant = Depends(
        require_permission("financial_closing_control:read")
    ),
) -> FinancialClosingControlResponse:
    return await service.assess(
        tenant.organization_id,
        fiscal_year_id,
        fiscal_period_id,
    )
