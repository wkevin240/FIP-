from datetime import datetime

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.audit.audit_event import (
    AuditEventPage,
    AuditIntegrityCheck,
)
from app.services.audit.audit_service import AuditService
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> AuditService:
    return AuditService(session)


@router.get("/events", response_model=AuditEventPage)
async def list_audit_events(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    resource_id: str | None = Query(None),
    actor_user_id: str | None = Query(None),
    transaction_id: str | None = Query(None),
    occurred_from: datetime | None = Query(None),
    occurred_to: datetime | None = Query(None),
    service: AuditService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("audit_event:read")),
) -> AuditEventPage:
    items = await service.list_events(
        tenant.organization_id,
        offset,
        limit,
        action,
        resource_type,
        resource_id,
        actor_user_id,
        transaction_id,
        occurred_from,
        occurred_to,
    )
    return AuditEventPage(offset=offset, limit=limit, items=items)


@router.get("/integrity", response_model=AuditIntegrityCheck)
async def verify_audit_integrity(
    service: AuditService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("audit_event:verify")),
) -> AuditIntegrityCheck:
    return await service.verify_integrity(tenant.organization_id)
