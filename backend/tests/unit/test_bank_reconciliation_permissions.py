from app.services.permission_service import PermissionService


def test_bank_reconciliation_match_is_limited_to_accountant_roles() -> None:
    assert (
        PermissionService.role_allows("ACCOUNTANT", "bank_reconciliation:match") is True
    )
    for role in ("MANAGER", "USER", "AUDITOR"):
        assert PermissionService.role_allows(role, "bank_reconciliation:match") is False
