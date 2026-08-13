from decimal import Decimal

import pytest
from app.domain.accounting.closing.rules import PeriodClosingRules


def test_balanced_summary_is_accepted() -> None:
    PeriodClosingRules.validate_summary(
        posted_entry_count=2,
        posted_line_count=4,
        total_debit=Decimal("250.00"),
        total_credit=Decimal("250.00"),
    )


def test_unbalanced_summary_is_rejected() -> None:
    with pytest.raises(ValueError, match="must balance"):
        PeriodClosingRules.validate_summary(
            posted_entry_count=1,
            posted_line_count=2,
            total_debit=Decimal("100.00"),
            total_credit=Decimal("90.00"),
        )


def test_lines_without_entries_are_rejected() -> None:
    with pytest.raises(ValueError, match="requires at least one"):
        PeriodClosingRules.validate_summary(
            posted_entry_count=0,
            posted_line_count=2,
            total_debit=Decimal("0.00"),
            total_credit=Decimal("0.00"),
        )
