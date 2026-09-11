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


@pytest.fixture
def context() -> CalculationContext:
    return CalculationContext(
        organization_id="org-1",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        rule_version="v1",
    )


def test_resolver_uses_normal_balance_and_preserves_provenance(context: CalculationContext) -> None:
    facts = (
        BalanceSheetFact("posting-asset", "cash", Decimal("150.00"), Decimal("0.00")),
        BalanceSheetFact("posting-liability", "payable", Decimal("0.00"), Decimal("60.00")),
        BalanceSheetFact("posting-equity", "capital", Decimal("0.00"), Decimal("90.00")),
    )
    rules = (
        BalanceSheetAccountRule("cash", "ASSET"),
        BalanceSheetAccountRule("payable", "LIABILITY"),
        BalanceSheetAccountRule("capital", "EQUITY"),
    )

    inputs = LedgerBalanceSheetInputResolver.resolve(context, facts, rules)
    results = BalanceSheetCalculationEngine.calculate(context, inputs)

    assert results["TOTAL_ASSETS"].value == Decimal("150.00")
    assert results["TOTAL_LIABILITIES"].value == Decimal("60.00")
    assert results["TOTAL_EQUITY"].value == Decimal("90.00")
    assert results["BALANCE_DIFFERENCE"].value == Decimal("0.00")
    assert results["BALANCE_DIFFERENCE"].status is CalculationStatus.READY
    assert {source.record_id for source in inputs["ASSET"].sources} == {"posting-asset"}


def test_missing_category_fails_closed_and_propagates_not_ready(context: CalculationContext) -> None:
    facts = (BalanceSheetFact("posting-asset", "cash", Decimal("100.00"), Decimal("0.00")),)
    rules = (BalanceSheetAccountRule("cash", "ASSET"),)

    inputs = LedgerBalanceSheetInputResolver.resolve(context, facts, rules)
    results = BalanceSheetCalculationEngine.calculate(context, inputs)

    assert inputs["LIABILITY"].status is CalculationStatus.NOT_READY
    assert inputs["EQUITY"].status is CalculationStatus.NOT_READY
    assert results["BALANCE_DIFFERENCE"].status is CalculationStatus.NOT_READY
    assert results["BALANCE_DIFFERENCE"].value is None


def test_negative_ledger_amount_is_rejected(context: CalculationContext) -> None:
    facts = (BalanceSheetFact("posting-1", "cash", Decimal("-1.00"), Decimal("0.00")),)

    with pytest.raises(ValueError, match="negative amount"):
        LedgerBalanceSheetInputResolver.resolve(
            context, facts, (BalanceSheetAccountRule("cash", "ASSET"),)
        )


def test_debit_and_credit_cannot_both_be_positive(context: CalculationContext) -> None:
    facts = (BalanceSheetFact("posting-1", "cash", Decimal("10.00"), Decimal("5.00")),)

    with pytest.raises(ValueError, match="exactly one positive side"):
        LedgerBalanceSheetInputResolver.resolve(
            context, facts, (BalanceSheetAccountRule("cash", "ASSET"),)
        )


def test_duplicate_rules_are_rejected(context: CalculationContext) -> None:
    facts = (BalanceSheetFact("posting-1", "cash", Decimal("10.00"), Decimal("0.00")),)
    rules = (
        BalanceSheetAccountRule("cash", "ASSET"),
        BalanceSheetAccountRule("cash", "EQUITY"),
    )

    with pytest.raises(ValueError, match="duplicate balance-sheet rule"):
        LedgerBalanceSheetInputResolver.resolve(context, facts, rules)


def test_unmapped_posting_does_not_become_zero_value_source(context: CalculationContext) -> None:
    facts = (BalanceSheetFact("posting-unmapped", "unknown", Decimal("75.00"), Decimal("0.00")),)
    rules = (BalanceSheetAccountRule("cash", "ASSET"),)

    inputs = LedgerBalanceSheetInputResolver.resolve(context, facts, rules)

    assert inputs["ASSET"].status is CalculationStatus.NOT_READY
    assert inputs["ASSET"].value is None
    assert inputs["ASSET"].sources == ()
