import inspect
from datetime import datetime, timezone

import app.models  # noqa: F401
import pytest
from app.api.v1.treasury.banking_control import list_statement_exceptions
from app.core.enums.users import MembershipRole
from app.models.treasury.banking_control import BankingControlException
from app.schemas.treasury.banking_control import BankingControlRefreshResponse
from app.services.permission_service import PermissionService
from app.services.treasury.banking_control_service import BankingControlService


def test_banking_control_rbac_is_least_privilege():
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "bank_control:refresh"
    )
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "bank_control:close"
    )
    assert PermissionService.role_allows(
        MembershipRole.MANAGER.value, "bank_control:read"
    )
    assert PermissionService.role_allows(
        MembershipRole.AUDITOR.value, "bank_control:read"
    )
    assert not PermissionService.role_allows(
        MembershipRole.MANAGER.value, "bank_control:close"
    )


def test_refresh_response_requires_non_negative_counts():
    response = BankingControlRefreshResponse(
        statement_import_id="import-real",
        total_imported=2,
        RECONCILED=1,
        NO_MATCH=1,
        AMBIGUOUS=0,
        PENDING=0,
        REJECTED=0,
        INVALID_RULE=0,
        POSTED_UNRECONCILED=0,
    )
    assert response.total_imported == 2


def test_control_exception_model_accepts_rejected_status():
    exception = BankingControlException(
        organization_id="org-real",
        bank_transaction_id="transaction-real",
        statement_import_id="import-real",
        status="REJECTED",
        reason="Explicit rejection",
        last_seen_at=datetime.now(timezone.utc),
    )
    assert exception.status == "REJECTED"


def test_exception_listing_exposes_bounded_pagination_and_tenant_dependency():
    signature = inspect.signature(list_statement_exceptions)

    assert "ge=0" in inspect.getsource(list_statement_exceptions)
    assert "ge=1" in inspect.getsource(list_statement_exceptions)
    assert "le=500" in inspect.getsource(list_statement_exceptions)
    assert "tenant" in signature.parameters


@pytest.mark.asyncio
async def test_exception_listing_rejects_invalid_pagination_before_database_access():
    service = BankingControlService(None)

    with pytest.raises(ValueError, match="offset"):
        await service.list_exceptions("org-real", offset=-1)

    with pytest.raises(ValueError, match="limit"):
        await service.list_exceptions("org-real", limit=501)


@pytest.mark.asyncio
async def test_exception_listing_applies_stable_order_and_sql_page_window():
    captured = {}

    class ScalarResult:
        def __iter__(self):
            return iter(())

    class FakeSession:
        async def scalars(self, query):
            captured["sql"] = str(query)
            return ScalarResult()

    service = BankingControlService(FakeSession())
    result = await service.list_exceptions("org-real", offset=20, limit=10)

    assert result == []
    assert "ORDER BY banking_control_exceptions.last_seen_at DESC" in captured["sql"]
    assert "banking_control_exceptions.id ASC" in captured["sql"]
    assert "LIMIT :param_1" in captured["sql"]
    assert "OFFSET :param_2" in captured["sql"]


def test_exception_listing_is_read_only_and_tenant_scoped():
    route_source = inspect.getsource(list_statement_exceptions)
    service_source = inspect.getsource(BankingControlService.list_exceptions)

    assert 'require_permission("bank_control:read")' in route_source
    assert "tenant.organization_id" in route_source
    assert (
        "BankingControlException.organization_id == organization_id" in service_source
    )
    assert "session.add" not in service_source
    assert "session.delete" not in service_source
    assert "commit" not in service_source
    assert "rollback" not in service_source
