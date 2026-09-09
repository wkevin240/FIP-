from dataclasses import dataclass
from decimal import Decimal

from .rules import MINIMUM_JOURNAL_LINES, ZERO


class JournalEntryValidationError(ValueError):
    """Raised when a journal entry violates double-entry invariants."""


@dataclass(frozen=True, slots=True)
class JournalLine:
    account_id: str
    debit: Decimal = ZERO
    credit: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class JournalEntry:
    lines: tuple[JournalLine, ...]

    @classmethod
    def from_lines(cls, lines: list[JournalLine] | tuple[JournalLine, ...]) -> "JournalEntry":
        entry = cls(tuple(lines))
        validate_entry(entry)
        return entry


def validate_entry(entry: JournalEntry) -> None:
    if len(entry.lines) < MINIMUM_JOURNAL_LINES:
        raise JournalEntryValidationError(
            f"A journal entry must contain at least {MINIMUM_JOURNAL_LINES} lines"
        )

    for line in entry.lines:
        if not line.account_id.strip():
            raise JournalEntryValidationError("Every journal line must reference an account")
        if line.debit < ZERO or line.credit < ZERO:
            raise JournalEntryValidationError("Debit and credit amounts cannot be negative")
        if line.debit > ZERO and line.credit > ZERO:
            raise JournalEntryValidationError(
                "A journal line cannot contain both debit and credit"
            )
        if line.debit == ZERO and line.credit == ZERO:
            raise JournalEntryValidationError(
                "A journal line must contain a debit or a credit"
            )

    debit = sum((line.debit for line in entry.lines), ZERO)
    credit = sum((line.credit for line in entry.lines), ZERO)
    if debit != credit:
        raise JournalEntryValidationError("Journal entry is not balanced")
