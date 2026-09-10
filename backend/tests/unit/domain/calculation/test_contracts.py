from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.domain.calculation import (
    CalculationContext,
    CalculationDefinition,
    CalculationResult,
    CalculationStatus,
    SourceReference,
)


def definition() -> CalculationDefinition:
    return CalculationDefinition(
        code="GROSS_PROFIT",
        formula="REVENUE - COGS",
        dependencies=("REVENUE", "COGS"),
        rule_version="1",
    )


def context() -> CalculationContext:
    return CalculationContext(
        organization_id="org-1",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        currency="XAF",
    )


def test_ready_result_requires_decimal_and_preserves_provenance() -> None:
    source = SourceReference("JournalEntryLine", "line-1", "accounting")
    result = CalculationResult.ready(
        definition(), context(), Decimal("1250.00"), sources=(source,)
    )

    assert result.status is CalculationStatus.READY
    assert result.value == Decimal("1250.00")
    assert result.sources == (source,)
    assert result.calculated_at.tzinfo is not None


def test_ready_result_rejects_float() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        CalculationResult.ready(definition(), context(), 1250.0)  # type: ignore[arg-type]


def test_not_ready_result_cannot_expose_a_financial_value() -> None:
    result = CalculationResult.not_ready(
        definition(), context(), "COGS mapping is not configured"
    )

    assert result.status is CalculationStatus.NOT_READY
    assert result.value is None
    assert result.reason == "COGS mapping is not configured"


def test_non_ready_result_rejects_a_value() -> None:
    with pytest.raises(ValueError, match="cannot expose a value"):
        CalculationResult(
            definition=definition(),
            context=context(),
            status=CalculationStatus.INCOMPLETE,
            value=Decimal("10"),
            reason="Missing source",
        )


def test_context_rejects_inverted_period() -> None:
    with pytest.raises(ValueError, match="period_start"):
        CalculationContext(
            organization_id="org-1",
            period_start=date(2026, 2, 1),
            period_end=date(2026, 1, 31),
        )


def test_context_requires_dimension_for_dimension_value() -> None:
    with pytest.raises(ValueError, match="dimension_id"):
        CalculationContext(
            organization_id="org-1",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            dimension_value_id="value-1",
        )


def test_result_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        CalculationResult(
            definition=definition(),
            context=context(),
            status=CalculationStatus.READY,
            value=Decimal("10"),
            calculated_at=datetime(2026, 1, 1),
        )


def test_definition_rejects_duplicate_dependencies() -> None:
    with pytest.raises(ValueError, match="unique"):
        CalculationDefinition(
            code="X",
            formula="A + B",
            dependencies=("A", "A"),
        )
