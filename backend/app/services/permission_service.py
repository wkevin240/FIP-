"""Small, explicit RBAC policy used by the API and application services."""

from app.core.enums.users import MembershipRole


class PermissionService:
    _ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
        MembershipRole.OWNER.value: frozenset({"*"}),
        MembershipRole.ADMIN.value: frozenset({"*"}),
        MembershipRole.ACCOUNTANT.value: frozenset({
            "account:create", "account:read", "account:update",
            "fiscal_year:create", "fiscal_year:read", "fiscal_year:update",
            "fiscal_period:create", "fiscal_period:read", "fiscal_period:update",
            "journal:create", "journal:read", "journal:update",
            "journal_entry:create", "journal_entry:read", "journal_entry:update", "journal_entry:post",
            "ledger:read",
            "profitability_mapping:create", "profitability_mapping:read",
            "balance_sheet_mapping:create", "balance_sheet_mapping:read",
            "customer:create", "customer:read", "customer:update",
            "customer_invoice:create", "customer_invoice:read", "customer_invoice:update", "customer_invoice:issue",
        }),
        MembershipRole.MANAGER.value: frozenset({
            "account:read", "fiscal_year:read", "fiscal_period:read",
            "journal:read", "journal_entry:read", "ledger:read",
            "profitability_mapping:read", "balance_sheet_mapping:read",
            "customer:read",
            "customer_invoice:read",
        }),
        MembershipRole.USER.value: frozenset(),
        MembershipRole.AUDITOR.value: frozenset({
            "account:read", "fiscal_year:read", "fiscal_period:read",
            "journal:read", "journal_entry:read", "ledger:read",
            "profitability_mapping:read", "balance_sheet_mapping:read", "audit:read",
            "customer:read",
            "customer_invoice:read",
        }),
    }

    @classmethod
    def role_allows(cls, role: str, permission: str, is_superuser: bool = False) -> bool:
        """Evaluate a permission while tolerating lowercase role values from identity context."""
        normalized_role = role.upper() if isinstance(role, str) else role
        allowed = cls._ROLE_PERMISSIONS.get(normalized_role, frozenset())
        return is_superuser or "*" in allowed or permission in allowed

