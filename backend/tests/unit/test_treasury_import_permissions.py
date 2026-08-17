from app.services.permission_service import PermissionService


def test_treasury_statement_import_uses_transaction_create_permission() -> None:
    assert PermissionService.role_allows("ACCOUNTANT", "treasury_transaction:create")
    for role in ("MANAGER", "USER", "AUDITOR"):
        assert not PermissionService.role_allows(role, "treasury_transaction:create")
