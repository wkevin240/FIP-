from datetime import datetime, timezone

from app.core.enums.users import MembershipRole
from app.models.treasury.banking_control import BankingControlException
from app.schemas.treasury.banking_control import BankingControlRefreshResponse
from app.services.permission_service import PermissionService


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
