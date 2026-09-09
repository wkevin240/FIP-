from decimal import Decimal

import pytest

from app.domain.accounting.journal_entry.calculators import balance_delta, is_balanced
from app.domain.accounting.journal_entry.journal_entry_domain_service import JournalEntryDomainService
from app.domain.accounting.journal_entry.validators import (
    JournalEntryValidationError,
    JournalLine,
)


def test_balanced_entry_is_accepted() -> None:
    entry = JournalEntryDomainService.build([
        JournalLine(account_id="411", debit=Decimal("100.00")),
        JournalLine(account_id="707", credit=Decimal("100.00")),
    ])
    assert is_balanced(entry)
    assert balance_delta(entry) == Decimal("0")
    assert JournalEntryDomainService.totals(entry) == (
        Decimal("100.00"),
        Decimal("100.00"),
    )


@pytest.mark.parametrize(
    "lines, message",
    [
        ([JournalLine(account_id="411", debit=Decimal("100"))], "at least"),
        (
            [
                JournalLine(account_id="411", debit=Decimal("100")),
                JournalLine(account_id="707", credit=Decimal("90")),
            ],
            "not balanced",
        ),
        (
            [
                JournalLine(account_id="411", debit=Decimal("100"), credit=Decimal("100")),
                JournalLine(account_id="707", credit=Decimal("200")),
            ],
            "both debit and credit",
        ),
    ],
)
def test_invalid_entries_are_rejected(lines: list[JournalLine], message: str) -> None:
    with pytest.raises(JournalEntryValidationError, match=message):
        JournalEntryDomainService.build(lines)


def test_negative_amount_is_rejected() -> None:
    with pytest.raises(JournalEntryValidationError, match="cannot be negative"):
        JournalEntryDomainService.build([
            JournalLine(account_id="411", debit=Decimal("-1")),
            JournalLine(account_id="707", credit=Decimal("-1")),
        ])
