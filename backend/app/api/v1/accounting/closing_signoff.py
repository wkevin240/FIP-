from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.closing_signoff import ClosingSignoffResponse
from app.services.accounting.closing_signoff_service import ClosingSignoffService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> ClosingSignoffService:
    return ClosingSignoffService(session)


@router.get(
    "/{fiscal_year_id}",
    response_model=ClosingSignoffResponse,
)
async def get_closing_signoff(
    fiscal_year_id: str,
    service: ClosingSignoffService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("closing_signoff:read")),
) -> ClosingSignoffResponse:
    return await service.get(tenant.organization_id, fiscal_year_id)


@router.post(
    "/{fiscal_year_id}/periods/{fiscal_period_id}",
    response_model=ClosingSignoffResponse,
    status_code=status.HTTP_201_CREATED,
)
async def sign_closing_year(
    fiscal_year_id: str,
    fiscal_period_id: str,
    service: ClosingSignoffService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("closing_signoff:create")),
) -> ClosingSignoffResponse:
    return await service.sign(
        tenant.organization_id,
        fiscal_year_id,
        fiscal_period_id,
        tenant.user_id,
    )
