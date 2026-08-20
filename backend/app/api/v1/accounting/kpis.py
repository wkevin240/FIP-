from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.kpi import KPIResponse
from app.services.accounting.kpi_service import KPIService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> KPIService:
    return KPIService(session)


@router.get("", response_model=KPIResponse)
async def calculate_kpis(
    fiscal_period_id: str | None = Query(default=None),
    service: KPIService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("kpi:read")),
) -> KPIResponse:
    return await service.calculate(tenant.organization_id, fiscal_period_id)
