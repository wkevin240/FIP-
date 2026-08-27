from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.closing_readiness import ClosingReadinessResponse
from app.services.accounting.closing_readiness_service import ClosingReadinessService
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> ClosingReadinessService:
    return ClosingReadinessService(session)


@router.get("/{fiscal_year_id}", response_model=ClosingReadinessResponse)
async def assess_closing_readiness(
    fiscal_year_id: str,
    service: ClosingReadinessService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("closing_readiness:read")),
) -> ClosingReadinessResponse:
    try:
        return await service.assess(tenant.organization_id, fiscal_year_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
