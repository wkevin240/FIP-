from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.financial_calculation import (
    ProfitabilityMappingCreate,
    ProfitabilityMappingResponse,
    ProfitabilityResponse,
)
from app.services.accounting.financial_calculation_service import (
    FinancialCalculationService,
)
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> FinancialCalculationService:
    return FinancialCalculationService(session)


@router.post(
    "/profitability-mappings",
    response_model=ProfitabilityMappingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_profitability_mapping(
    data: ProfitabilityMappingCreate,
    service: FinancialCalculationService = Depends(get_service),
    tenant: CurrentTenant = Depends(
        require_permission("professional_reporting:configure")
    ),
) -> ProfitabilityMappingResponse:
    return await service.create_mapping(tenant.organization_id, tenant.user_id, data)


@router.get(
    "/profitability-mappings",
    response_model=list[ProfitabilityMappingResponse],
)
async def list_profitability_mappings(
    service: FinancialCalculationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("professional_reporting:read")),
) -> list[ProfitabilityMappingResponse]:
    return await service.list_mappings(tenant.organization_id)


@router.get("/profitability", response_model=ProfitabilityResponse)
async def calculate_profitability(
    period_start: date = Query(...),
    period_end: date = Query(...),
    service: FinancialCalculationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("professional_reporting:read")),
) -> ProfitabilityResponse:
    return await service.profitability(tenant.organization_id, period_start, period_end)
