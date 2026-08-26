from datetime import date
from typing import Annotated

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.control_center import FinancialControlCenterResponse
from app.services.accounting.control_center_service import (
    FinancialControlCenterService,
)
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> FinancialControlCenterService:
    return FinancialControlCenterService(session)


@router.get("/summary", response_model=FinancialControlCenterResponse)
async def get_control_center_summary(
    as_of_date: Annotated[date, Query()],
    service: FinancialControlCenterService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("financial_control:read")),
):
    return await service.summarize(tenant.organization_id, as_of_date)
