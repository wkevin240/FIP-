from decimal import Decimal

from .calculators import balance_delta, is_balanced
from .validators import JournalEntry, JournalEntryValidationError, JournalLine, validate_entry


class JournalEntryDomainService:
    """Pure domain operations for creating and validating journal entries."""

    @staticmethod
    def validate(entry: JournalEntry) -> None:
        validate_entry(entry)

    @staticmethod
    def build(lines: list[JournalLine]) -> JournalEntry:
        entry = JournalEntry.from_lines(lines)
        if not is_balanced(entry):
            raise JournalEntryValidationError(
                f"Journal entry is out of balance by {balance_delta(entry)}"
            )
        return entry

    @staticmethod
    def totals(entry: JournalEntry) -> tuple[Decimal, Decimal]:
        from .calculators import total_credit, total_debit

        return total_debit(entry), total_credit(entry)
