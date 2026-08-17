from app.services.permission_service import PermissionService


def test_invoice_accounting_permissions_are_limited_to_accountant_roles() -> None:
    accountant_permissions = (
        "invoice:post",
        "invoice:accounting:configure",
        "credit_note:post",
        "payment:post",
    )
    for permission in accountant_permissions:
        assert PermissionService.role_allows("ACCOUNTANT", permission) is True
    for role in ("MANAGER", "USER", "AUDITOR"):
        for permission in accountant_permissions:
            assert PermissionService.role_allows(role, permission) is False
