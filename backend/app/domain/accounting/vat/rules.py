from datetime import date
from decimal import ROUND_HALF_UP, Decimal


class VATRules:
    MONEY_QUANTUM = Decimal("0.01")

    @classmethod
    def calculate_vat(cls, taxable_amount: Decimal, rate: Decimal) -> Decimal:
        if taxable_amount < 0:
            raise ValueError("Taxable amount must be non-negative")
        if rate < 0 or rate > 100:
            raise ValueError("VAT rate must be between 0 and 100")
        return (taxable_amount * rate / Decimal(100)).quantize(
            cls.MONEY_QUANTUM, rounding=ROUND_HALF_UP
        )

    @staticmethod
    def validate_period(start_date: date, end_date: date) -> None:
        if start_date > end_date:
            raise ValueError("Start date must not be after end date")
