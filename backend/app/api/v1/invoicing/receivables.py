from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.invoicing.payment import ReceivableStatementResponse
from app.services.invoicing.receivable_service import ReceivableService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> ReceivableService:
    return ReceivableService(session)


@router.get("/statement", response_model=ReceivableStatementResponse)
async def receivable_statement(
    as_of_date: date = Query(...),
    customer_key: str | None = Query(default=None),
    service: ReceivableService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("receivable:read")),
) -> ReceivableStatementResponse:
    return await service.statement(tenant.organization_id, as_of_date, customer_key)
