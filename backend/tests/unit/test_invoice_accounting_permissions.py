from app.services.permission_service import PermissionService


def test_invoice_accounting_permissions_are_limited_to_accountant_roles() -> None:
    assert PermissionService.role_allows("ACCOUNTANT", "invoice:post") is True
    assert (
        PermissionService.role_allows("ACCOUNTANT", "invoice:accounting:configure")
        is True
    )
    for role in ("MANAGER", "USER", "AUDITOR"):
        assert PermissionService.role_allows(role, "invoice:post") is False
        assert (
            PermissionService.role_allows(role, "invoice:accounting:configure") is False
        )
