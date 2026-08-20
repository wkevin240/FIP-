from decimal import Decimal

import pytest
from app.core.enums.users import MembershipRole
from app.schemas.accounting.scenario import (
    ScenarioAssumptionCreate,
    ScenarioStatusResponse,
)
from app.services.permission_service import PermissionService


def test_scenario_rbac_is_least_privilege():
    assert PermissionService.role_allows(MembershipRole.ACCOUNTANT.value, "scenario:create")
    assert PermissionService.role_allows(MembershipRole.ACCOUNTANT.value, "scenario:update")
    assert PermissionService.role_allows(MembershipRole.ACCOUNTANT.value, "scenario:approve")
    assert PermissionService.role_allows(MembershipRole.MANAGER.value, "scenario:read")
    assert PermissionService.role_allows(MembershipRole.AUDITOR.value, "scenario:read")
    assert not PermissionService.role_allows(MembershipRole.MANAGER.value, "scenario:approve")
    assert not PermissionService.role_allows(MembershipRole.AUDITOR.value, "scenario:update")


def test_scenario_assumption_rejects_zero_and_preserves_decimal():
    assumption = ScenarioAssumptionCreate(
        fiscal_period_id="period-real",
        account_id="account-real",
        amount=Decimal("125.10"),
        rationale="Validated operating assumption",
    )
    assert assumption.amount == Decimal("125.10")
    with pytest.raises(ValueError):
        ScenarioAssumptionCreate(
            fiscal_period_id="period-real",
            account_id="account-real",
            amount=Decimal("0.00"),
            rationale="invalid",
        )


def test_scenario_status_is_not_ready_without_approved_assumptions():
    status = ScenarioStatusResponse(
        scenario_id="scenario-real",
        status="DRAFT",
        assumption_count=0,
        ready=False,
    )
    assert status.ready is False
