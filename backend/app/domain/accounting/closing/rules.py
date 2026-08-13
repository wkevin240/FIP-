from decimal import Decimal


class PeriodClosingRules:
    """Validation rules for a deterministic accounting period close."""

    @staticmethod
    def validate_summary(
        posted_entry_count: int,
        posted_line_count: int,
        total_debit: Decimal,
        total_credit: Decimal,
    ) -> None:
        if posted_entry_count < 0 or posted_line_count < 0:
            raise ValueError("Closing counts must be non-negative")
        if posted_entry_count == 0 and posted_line_count != 0:
            raise ValueError("Closing line count requires at least one posted entry")
        if total_debit < 0 or total_credit < 0:
            raise ValueError("Closing totals must be non-negative")
        if total_debit != total_credit:
            raise ValueError("Posted journal entries must balance before closing")
