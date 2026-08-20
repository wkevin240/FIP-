from decimal import Decimal

import pytest
from app.core.enums.users import MembershipRole
from app.schemas.accounting.budget import BudgetVarianceResponse
from app.services.permission_service import PermissionService


def test_budget_rbac_is_least_privilege():
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "budget:create"
    )
    assert PermissionService.role_allows(
        MembershipRole.ACCOUNTANT.value, "budget:approve"
    )
    assert PermissionService.role_allows(MembershipRole.MANAGER.value, "budget:read")
    assert PermissionService.role_allows(MembershipRole.AUDITOR.value, "budget:read")
    assert not PermissionService.role_allows(
        MembershipRole.MANAGER.value, "budget:approve"
    )


def test_budget_variance_is_decimal_and_balanced():
    result = BudgetVarianceResponse(
        budget_id="budget-real",
        fiscal_period_id="period-real",
        account_id="account-real",
        budget_amount=Decimal("1000.00"),
        actual_amount=Decimal("275.35"),
        variance_amount=Decimal("724.65"),
    )
    assert result.variance_amount == Decimal("724.65")
    with pytest.raises(ValueError):
        BudgetVarianceResponse(
            budget_id="budget-real",
            fiscal_period_id="period-real",
            account_id="account-real",
            budget_amount=Decimal("1000.00"),
            actual_amount=Decimal("275.35"),
            variance_amount=Decimal("724.64"),
        )
