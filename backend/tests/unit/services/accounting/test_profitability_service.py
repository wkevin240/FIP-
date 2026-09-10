from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.domain.calculation.accounting_profitability import profitability_context
from app.domain.calculation.contracts import CalculationStatus
from app.domain.calculation.ledger_profitability import (
    LedgerProfitabilityFact,
    ProfitabilityAccountRule,
)
from app.services.accounting.profitability_service import LedgerProfitabilityService


@pytest.mark.asyncio
async def test_calculate_uses_context_window_and_explicit_mapping() -> None:
    ledger = AsyncMock()
    ledger.profitability_facts.return_value = [
        LedgerProfitabilityFact("p-revenue", "a-revenue", Decimal("0.00"), Decimal("150.00")),
        LedgerProfitabilityFact("p-cogs", "a-cogs", Decimal("60.00"), Decimal("0.00")),
        LedgerProfitabilityFact("p-opex", "a-opex", Decimal("20.00"), Decimal("0.00")),
    ]
    service = LedgerProfitabilityService(ledger)
    context = profitability_context(
        "org-1",
        date(2026, 1, 1),
        date(2026, 12, 31),
        currency="XAF",
        rule_version="2026.1",
    )
    rules = (
        ProfitabilityAccountRule("a-revenue", "REVENUE"),
        ProfitabilityAccountRule("a-cogs", "COGS"),
        ProfitabilityAccountRule("a-opex", "OPERATING_EXPENSE"),
    )

    result = await service.calculate(context, rules, fiscal_period_id="period-1")

    ledger.profitability_facts.assert_awaited_once_with(
        "org-1",
        fiscal_period_id="period-1",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    assert result["GROSS_PROFIT"].status is CalculationStatus.READY
    assert result["GROSS_PROFIT"].value == Decimal("90.00")
    assert result["OPERATING_INCOME"].value == Decimal("70.00")
    assert result["NET_INCOME"].status is CalculationStatus.NOT_READY
    assert result["GROSS_PROFIT"].definition.rule_version == "2026.1"


@pytest.mark.asyncio
async def test_calculate_does_not_bypass_missing_source_status() -> None:
    ledger = AsyncMock()
    ledger.profitability_facts.return_value = [
        LedgerProfitabilityFact("p-revenue", "a-revenue", Decimal("0.00"), Decimal("150.00")),
    ]
    service = LedgerProfitabilityService(ledger)
    context = profitability_context("org-1", date(2026, 1, 1), date(2026, 12, 31))

    result = await service.calculate(
        context,
        (ProfitabilityAccountRule("a-revenue", "REVENUE"),),
    )

    assert result["REVENUE"].status is CalculationStatus.READY
    assert result["COGS"].status is CalculationStatus.NOT_READY
    assert result["GROSS_PROFIT"].status is CalculationStatus.NOT_READY
    assert result["GROSS_PROFIT"].value is None
