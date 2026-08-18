from decimal import Decimal

import pytest
from app.core.enums.users import MembershipRole
from app.schemas.accounting.analytical import AnalyticalActualResponse
from app.services.permission_service import PermissionService


def test_analytical_rbac_is_least_privilege():
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "analytical_dimension:create"
    )
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "analytical_allocation:create"
    )
    assert PermissionService.role_allows(
        MembershipRole.MANAGER.value, "analytical_report:read"
    )
    assert PermissionService.role_allows(
        MembershipRole.AUDITOR.value, "analytical_report:read"
    )
    assert not PermissionService.role_allows(
        MembershipRole.MANAGER.value, "analytical_allocation:create"
    )


def test_analytical_reconciliation_uses_decimal():
    result = AnalyticalActualResponse(
        dimension_id="dimension-real",
        dimension_value_id="value-real",
        account_id="account-real",
        fiscal_period_id="period-real",
        allocated_amount=Decimal("100.00"),
        ledger_amount=Decimal("100.00"),
        variance_to_ledger=Decimal("0.00"),
    )
    assert result.variance_to_ledger == Decimal("0.00")
    with pytest.raises(ValueError):
        AnalyticalActualResponse(
            dimension_id="dimension-real",
            dimension_value_id="value-real",
            account_id="account-real",
            fiscal_period_id="period-real",
            allocated_amount=Decimal("100.00"),
            ledger_amount=Decimal("99.99"),
            variance_to_ledger=Decimal("0.00"),
        )
