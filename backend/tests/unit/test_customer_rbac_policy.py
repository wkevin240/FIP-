from app.core.enums.users import MembershipRole
from app.services.permission_service import PermissionService


def test_accountant_can_create_update_and_read_customers() -> None:
    role = MembershipRole.ACCOUNTANT.value
    assert PermissionService.role_allows(role, "customer:create")
    assert PermissionService.role_allows(role, "customer:update")
    assert PermissionService.role_allows(role, "customer:read")


def test_manager_and_auditor_can_read_but_not_mutate_customers() -> None:
    for role in (MembershipRole.MANAGER.value, MembershipRole.AUDITOR.value):
        assert PermissionService.role_allows(role, "customer:read")
        assert not PermissionService.role_allows(role, "customer:create")
        assert not PermissionService.role_allows(role, "customer:update")


def test_unknown_role_fails_closed_for_customer_permissions() -> None:
    for permission in ("customer:create", "customer:read", "customer:update"):
        assert not PermissionService.role_allows("UNKNOWN_ROLE", permission)
