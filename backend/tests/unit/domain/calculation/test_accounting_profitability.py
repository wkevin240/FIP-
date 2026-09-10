from datetime import date
from decimal import Decimal

import pytest

from app.domain.calculation.accounting_profitability import (
    CATEGORY_CODES,
    ProfitabilityCalculationEngine,
    profitability_context,
)
from app.domain.calculation.contracts import CalculationStatus, SourceReference


def context():
    return profitability_context("org-a", date(2026, 1, 1), date(2026, 1, 31), currency="XAF")


def source(code: str, value: Decimal | None, reason: str | None = None):
    return ProfitabilityCalculationEngine.source_result(
        context(),
        code,
        value,
        reason=reason,
        sources=(SourceReference("journal_entry_line", f"line-{code.lower()}", "accounting"),),
    )


def test_profitability_dag_calculates_income_statement_from_resolved_facts():
    inputs = {
        "REVENUE": source("REVENUE", Decimal("1000.01")),
        "COGS": source("COGS", Decimal("400.00")),
        "OPERATING_EXPENSE": source("OPERATING_EXPENSE", Decimal("100.01")),
        "OTHER_INCOME": source("OTHER_INCOME", Decimal("25.00")),
        "OTHER_EXPENSE": source("OTHER_EXPENSE", Decimal("5.00")),
    }

    results = ProfitabilityCalculationEngine.calculate(context(), inputs)

    assert results["GROSS_PROFIT"].value == Decimal("600.01")
    assert results["OPERATING_INCOME"].value == Decimal("500.00")
    assert results["NET_INCOME"].value == Decimal("520.00")
    assert results["GROSS_MARGIN"].value == Decimal("0.60")
    assert results["OPERATING_MARGIN"].value == Decimal("0.50")
    assert results["NET_MARGIN"].value == Decimal("0.52")
    assert results["NET_INCOME"].status is CalculationStatus.READY
    assert {source.record_id for source in results["NET_INCOME"].sources} == {
        "line-revenue",
        "line-cogs",
        "line-operating_expense",
        "line-other_income",
        "line-other_expense",
    }


def test_missing_operating_expense_blocks_dependent_metrics_without_zero_substitution():
    inputs = {
        "REVENUE": source("REVENUE", Decimal("1000.00")),
        "COGS": source("COGS", Decimal("400.00")),
        "OPERATING_EXPENSE": source("OPERATING_EXPENSE", None, "mapping not configured"),
        "OTHER_INCOME": source("OTHER_INCOME", Decimal("0.00")),
        "OTHER_EXPENSE": source("OTHER_EXPENSE", Decimal("0.00")),
    }

    results = ProfitabilityCalculationEngine.calculate(context(), inputs)

    assert results["GROSS_PROFIT"].value == Decimal("600.00")
    assert results["OPERATING_INCOME"].status is CalculationStatus.NOT_READY
    assert results["OPERATING_INCOME"].value is None
    assert results["NET_INCOME"].status is CalculationStatus.NOT_READY
    assert results["NET_MARGIN"].status is CalculationStatus.NOT_READY


def test_zero_revenue_propagates_as_error_through_margin_dag():
    inputs = {
        code: source(code, Decimal("0.00"))
        for code in CATEGORY_CODES
    }
    results = ProfitabilityCalculationEngine.calculate(context(), inputs)

    assert results["NET_INCOME"].value == Decimal("0.00")
    assert results["NET_MARGIN"].status is CalculationStatus.ERROR
    assert results["NET_MARGIN"].value is None
    assert "DivisionByZero" in (results["NET_MARGIN"].reason or "")


def test_unknown_profitability_input_is_rejected():
    inputs = {
        code: source(code, Decimal("1.00"))
        for code in CATEGORY_CODES
    }
    inputs.pop("COGS")

    with pytest.raises(ValueError, match="missing required categories: COGS"):
        ProfitabilityCalculationEngine.calculate(context(), inputs)
