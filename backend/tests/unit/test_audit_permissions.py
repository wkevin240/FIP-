from app.core.enums.users import MembershipRole
from app.services.permission_service import PermissionService


def test_audit_permissions_are_read_only_for_non_administrative_roles() -> None:
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "audit_event:read"
    )
    assert PermissionService.role_allows(
        MembershipRole.MANAGER.value, "audit_event:read"
    )
    assert PermissionService.role_allows(
        MembershipRole.AUDITOR.value, "audit_event:read"
    )
    assert not PermissionService.role_allows(
        MembershipRole.MANAGER.value, "audit_event:verify"
    )
    assert not PermissionService.role_allows(
        MembershipRole.USER.value, "audit_event:read"
    )


def test_auditor_can_verify_but_not_mutate_audit_events() -> None:
    assert PermissionService.role_allows(
        MembershipRole.AUDITOR.value, "audit_event:verify"
    )
    assert not PermissionService.role_allows(
        MembershipRole.AUDITOR.value, "audit_event:update"
    )
    assert not PermissionService.role_allows(
        MembershipRole.AUDITOR.value, "audit_event:delete"
    )
