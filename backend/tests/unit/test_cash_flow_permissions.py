from app.core.enums.users import MembershipRole
from app.services.permission_service import PermissionService


def test_cash_flow_permissions_follow_least_privilege() -> None:
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "cash_flow:read"
    )
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "cash_flow:configure"
    )
    for role in (MembershipRole.MANAGER.value, MembershipRole.AUDITOR.value):
        assert PermissionService.role_allows(role, "cash_flow:read")
        assert not PermissionService.role_allows(role, "cash_flow:configure")
    assert not PermissionService.role_allows(
        MembershipRole.USER.value, "cash_flow:read"
    )
