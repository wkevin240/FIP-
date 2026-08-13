from datetime import date
from decimal import Decimal

import pytest
from app.domain.accounting.journal_entry.rules import JournalEntryRules
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate


def test_balanced_lines_are_accepted() -> None:
    lines = [
        JournalEntryLineCreate(account_id="cash", debit=Decimal("100.00")),
        JournalEntryLineCreate(account_id="revenue", credit=Decimal("100.00")),
    ]

    debit, credit = JournalEntryRules.validate_balanced_lines(lines)

    assert debit == Decimal("100.00")
    assert credit == Decimal("100.00")


def test_unbalanced_lines_are_rejected() -> None:
    lines = [
        JournalEntryLineCreate(account_id="cash", debit=Decimal("100.00")),
        JournalEntryLineCreate(account_id="revenue", credit=Decimal("90.00")),
    ]

    with pytest.raises(ValueError, match="totals must balance"):
        JournalEntryRules.validate_balanced_lines(lines)


def test_line_with_both_sides_is_rejected() -> None:
    lines = [
        JournalEntryLineCreate(
            account_id="cash", debit=Decimal("100.00"), credit=Decimal("100.00")
        ),
        JournalEntryLineCreate(account_id="revenue", credit=Decimal("100.00")),
    ]

    with pytest.raises(ValueError, match="either a debit or a credit"):
        JournalEntryRules.validate_balanced_lines(lines)


def test_entry_date_must_be_in_fiscal_period() -> None:
    with pytest.raises(ValueError, match="must fall within"):
        JournalEntryRules.validate_entry_date(
            date(2026, 2, 1), date(2026, 1, 1), date(2026, 1, 31)
        )
