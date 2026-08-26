from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.services.accounting.financial_closing_control_service import (
    FinancialClosingControlService,
)


@pytest.mark.asyncio
async def test_control_orchestrates_existing_services_without_mutation():
    session = SimpleNamespace(scalar=AsyncMock())
    period = SimpleNamespace(
        id="period-real",
        fiscal_year_id="year-real",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status="OPEN",
    )
    session.scalar.return_value = period
    service = FinancialClosingControlService(session)
    service.readiness.assess = AsyncMock(
        return_value=SimpleNamespace(status="READY", blockers=[])
    )
    service.kpi.calculate = AsyncMock(
        return_value=SimpleNamespace(
            metrics=[
                SimpleNamespace(
                    code="AR_OUTSTANDING",
                    status="READY",
                    formula="invoice total - payments - credits",
                    value=Decimal("100.00"),
                    source_ids=["invoice-real"],
                    blockers=[],
                    reason=None,
                )
            ]
        )
    )
    service.reporting.trial_balance = AsyncMock(
        return_value=SimpleNamespace(
            total_debit=Decimal("100.00"),
            total_credit=Decimal("100.00"),
            is_balanced=True,
            lines=[SimpleNamespace(account_id="account-real")],
        )
    )

    result = await service.assess("org-real", "year-real", "period-real")

    assert result.organization_id == "org-real"
    assert result.status == "READY"
    assert {control.control_code for control in result.controls} == {
        "CLOSING_READINESS",
        "FISCAL_PERIOD",
        "AR_OUTSTANDING",
        "REPORTING_TRIAL_BALANCE",
    }
    service.readiness.assess.assert_awaited_once_with("org-real", "year-real")
    service.kpi.calculate.assert_awaited_once_with(
        "org-real",
        fiscal_period_id="period-real",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        as_of=date(2026, 1, 31),
    )
    service.reporting.trial_balance.assert_awaited_once_with(
        "org-real", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)
    )


@pytest.mark.asyncio
async def test_control_preserves_incomplete_and_deterministic_blockers():
    session = SimpleNamespace(scalar=AsyncMock())
    session.scalar.return_value = SimpleNamespace(
        id="period-real",
        fiscal_year_id="year-real",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status="OPEN",
    )
    service = FinancialClosingControlService(session)
    service.readiness.assess = AsyncMock(
        return_value=SimpleNamespace(
            status="NOT_READY", blockers=["DRAFT_JOURNAL_ENTRIES"]
        )
    )
    service.kpi.calculate = AsyncMock(
        return_value=SimpleNamespace(
            metrics=[
                SimpleNamespace(
                    code="RECONCILIATION",
                    status="INCOMPLETE",
                    formula=None,
                    value=None,
                    source_ids=["payment-real", "bank-real"],
                    blockers=["PAYMENT_BANK_AMOUNT_MISMATCH"],
                    reason="Payment and bank amounts differ.",
                )
            ]
        )
    )
    service.reporting.trial_balance = AsyncMock(
        return_value=SimpleNamespace(
            total_debit=Decimal("120.00"),
            total_credit=Decimal("100.00"),
            is_balanced=False,
            lines=[SimpleNamespace(account_id="account-real")],
        )
    )

    result = await service.assess("org-real", "year-real", "period-real")

    assert result.status == "INCOMPLETE"
    assert [blocker.code for blocker in result.blockers] == [
        "DRAFT_JOURNAL_ENTRIES",
        "PAYMENT_BANK_AMOUNT_MISMATCH",
        "REPORTING_TRIAL_BALANCE_UNBALANCED",
    ]
    assert result.blockers[1].source_ids == ["payment-real", "bank-real"]
    assert result.blockers[2].amount == Decimal("20.00")


def test_period_control_rejects_locked_period_without_mutation():
    service = FinancialClosingControlService(SimpleNamespace())
    result = service._period_control(
        SimpleNamespace(
            id="period-locked",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            status="LOCKED",
        )
    )
    assert result.status == "NOT_READY"
    assert result.blockers[0].code == "FISCAL_PERIOD_NOT_OPEN"
