from decimal import Decimal

ZERO = Decimal("0.00")


def signed_balance(debit: Decimal, credit: Decimal) -> Decimal:
    """Return the accounting movement sign convention used by FIP reports."""
    return debit - credit


def is_balanced(debit: Decimal, credit: Decimal) -> bool:
    return debit == credit
