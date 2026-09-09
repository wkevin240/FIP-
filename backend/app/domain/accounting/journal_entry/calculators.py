from decimal import Decimal

from .rules import ZERO
from .validators import JournalEntry, JournalEntryValidationError


def total_debit(entry: JournalEntry) -> Decimal:
    return sum((line.debit for line in entry.lines), ZERO)


def total_credit(entry: JournalEntry) -> Decimal:
    return sum((line.credit for line in entry.lines), ZERO)


def balance_delta(entry: JournalEntry) -> Decimal:
    return total_debit(entry) - total_credit(entry)


def is_balanced(entry: JournalEntry) -> bool:
    return balance_delta(entry) == ZERO
