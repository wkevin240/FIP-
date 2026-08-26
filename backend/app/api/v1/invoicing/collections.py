from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.invoicing.collections import CollectionSummary
from app.services.invoicing.collection_service import CollectionService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/snapshot", response_model=CollectionSummary)
async def collection_snapshot(
    as_of: date = Query(default_factory=date.today),
    customer_name: str | None = Query(None, min_length=1, max_length=255),
    overdue_only: bool = Query(False),
    tenant: CurrentTenant = Depends(require_permission("collection:read")),
    session: AsyncSession = Depends(get_db),
) -> CollectionSummary:
    return await CollectionService(session).snapshot(
        organization_id=tenant.organization_id,
        as_of=as_of,
        customer_name=customer_name,
        overdue_only=overdue_only,
    )
