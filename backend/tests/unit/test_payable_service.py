from datetime import date
from decimal import Decimal

from app.core.enums.users import MembershipRole
from app.services.permission_service import PermissionService
from app.services.procurement_payable_service import PayableService


def test_payable_ageing_uses_reporting_date_and_due_date():
    as_of = date(2026, 8, 20)
    assert PayableService._age(date(2026, 8, 20), as_of, Decimal("100.00")) == (
        "CURRENT",
        Decimal("0.00"),
    )
    assert PayableService._age(date(2026, 8, 1), as_of, Decimal("100.00")) == (
        "1-30",
        Decimal("100.00"),
    )
    assert PayableService._age(date(2026, 6, 1), as_of, Decimal("100.00")) == (
        "61-90",
        Decimal("100.00"),
    )
    assert PayableService._age(None, as_of, Decimal("100.00")) == (
        "CURRENT",
        Decimal("0.00"),
    )
    assert PayableService._age(date(2026, 8, 1), as_of, Decimal("0.00")) == (
        None,
        Decimal("0.00"),
    )


def test_payable_read_permission_is_explicit():
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "payable:read"
    )
    assert PermissionService.role_allows(MembershipRole.MANAGER.value, "payable:read")
    assert PermissionService.role_allows(MembershipRole.AUDITOR.value, "payable:read")
    assert not PermissionService.role_allows(MembershipRole.USER.value, "payable:read")
