from datetime import date
from decimal import Decimal

import pytest

from app.domain.calculation.contracts import CalculationContext, CalculationStatus
from app.domain.calculation.ledger_profitability import (
    LedgerProfitabilityFact,
    LedgerProfitabilityInputResolver,
    ProfitabilityAccountRule,
)


def context() -> CalculationContext:
    return CalculationContext(
        organization_id="org-1",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        currency="XAF",
        rule_version="7",
    )


def test_resolver_uses_explicit_mapping_and_preserves_posting_provenance() -> None:
    facts = [
        LedgerProfitabilityFact("posting-revenue", "account-revenue", Decimal("0.00"), Decimal("150.00")),
        LedgerProfitabilityFact("posting-cogs", "account-cogs", Decimal("60.00"), Decimal("0.00")),
        LedgerProfitabilityFact("posting-opex", "account-opex", Decimal("20.00"), Decimal("0.00")),
    ]
    rules = [
        ProfitabilityAccountRule("account-revenue", "REVENUE"),
        ProfitabilityAccountRule("account-cogs", "COGS"),
        ProfitabilityAccountRule("account-opex", "OPERATING_EXPENSE"),
    ]

    result = LedgerProfitabilityInputResolver.resolve(context(), facts, rules)

    assert result["REVENUE"].status is CalculationStatus.READY
    assert result["REVENUE"].value == Decimal("150.00")
    assert result["REVENUE"].sources[0].record_id == "posting-revenue"
    assert result["REVENUE"].metadata["account_ids"] == "account-revenue"
    assert result["REVENUE"].definition.rule_version == "7"
    assert result["COGS"].value == Decimal("60.00")
    assert result["OPERATING_EXPENSE"].value == Decimal("20.00")
    assert result["OTHER_INCOME"].status is CalculationStatus.NOT_READY
    assert result["OTHER_EXPENSE"].status is CalculationStatus.NOT_READY


def test_unmapped_ledger_facts_do_not_become_profitability_inputs() -> None:
    facts = [LedgerProfitabilityFact("posting-bank", "account-bank", Decimal("100.00"), Decimal("0.00"))]
    rules = [ProfitabilityAccountRule("account-revenue", "REVENUE")]

    result = LedgerProfitabilityInputResolver.resolve(context(), facts, rules)

    assert result["REVENUE"].status is CalculationStatus.NOT_READY
    assert result["REVENUE"].value is None
    assert result["REVENUE"].sources == ()


def test_duplicate_account_classification_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate profitability rule"):
        LedgerProfitabilityInputResolver.resolve(
            context(),
            (),
            (
                ProfitabilityAccountRule("account-1", "REVENUE"),
                ProfitabilityAccountRule("account-1", "COGS"),
            ),
        )


def test_invalid_ledger_movement_is_rejected() -> None:
    with pytest.raises(ValueError, match="exactly one positive side"):
        LedgerProfitabilityInputResolver.resolve(
            context(),
            (LedgerProfitabilityFact("posting-invalid", "account-1", Decimal("10.00"), Decimal("10.00")),),
            (ProfitabilityAccountRule("account-1", "REVENUE"),),
        )


def test_unsupported_category_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported profitability category"):
        LedgerProfitabilityInputResolver.resolve(
            context(),
            (),
            (ProfitabilityAccountRule("account-1", "UNKNOWN"),),
        )


def test_ledger_fact_requires_identifiers_and_decimal_amounts() -> None:
    with pytest.raises(ValueError, match="posting_id is required"):
        LedgerProfitabilityFact("", "account-1", Decimal("1.00"), Decimal("0.00"))
    with pytest.raises(ValueError, match="account_id is required"):
        LedgerProfitabilityFact("posting-1", "", Decimal("1.00"), Decimal("0.00"))
    with pytest.raises(TypeError, match="ledger amounts must use Decimal"):
        LedgerProfitabilityFact("posting-1", "account-1", 1, Decimal("0.00"))


def test_profitability_rule_requires_identifiers() -> None:
    with pytest.raises(ValueError, match="account_id is required"):
        ProfitabilityAccountRule("", "REVENUE")
    with pytest.raises(ValueError, match="category is required"):
        ProfitabilityAccountRule("account-1", "")
