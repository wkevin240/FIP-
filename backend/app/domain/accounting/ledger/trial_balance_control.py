from collections.abc import Iterable, Mapping
from decimal import Decimal


ZERO = Decimal("0.00")


def trial_balance_control(rows: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Reconcile trial-balance debit and credit totals without touching persistence.

    Rows must already have been resolved from the authoritative posted ledger.
    The control deliberately performs no rounding or tolerance adjustment: the
    accounting ledger uses cent-precision amounts, so any non-zero difference is
    an explicit control exception.
    """
    total_debit = ZERO
    total_credit = ZERO
    row_count = 0
    for row in rows:
        debit = row.get("debit")
        credit = row.get("credit")
        if not isinstance(debit, Decimal) or not isinstance(credit, Decimal):
            raise TypeError("trial balance control requires Decimal debit and credit values")
        total_debit += debit
        total_credit += credit
        row_count += 1

    difference = total_debit - total_credit
    return {
        "row_count": row_count,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balance_difference": difference,
        "is_balanced": difference == ZERO,
    }
