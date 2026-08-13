from app.core.enums.users import MembershipRole
from app.services.permission_service import PermissionService


def test_accountant_has_sensitive_payroll_permissions() -> None:
    for permission in (
        "payroll_employee:create",
        "payroll_contract:update",
        "payroll_rule_set:create",
        "payroll_period:calculate",
        "payroll_period:validate",
        "payroll_period:lock",
        "payroll_period:post",
        "payroll_correction:create",
    ):
        assert PermissionService.role_allows(
            MembershipRole.ACCOUNTANT.value, permission
        )


def test_manager_and_auditor_are_limited_to_payroll_read_permissions() -> None:
    for role in (MembershipRole.MANAGER.value, MembershipRole.AUDITOR.value):
        assert PermissionService.role_allows(role, "payroll_slip:read")
        assert PermissionService.role_allows(role, "payroll_audit:read")
        assert not PermissionService.role_allows(role, "payroll_period:post")
        assert not PermissionService.role_allows(role, "payroll_correction:create")
