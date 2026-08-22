from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.services.accounting.financial_calculation_service import (
    FinancialCalculationService,
)
from fastapi import HTTPException


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


@pytest.mark.asyncio
async def test_profitability_is_not_ready_without_explicit_mappings():
    session = AsyncMock()
    session.execute.return_value = Rows([])
    session.scalar.return_value = Decimal("0.00")
    service = FinancialCalculationService(session)
    service.list_mappings = AsyncMock(return_value=[])

    result = await service.profitability("org-a", date(2026, 1, 1), date(2026, 1, 31))

    assert result.status == "NOT_READY"
    assert result.ledger_is_balanced is True
    metrics = {metric.code: metric for metric in result.metrics}
    assert metrics["NET_INCOME"].value is None
    assert metrics["NET_INCOME"].reason is not None
    assert metrics["NET_MARGIN"].status == "NOT_READY"


@pytest.mark.asyncio
async def test_profitability_uses_explicit_mappings_and_decimal_formulas():
    mappings = [
        SimpleNamespace(account_id="revenue", category="REVENUE"),
        SimpleNamespace(account_id="cogs", category="COGS"),
        SimpleNamespace(account_id="opex", category="OPERATING_EXPENSE"),
    ]
    rows = Rows(
        [
            ("line-r", "revenue", Decimal("0.00"), Decimal("1000.01"), "REVENUE"),
            ("line-c", "cogs", Decimal("400.00"), Decimal("0.00"), "COGS"),
            ("line-o", "opex", Decimal("100.01"), Decimal("0.00"), "OPERATING_EXPENSE"),
        ]
    )
    session = AsyncMock()
    session.execute.return_value = rows
    session.scalar.return_value = Decimal("0.00")
    service = FinancialCalculationService(session)
    service.list_mappings = AsyncMock(return_value=mappings)

    result = await service.profitability("org-a", date(2026, 1, 1), date(2026, 1, 31))

    assert result.status == "READY"
    assert result.ledger_is_balanced is True
    metrics = {metric.code: metric for metric in result.metrics}
    assert metrics["REVENUE"].value == Decimal("1000.01")
    assert metrics["COGS"].value == Decimal("400.00")
    assert metrics["OPERATING_EXPENSE"].value == Decimal("100.01")
    assert metrics["GROSS_PROFIT"].value == Decimal("600.01")
    assert metrics["OPERATING_INCOME"].value == Decimal("500.00")
    assert metrics["NET_INCOME"].value == Decimal("500.00")
    assert metrics["NET_INCOME"].formula == (
        "REVENUE - COGS - OPERATING_EXPENSE + OTHER_INCOME - OTHER_EXPENSE"
    )
    assert metrics["NET_INCOME"].journal_entry_line_ids == [
        "line-c",
        "line-o",
        "line-r",
    ]
    assert metrics["GROSS_MARGIN"].value == Decimal("0.60")
    assert metrics["OPERATING_MARGIN"].value == Decimal("0.50")
    assert metrics["NET_MARGIN"].value == Decimal("0.50")


@pytest.mark.asyncio
async def test_profitability_rejects_inverted_period():
    service = FinancialCalculationService(AsyncMock())
    with pytest.raises(HTTPException, match="period_start must be before period_end"):
        await service.profitability("org-a", date(2026, 2, 1), date(2026, 1, 31))


@pytest.mark.asyncio
async def test_profitability_returns_not_ready_ratios_when_revenue_is_zero():
    mappings = [
        SimpleNamespace(account_id="revenue", category="REVENUE"),
        SimpleNamespace(account_id="cogs", category="COGS"),
        SimpleNamespace(account_id="opex", category="OPERATING_EXPENSE"),
    ]
    rows = Rows(
        [
            ("line-r", "revenue", Decimal("0.00"), Decimal("0.00"), "REVENUE"),
            ("line-c", "cogs", Decimal("10.00"), Decimal("0.00"), "COGS"),
            ("line-o", "opex", Decimal("5.00"), Decimal("0.00"), "OPERATING_EXPENSE"),
        ]
    )
    session = AsyncMock()
    session.execute.return_value = rows
    session.scalar.return_value = Decimal("0.00")
    service = FinancialCalculationService(session)
    service.list_mappings = AsyncMock(return_value=mappings)

    result = await service.profitability("org-a", date(2026, 1, 1), date(2026, 1, 31))
    metrics = {metric.code: metric for metric in result.metrics}

    assert metrics["REVENUE"].value == Decimal("0.00")
    assert metrics["GROSS_MARGIN"].value is None
    assert metrics["GROSS_MARGIN"].status == "NOT_READY"
    assert "denominator is zero" in metrics["NET_MARGIN"].reason


@pytest.mark.asyncio
async def test_profitability_is_incomplete_when_posted_scope_is_unbalanced():
    mappings = [
        SimpleNamespace(account_id="revenue", category="REVENUE"),
        SimpleNamespace(account_id="cogs", category="COGS"),
        SimpleNamespace(account_id="opex", category="OPERATING_EXPENSE"),
    ]
    session = AsyncMock()
    session.execute.return_value = Rows(
        [("line-r", "revenue", Decimal("0.00"), Decimal("100.00"), "REVENUE")]
    )
    session.scalar.return_value = Decimal("100.00")
    service = FinancialCalculationService(session)
    service.list_mappings = AsyncMock(return_value=mappings)

    result = await service.profitability("org-a", date(2026, 1, 1), date(2026, 1, 31))

    assert result.status == "INCOMPLETE"
    assert result.ledger_is_balanced is False
    assert result.ledger_balance_difference == Decimal("100.00")
    assert all(
        metric.status in {"INCOMPLETE", "NOT_READY"} for metric in result.metrics
    )
