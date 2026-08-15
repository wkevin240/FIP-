from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.cash_flow import (
    CashFlowAccountMappingCreate,
    CashFlowAccountMappingResponse,
    CashFlowStatementResponse,
)
from app.services.accounting.cash_flow_configuration_service import (
    CashFlowConfigurationService,
)
from app.services.accounting.cash_flow_service import CashFlowService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_configuration_service(
    session: AsyncSession = Depends(get_db),
) -> CashFlowConfigurationService:
    return CashFlowConfigurationService(session)


async def get_cash_flow_service(
    session: AsyncSession = Depends(get_db),
) -> CashFlowService:
    return CashFlowService(session)


@router.post(
    "/mappings",
    response_model=CashFlowAccountMappingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_cash_flow_mapping(
    data: CashFlowAccountMappingCreate,
    service: CashFlowConfigurationService = Depends(get_configuration_service),
    tenant: CurrentTenant = Depends(require_permission("cash_flow:configure")),
) -> CashFlowAccountMappingResponse:
    return await service.create(tenant.organization_id, tenant.user_id, data)


@router.get("/mappings", response_model=list[CashFlowAccountMappingResponse])
async def list_cash_flow_mappings(
    service: CashFlowConfigurationService = Depends(get_configuration_service),
    tenant: CurrentTenant = Depends(require_permission("cash_flow:read")),
) -> list[CashFlowAccountMappingResponse]:
    return await service.list_active(tenant.organization_id)


@router.get("/statement", response_model=CashFlowStatementResponse)
async def get_cash_flow_statement(
    start_date: date = Query(...),
    end_date: date = Query(...),
    service: CashFlowService = Depends(get_cash_flow_service),
    tenant: CurrentTenant = Depends(require_permission("cash_flow:read")),
) -> CashFlowStatementResponse:
    return await service.statement(tenant.organization_id, start_date, end_date)
