from app.core.enums.users import MembershipRole
from app.services.permission_service import PermissionService


def test_accountant_can_operate_supplier_invoices() -> None:
    role = MembershipRole.ACCOUNTANT.value
    for permission in (
        "supplier_invoice:create",
        "supplier_invoice:read",
        "supplier_invoice:update",
        "supplier_invoice:approve",
        "supplier_invoice:cancel",
    ):
        assert PermissionService.role_allows(role, permission)


def test_manager_can_review_but_not_create_or_edit_supplier_invoices() -> None:
    role = MembershipRole.MANAGER.value
    assert PermissionService.role_allows(role, "supplier_invoice:read")
    assert PermissionService.role_allows(role, "supplier_invoice:approve")
    assert PermissionService.role_allows(role, "supplier_invoice:cancel")
    assert not PermissionService.role_allows(role, "supplier_invoice:create")
    assert not PermissionService.role_allows(role, "supplier_invoice:update")


def test_auditor_is_read_only_for_supplier_invoices() -> None:
    role = MembershipRole.AUDITOR.value
    assert PermissionService.role_allows(role, "supplier_invoice:read")
    assert not PermissionService.role_allows(role, "supplier_invoice:approve")
    assert not PermissionService.role_allows(role, "supplier_invoice:cancel")


def test_unknown_role_fails_closed_for_supplier_invoice_permissions() -> None:
    for permission in (
        "supplier_invoice:create",
        "supplier_invoice:read",
        "supplier_invoice:update",
        "supplier_invoice:approve",
        "supplier_invoice:cancel",
    ):
        assert not PermissionService.role_allows("UNKNOWN_ROLE", permission)
