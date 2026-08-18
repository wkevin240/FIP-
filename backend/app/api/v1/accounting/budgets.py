from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.budget import (
    BudgetCreate,
    BudgetLineCreate,
    BudgetLineResponse,
    BudgetResponse,
    BudgetVarianceResponse,
)
from app.services.accounting.budget_service import BudgetService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> BudgetService:
    return BudgetService(session)


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
async def create_budget(
    data: BudgetCreate,
    service: BudgetService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("budget:create")),
) -> BudgetResponse:
    return await service.create_budget(tenant.organization_id, tenant.user_id, data)


@router.post(
    "/{budget_id}/lines",
    response_model=BudgetLineResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_budget_line(
    budget_id: str,
    data: BudgetLineCreate,
    service: BudgetService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("budget:update")),
) -> BudgetLineResponse:
    return await service.add_line(
        tenant.organization_id, tenant.user_id, budget_id, data
    )


@router.post("/{budget_id}/approve", response_model=BudgetResponse)
async def approve_budget(
    budget_id: str,
    service: BudgetService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("budget:approve")),
) -> BudgetResponse:
    return await service.approve(tenant.organization_id, tenant.user_id, budget_id)


@router.get("/{budget_id}/variance", response_model=list[BudgetVarianceResponse])
async def budget_variance(
    budget_id: str,
    period_id: str | None = Query(default=None),
    account_id: str | None = Query(default=None),
    service: BudgetService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("budget:read")),
) -> list[BudgetVarianceResponse]:
    return await service.variance(
        tenant.organization_id, budget_id, period_id, account_id
    )
