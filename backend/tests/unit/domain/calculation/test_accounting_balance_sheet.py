from datetime import date
from decimal import Decimal

import pytest

from app.domain.calculation.accounting_balance_sheet import (
    BalanceSheetAccountRule,
    BalanceSheetCalculationEngine,
    BalanceSheetFact,
    LedgerBalanceSheetInputResolver,
)
from app.domain.calculation.contracts import CalculationContext, CalculationStatus


def context() -> CalculationContext:
    return CalculationContext(
        organization_id="org",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        currency="XAF",
        rule_version="1",
    )


def test_balance_sheet_resolves_explicit_ledger_rules_and_balances() -> None:
    ctx = context()
    facts = (
        BalanceSheetFact("asset-posting", "cash", Decimal("150.00"), Decimal("0.00")),
        BalanceSheetFact("liability-posting", "payable", Decimal("0.00"), Decimal("100.00")),
        BalanceSheetFact("equity-posting", "capital", Decimal("0.00"), Decimal("50.00")),
    )
    rules = (
        BalanceSheetAccountRule("cash", "ASSET"),
        BalanceSheetAccountRule("payable", "LIABILITY"),
        BalanceSheetAccountRule("capital", "EQUITY"),
    )

    inputs = LedgerBalanceSheetInputResolver.resolve(ctx, facts, rules)
    results = BalanceSheetCalculationEngine.calculate(ctx, inputs)

    assert results["TOTAL_ASSETS"].value == Decimal("150.00")
    assert results["TOTAL_LIABILITIES"].value == Decimal("100.00")
    assert results["TOTAL_EQUITY"].value == Decimal("50.00")
    assert results["BALANCE_DIFFERENCE"].value == Decimal("0.00")
    assert len(results["BALANCE_DIFFERENCE"].sources) == 3


def test_missing_explicit_category_propagates_not_ready() -> None:
    ctx = context()
    facts = (BalanceSheetFact("asset-posting", "cash", Decimal("10.00"), Decimal("0.00")),)
    rules = (BalanceSheetAccountRule("cash", "ASSET"),)

    inputs = LedgerBalanceSheetInputResolver.resolve(ctx, facts, rules)
    results = BalanceSheetCalculationEngine.calculate(ctx, inputs)

    assert results["TOTAL_ASSETS"].status is CalculationStatus.READY
    assert results["TOTAL_LIABILITIES"].status is CalculationStatus.NOT_READY
    assert results["TOTAL_EQUITY"].status is CalculationStatus.NOT_READY
    assert results["BALANCE_DIFFERENCE"].status is CalculationStatus.NOT_READY
    assert results["BALANCE_DIFFERENCE"].value is None


def test_balance_sheet_fact_rejects_negative_amount() -> None:
    with pytest.raises(ValueError, match="negative amount"):
        LedgerBalanceSheetInputResolver.resolve(
            context(),
            (BalanceSheetFact("bad", "cash", Decimal("-1.00"), Decimal("0.00")),),
            (BalanceSheetAccountRule("cash", "ASSET"),),
        )


def test_balance_sheet_fact_rejects_both_sides() -> None:
    with pytest.raises(ValueError, match="exactly one positive side"):
        LedgerBalanceSheetInputResolver.resolve(
            context(),
            (BalanceSheetFact("bad", "cash", Decimal("1.00"), Decimal("1.00")),),
            (BalanceSheetAccountRule("cash", "ASSET"),),
        )


def test_duplicate_account_rules_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate balance-sheet rule"):
        LedgerBalanceSheetInputResolver.resolve(
            context(),
            (),
            (
                BalanceSheetAccountRule("cash", "ASSET"),
                BalanceSheetAccountRule("cash", "ASSET"),
            ),
        )
