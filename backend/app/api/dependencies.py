"""Authentication, tenant resolution and permission dependencies."""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.membership import OrganizationMembership
from app.models.user import User
from app.services.permission_service import PermissionService

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentTenant:
    user_id: str
    organization_id: str
    role: str
    is_superuser: bool


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> CurrentTenant:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = await session.scalar(select(User).where(User.id == payload["sub"], User.is_active.is_(True)))
    membership = await session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == payload["sub"],
            OrganizationMembership.organization_id == payload["org"],
            OrganizationMembership.is_active.is_(True),
        )
    )
    if user is None or membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant access denied")
    return CurrentTenant(user.id, membership.organization_id, membership.role, user.is_superuser)


def require_permission(permission: str):
    async def dependency(tenant: CurrentTenant = Depends(get_current_tenant)) -> CurrentTenant:
        if not PermissionService.role_allows(tenant.role, permission, tenant.is_superuser):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return tenant

    return dependency
