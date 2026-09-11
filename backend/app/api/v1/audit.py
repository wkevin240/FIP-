from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.repositories.audit.audit_log_repository import AuditLogRepository
from app.schemas.audit import AuditChainVerificationResponse

router = APIRouter()


@router.get("/verify", response_model=AuditChainVerificationResponse)
async def verify_audit_chain(
    tenant: CurrentTenant = Depends(require_permission("audit:read")),
    db: AsyncSession = Depends(get_db),
) -> AuditChainVerificationResponse:
    repository = AuditLogRepository(db)
    records = await repository.list_for_organization(tenant.organization_id)
    valid = await repository.verify_organization_chain(tenant.organization_id)
    return AuditChainVerificationResponse(
        organization_id=tenant.organization_id,
        valid=valid,
        record_count=len(records),
    )
