from app.services.permission_service import PermissionService


def test_bank_rule_permissions_are_explicitly_role_scoped() -> None:
    for permission in (
        "bank_rule:create",
        "bank_rule:read",
        "bank_rule:update",
        "bank_transaction:propose",
        "bank_transaction:validate_accounting",
    ):
        assert PermissionService.role_allows("ACCOUNTANT", permission)

    assert PermissionService.role_allows("MANAGER", "bank_rule:read")
    assert PermissionService.role_allows("AUDITOR", "bank_rule:read")
    for role in ("MANAGER", "AUDITOR", "USER"):
        for permission in (
            "bank_rule:create",
            "bank_rule:update",
            "bank_transaction:propose",
            "bank_transaction:validate_accounting",
        ):
            assert not PermissionService.role_allows(role, permission)
