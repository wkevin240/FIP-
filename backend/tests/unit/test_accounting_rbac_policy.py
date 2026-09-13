from app.core.enums.users import MembershipRole
from app.services.permission_service import PermissionService


ACCOUNTING_READ_PERMISSIONS = (
    "account:read",
    "fiscal_year:read",
    "fiscal_period:read",
    "journal:read",
    "journal_entry:read",
    "ledger:read",
)


CRITICAL_ACCOUNTING_MUTATIONS = (
    "journal_entry:create",
    "journal_entry:update",
    "journal_entry:post",
    "journal_entry:reverse",
    "fiscal_period:close",
    "fiscal_period:reopen",
)


def test_accountant_can_create_and_post_but_not_reverse_or_close() -> None:
    role = MembershipRole.ACCOUNTANT.value

    assert PermissionService.role_allows(role, "journal_entry:create")
    assert PermissionService.role_allows(role, "journal_entry:post")
    assert not PermissionService.role_allows(role, "journal_entry:reverse")
    assert not PermissionService.role_allows(role, "fiscal_period:close")
    assert not PermissionService.role_allows(role, "fiscal_period:reopen")


def test_manager_and_auditor_are_read_only_for_core_accounting_lifecycle() -> None:
    for role in (MembershipRole.MANAGER.value, MembershipRole.AUDITOR.value):
        for permission in ACCOUNTING_READ_PERMISSIONS:
            assert PermissionService.role_allows(role, permission)
        for permission in CRITICAL_ACCOUNTING_MUTATIONS:
            assert not PermissionService.role_allows(role, permission)


def test_owner_and_admin_retain_explicit_administrative_override() -> None:
    for role in (MembershipRole.OWNER.value, MembershipRole.ADMIN.value):
        for permission in CRITICAL_ACCOUNTING_MUTATIONS:
            assert PermissionService.role_allows(role, permission)


def test_unknown_role_fails_closed() -> None:
    for permission in ACCOUNTING_READ_PERMISSIONS + CRITICAL_ACCOUNTING_MUTATIONS:
        assert not PermissionService.role_allows("UNKNOWN_ROLE", permission)


def test_superuser_override_is_explicit() -> None:
    assert PermissionService.role_allows("UNKNOWN_ROLE", "journal_entry:reverse", is_superuser=True)
