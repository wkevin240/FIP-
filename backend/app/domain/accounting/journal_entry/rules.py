from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Protocol


class JournalEntryLineAmounts(Protocol):
    debit: Decimal
    credit: Decimal


class JournalEntryRules:
    """Domain invariants for double-entry accounting records."""

    @staticmethod
    def validate_entry_date(
        entry_date: date, period_start: date, period_end: date
    ) -> None:
        if not period_start <= entry_date <= period_end:
            raise ValueError("Entry date must fall within the fiscal period")

    @staticmethod
    def validate_balanced_lines(
        lines: Iterable[JournalEntryLineAmounts],
    ) -> tuple[Decimal, Decimal]:
        materialized_lines = list(lines)
        if len(materialized_lines) < 2:
            raise ValueError("A journal entry must contain at least two lines")

        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")
        for line in materialized_lines:
            debit = Decimal(line.debit)
            credit = Decimal(line.credit)
            if debit < 0 or credit < 0:
                raise ValueError("Debit and credit amounts must be non-negative")
            if (debit == 0) == (credit == 0):
                raise ValueError("Each line must contain either a debit or a credit")
            total_debit += debit
            total_credit += credit

        if total_debit != total_credit:
            raise ValueError("Journal entry debit and credit totals must balance")
        return total_debit, total_credit
