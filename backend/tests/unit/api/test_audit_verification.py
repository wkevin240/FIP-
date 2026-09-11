from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.audit import verify_audit_chain


@pytest.mark.asyncio
async def test_verify_audit_chain_is_tenant_scoped_and_returns_verification_result() -> None:
    tenant = SimpleNamespace(organization_id="org-42")
    repository = SimpleNamespace(
        list_for_organization=AsyncMock(return_value=[object(), object()]),
        verify_organization_chain=AsyncMock(return_value=True),
    )

    with patch("app.api.v1.audit.AuditLogRepository", return_value=repository):
        result = await verify_audit_chain(tenant=tenant, db=object())

    assert result.organization_id == "org-42"
    assert result.valid is True
    assert result.record_count == 2
    repository.list_for_organization.assert_awaited_once_with("org-42")
    repository.verify_organization_chain.assert_awaited_once_with("org-42")
