from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.scenario import (
    ScenarioAssumptionCreate,
    ScenarioAssumptionResponse,
    ScenarioCreate,
    ScenarioResponse,
    ScenarioStatusResponse,
)
from app.services.accounting.scenario_service import ScenarioService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> ScenarioService:
    return ScenarioService(session)


@router.post("", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    data: ScenarioCreate,
    service: ScenarioService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("scenario:create")),
) -> ScenarioResponse:
    return await service.create(tenant.organization_id, tenant.user_id, data)


@router.post(
    "/{scenario_id}/assumptions",
    response_model=ScenarioAssumptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_assumption(
    scenario_id: str,
    data: ScenarioAssumptionCreate,
    service: ScenarioService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("scenario:update")),
) -> ScenarioAssumptionResponse:
    return await service.add_assumption(
        tenant.organization_id, tenant.user_id, scenario_id, data
    )


@router.post("/{scenario_id}/approve", response_model=ScenarioResponse)
async def approve_scenario(
    scenario_id: str,
    service: ScenarioService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("scenario:approve")),
) -> ScenarioResponse:
    return await service.approve(tenant.organization_id, tenant.user_id, scenario_id)


@router.get("/{scenario_id}/status", response_model=ScenarioStatusResponse)
async def scenario_status(
    scenario_id: str,
    service: ScenarioService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("scenario:read")),
) -> ScenarioStatusResponse:
    return await service.status(tenant.organization_id, scenario_id)
