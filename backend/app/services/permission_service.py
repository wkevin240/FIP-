"""Small, explicit RBAC policy used by the API and application services."""

from typing import ClassVar

from app.core.enums.users import MembershipRole


class PermissionService:
    _ROLE_PERMISSIONS: ClassVar[dict[str, frozenset[str]]] = {
        MembershipRole.OWNER.value: frozenset({"*"}),
        MembershipRole.ADMIN.value: frozenset({"*"}),
        MembershipRole.ACCOUNTANT.value: frozenset(
            {
                "account:create",
                "account:read",
                "account:update",
                "fiscal_year:create",
                "fiscal_year:read",
                "fiscal_year:update",
                "fiscal_period:create",
                "fiscal_period:read",
                "fiscal_period:update",
                "fiscal_period:close",
                "journal:create",
                "journal:read",
                "journal:update",
                "journal_entry:create",
                "journal_entry:read",
                "journal_entry:update",
                "journal_entry:post",
            }
        ),
        MembershipRole.MANAGER.value: frozenset(
            {
                "account:read",
                "fiscal_year:read",
                "fiscal_period:read",
                "journal:read",
                "journal_entry:read",
            }
        ),
        MembershipRole.USER.value: frozenset(),
        MembershipRole.AUDITOR.value: frozenset(
            {
                "account:read",
                "fiscal_year:read",
                "fiscal_period:read",
                "journal:read",
                "journal_entry:read",
                "audit:read",
            }
        ),
    }

    @classmethod
    def role_allows(
        cls, role: str, permission: str, is_superuser: bool = False
    ) -> bool:
        allowed = cls._ROLE_PERMISSIONS.get(role, frozenset())
        return is_superuser or "*" in allowed or permission in allowed
