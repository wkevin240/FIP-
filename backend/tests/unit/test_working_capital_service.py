from datetime import date
from decimal import Decimal

import pytest
from app.core.enums.users import MembershipRole
from app.services.accounting.working_capital_service import WorkingCapitalService
from app.services.permission_service import PermissionService


def test_working_capital_days_are_decimal_and_deterministic():
    metric = WorkingCapitalService._days_metric(
        "DSO", Decimal("100.00"), Decimal("1_000.00"), "customer invoices"
    )
    assert metric.status == "READY"
    assert metric.value == Decimal("36.50")
    empty = WorkingCapitalService._days_metric(
        "DPO", Decimal("100.00"), Decimal("0.00"), "supplier invoices"
    )
    assert empty.status == "NOT_READY"
    assert empty.value is None


def test_working_capital_rejects_inverted_dates():
    with pytest.raises(ValueError, match="period_start"):
        WorkingCapitalService._validate_dates(date(2026, 8, 20), date(2026, 8, 1))


def test_working_capital_rbac_is_read_only():
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "working_capital:read"
    )
    assert PermissionService.role_allows(
        MembershipRole.MANAGER.value, "working_capital:read"
    )
    assert PermissionService.role_allows(
        MembershipRole.AUDITOR.value, "working_capital:read"
    )
    assert not PermissionService.role_allows(
        MembershipRole.USER.value, "working_capital:read"
    )
