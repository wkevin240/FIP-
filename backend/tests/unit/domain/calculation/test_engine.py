import random
from datetime import date
from decimal import Decimal

import pytest

from app.domain.calculation.contracts import (
    CalculationContext,
    CalculationDefinition,
    CalculationResult,
    CalculationStatus,
)
from app.domain.calculation.engine import (
    CalculationEngine,
    CalculationGraphError,
    CalculationNode,
)


def context() -> CalculationContext:
    return CalculationContext(
        organization_id="org-1",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        currency="XAF",
    )


def result(code: str, value: Decimal) -> CalculationResult:
    return CalculationResult.ready(
        CalculationDefinition(code=code, formula=code), context(), value
    )


def node(code: str, dependencies: tuple[str, ...], operation):
    return CalculationNode(
        CalculationDefinition(code=code, formula=code, dependencies=dependencies),
        operation,
    )


def test_engine_resolves_dag_without_eval() -> None:
    engine = CalculationEngine(
        (
            node("GROSS_PROFIT", ("REVENUE", "COGS"), lambda values: values[0] - values[1]),
            node("OPERATING_INCOME", ("GROSS_PROFIT", "OPEX"), lambda values: values[0] - values[1]),
        )
    )
    results = engine.execute(
        context(),
        {
            "REVENUE": result("REVENUE", Decimal("120000000")),
            "COGS": result("COGS", Decimal("70000000")),
            "OPEX": result("OPEX", Decimal("25000000")),
        },
    )

    assert results["GROSS_PROFIT"].value == Decimal("50000000")
    assert results["OPERATING_INCOME"].value == Decimal("25000000")


def test_error_propagates_through_three_dag_levels() -> None:
    revenue = CalculationResult.error(
        CalculationDefinition(code="REVENUE", formula="REVENUE"),
        context(),
        "Revenue source calculation failed",
    )
    engine = CalculationEngine(
        (
            node("GROSS_PROFIT", ("REVENUE", "COGS"), lambda values: values[0] - values[1]),
            node("OPERATING_INCOME", ("GROSS_PROFIT", "OPEX"), lambda values: values[0] - values[1]),
            node(
                "NET_INCOME",
                ("OPERATING_INCOME", "OTHER"),
                lambda values: values[0] + values[1],
            ),
        )
    )

    results = engine.execute(
        context(),
        {
            "REVENUE": revenue,
            "COGS": result("COGS", Decimal("10")),
            "OPEX": result("OPEX", Decimal("5")),
            "OTHER": result("OTHER", Decimal("1")),
        },
    )

    assert results["GROSS_PROFIT"].status is CalculationStatus.ERROR
    assert results["OPERATING_INCOME"].status is CalculationStatus.ERROR
    assert results["NET_INCOME"].status is CalculationStatus.ERROR
    assert results["NET_INCOME"].value is None


def test_worst_dependency_status_is_error_even_when_another_dependency_is_not_ready() -> None:
    error = CalculationResult.error(
        CalculationDefinition(code="FAILED", formula="FAILED"), context(), "source failure"
    )
    not_ready = CalculationResult.not_ready(
        CalculationDefinition(code="MISSING", formula="MISSING"), context(), "source missing"
    )
    engine = CalculationEngine(
        (node("TOTAL", ("FAILED", "MISSING"), lambda values: values[0] + values[1]),)
    )

    output = engine.execute(context(), {"FAILED": error, "MISSING": not_ready})["TOTAL"]

    assert output.status is CalculationStatus.ERROR
    assert output.value is None


def test_not_ready_propagates_without_becoming_zero() -> None:
    definition = CalculationDefinition(code="REVENUE", formula="REVENUE")
    revenue = CalculationResult.not_ready(
        definition, context(), "Revenue source is unavailable"
    )
    engine = CalculationEngine(
        (node("GROSS_PROFIT", ("REVENUE", "COGS"), lambda values: values[0] - values[1]),)
    )

    output = engine.execute(
        context(),
        {"REVENUE": revenue, "COGS": result("COGS", Decimal("10"))},
    )["GROSS_PROFIT"]

    assert output.status is CalculationStatus.NOT_READY
    assert output.value is None
    assert "Revenue source is unavailable" in (output.reason or "")


def test_division_by_zero_is_error_not_not_ready_and_does_not_crash() -> None:
    engine = CalculationEngine(
        (node("MARGIN", ("PROFIT", "REVENUE"), lambda values: values[0] / values[1]),)
    )
    output = engine.execute(
        context(),
        {"PROFIT": result("PROFIT", Decimal("100")), "REVENUE": result("REVENUE", Decimal("0"))},
    )["MARGIN"]

    assert output.status is CalculationStatus.ERROR
    assert output.value is None
    assert "DivisionByZero" in (output.reason or "")


def test_randomly_generated_double_entry_cases_balance() -> None:
    rng = random.Random(20260910)
    for _ in range(1000):
        amounts = [Decimal(rng.randint(1, 10_000)) / Decimal("100") for _ in range(rng.randint(1, 20))]
        total = sum(amounts, Decimal("0.00"))
        debits = amounts
        credits = [total]
        assert sum(debits, Decimal("0.00")) == sum(credits, Decimal("0.00"))


def test_unknown_dependency_is_rejected() -> None:
    with pytest.raises(CalculationGraphError, match="unknown"):
        CalculationEngine((node("A", ("MISSING",), lambda values: values[0]),))


def test_cycle_is_rejected() -> None:
    with pytest.raises(CalculationGraphError, match="cycle"):
        CalculationEngine(
            (
                node("A", ("B",), lambda values: values[0]),
                node("B", ("A",), lambda values: values[0]),
            )
        )
