from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.api.dependencies import CurrentTenant
from app.api.v1.accounting.profitability import profitability_report
from app.domain.calculation.contracts import (
    CalculationContext,
    CalculationDefinition,
    CalculationResult,
)
from app.services.accounting.profitability_service import LedgerProfitabilityIntegrityError


class StubProfitabilityService:
    def __init__(self, results=None, error=None):
        self.results = results or {}
        self.error = error
        self.contexts = []

    async def calculate_from_persisted_mappings(self, context, *, fiscal_period_id=None):
        self.contexts.append((context, fiscal_period_id))
        if self.error is not None:
            raise self.error
        return self.results


@pytest.mark.asyncio
async def test_profitability_report_uses_authenticated_tenant_context():
    tenant = CurrentTenant(
        user_id="user-1",
        organization_id="org-authenticated",
        role="accountant",
        is_superuser=False,
    )
    context = CalculationContext(
        organization_id="org-authenticated",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        rule_version="2026.1",
    )
    definition = CalculationDefinition(
        code="GROSS_PROFIT",
        formula="REVENUE - COGS",
        dependencies=("REVENUE", "COGS"),
        rule_version="2026.1",
    )
    result = CalculationResult.ready(definition, context, Decimal("125.00"))
    service = StubProfitabilityService({"GROSS_PROFIT": result})

    response = await profitability_report(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        fiscal_period_id="period-1",
        rule_version="2026.1",
        tenant=tenant,
        service=service,
    )

    assert response.organization_id == "org-authenticated"
    assert response.results[0].code == "GROSS_PROFIT"
    assert response.results[0].value == Decimal("125.00")
    assert service.contexts[0][0].organization_id == "org-authenticated"
    assert service.contexts[0][0].rule_version == "2026.1"
    assert service.contexts[0][1] == "period-1"


@pytest.mark.asyncio
async def test_profitability_report_does_not_hide_ledger_integrity_failure():
    tenant = CurrentTenant("user-1", "org-1", "accountant", False)
    service = StubProfitabilityService(
        error=LedgerProfitabilityIntegrityError("ledger mismatch")
    )

    with pytest.raises(HTTPException) as exc_info:
        await profitability_report(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            tenant=tenant,
            service=service,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "LEDGER_NOT_RECONCILED"
