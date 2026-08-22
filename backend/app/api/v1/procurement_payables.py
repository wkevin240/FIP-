from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.procurement_payables import PayableStatementResponse
from app.services.procurement_payable_service import PayableService

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> PayableService:
    return PayableService(session)


@router.get("/statement", response_model=PayableStatementResponse)
async def payable_statement(
    as_of_date: date = Query(...),
    supplier_id: str | None = Query(default=None),
    service: PayableService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payable:read")),
) -> PayableStatementResponse:
    return await service.statement(tenant.organization_id, as_of_date, supplier_id)
