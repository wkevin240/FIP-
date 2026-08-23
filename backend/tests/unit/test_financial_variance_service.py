from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.schemas.accounting.financial_variance import VarianceComparison
from app.services.accounting.financial_variance_service import FinancialVarianceService
from fastapi import HTTPException


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


@pytest.mark.asyncio
async def test_previous_period_variance_is_decimal_and_explainable():
    calculation = AsyncMock()
    calculation.profitability.side_effect = [
        SimpleNamespace(
            status="READY",
            metrics=[
                SimpleNamespace(
                    code="NET_INCOME",
                    value=Decimal("120.00"),
                    account_ids=["a-current"],
                    journal_entry_line_ids=["line-current"],
                    dimensions=[],
                )
            ],
        ),
        SimpleNamespace(
            status="READY",
            metrics=[
                SimpleNamespace(
                    code="NET_INCOME",
                    value=Decimal("100.00"),
                    account_ids=["a-prior"],
                    journal_entry_line_ids=["line-prior"],
                    dimensions=[],
                )
            ],
        ),
    ]
    service = FinancialVarianceService(AsyncMock())
    service.calculation = calculation

    result = await service.calculate(
        "org-a",
        date(2026, 2, 1),
        date(2026, 2, 28),
        VarianceComparison.PREVIOUS_PERIOD,
    )

    metric = result.metrics[0]
    assert result.status == "READY"
    assert metric.actual == Decimal("120.00")
    assert metric.comparison == Decimal("100.00")
    assert metric.variance == Decimal("20.00")
    assert metric.variance_percentage == Decimal("0.20")
    assert metric.source_lines == ["line-current"]
    assert metric.comparison_source_lines == ["line-prior"]


@pytest.mark.asyncio
async def test_variance_percentage_is_null_when_comparison_is_zero():
    calculation = AsyncMock()
    metric = lambda value: SimpleNamespace(
        code="REVENUE",
        value=value,
        account_ids=[],
        journal_entry_line_ids=[],
        dimensions=[],
    )
    calculation.profitability.side_effect = [
        SimpleNamespace(status="READY", metrics=[metric(Decimal("10.00"))]),
        SimpleNamespace(status="READY", metrics=[metric(Decimal("0.00"))]),
    ]
    service = FinancialVarianceService(AsyncMock())
    service.calculation = calculation

    result = await service.calculate(
        "org-a",
        date(2026, 2, 1),
        date(2026, 2, 28),
        VarianceComparison.PREVIOUS_PERIOD,
    )

    assert result.metrics[0].variance == Decimal("10.00")
    assert result.metrics[0].variance_percentage is None
    assert "zero" in result.metrics[0].reason


@pytest.mark.asyncio
async def test_budget_and_forecast_without_approved_source_are_not_ready():
    service = FinancialVarianceService(AsyncMock())
    service.calculation = AsyncMock()
    service.calculation.list_mappings.return_value = []
    service.calculation.profitability.return_value = SimpleNamespace(
        status="READY", metrics=[]
    )
    for comparison in (VarianceComparison.BUDGET, VarianceComparison.FORECAST):
        result = await service.calculate(
            "org-a", date(2026, 1, 1), date(2026, 1, 31), comparison
        )
        assert result.status == "NOT_READY"
        assert result.metrics == []
        assert result.reason is not None


@pytest.mark.asyncio
async def test_variance_rejects_inverted_period():
    service = FinancialVarianceService(AsyncMock())
    with pytest.raises(HTTPException, match="period_start must be before period_end"):
        await service.calculate(
            "org-a",
            date(2026, 2, 1),
            date(2026, 1, 31),
            VarianceComparison.PREVIOUS_PERIOD,
        )
