from decimal import Decimal

import pytest
from app.core.enums.users import MembershipRole
from app.schemas.accounting.forecast import ForecastLineResponse
from app.services.permission_service import PermissionService


def test_forecast_formula_is_decimal_and_reconciled():
    line = ForecastLineResponse(
        budget_id="budget-real",
        scenario_id="scenario-real",
        fiscal_period_id="period-real",
        account_id="account-real",
        dimension_value_id=None,
        actual_amount=Decimal("100.10"),
        approved_budget_amount=Decimal("50.00"),
        scenario_assumption_amount=Decimal("-10.10"),
        forecast_amount=Decimal("140.00"),
        status="READY",
    )
    assert line.forecast_amount == Decimal("140.00")
    with pytest.raises(ValueError):
        ForecastLineResponse(
            budget_id="budget-real",
            scenario_id="scenario-real",
            fiscal_period_id="period-real",
            account_id="account-real",
            dimension_value_id=None,
            actual_amount=Decimal("100.10"),
            approved_budget_amount=Decimal("50.00"),
            scenario_assumption_amount=Decimal("-10.10"),
            forecast_amount=Decimal("140.01"),
            status="READY",
        )


def test_forecast_read_is_available_without_mutation_permissions():
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "forecast:read"
    )
    assert PermissionService.role_allows(MembershipRole.MANAGER.value, "forecast:read")
    assert PermissionService.role_allows(MembershipRole.AUDITOR.value, "forecast:read")
    assert not PermissionService.role_allows(
        MembershipRole.MANAGER.value, "forecast:update"
    )
