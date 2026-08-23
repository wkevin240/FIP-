from decimal import Decimal

from app.core.enums.users import MembershipRole
from app.schemas.accounting.closing_readiness import ClosingReadinessResponse
from app.services.permission_service import PermissionService


def test_closing_readiness_response_preserves_decimal_totals():
    result = ClosingReadinessResponse(
        organization_id="org-real",
        fiscal_year_id="year-real",
        fiscal_year_status="OPEN",
        fiscal_period_count=1,
        open_period_count=0,
        locked_period_count=0,
        draft_journal_entry_count=0,
        unresolved_banking_exception_count=0,
        unclosed_statement_count=0,
        missing_period_closing_count=0,
        total_posted_debit=Decimal("100.00"),
        total_posted_credit=Decimal("100.00"),
        status="READY",
        blockers=[],
    )
    assert result.total_posted_debit == result.total_posted_credit
    assert result.status == "READY"


def test_closing_readiness_is_read_only_and_rbac_scoped():
    for role in (
        MembershipRole.ACCOUNTANT,
        MembershipRole.MANAGER,
        MembershipRole.AUDITOR,
    ):
        assert PermissionService.role_allows(role.value, "closing_readiness:read")
    assert not PermissionService.role_allows(
        MembershipRole.USER.value, "closing_readiness:read"
    )
