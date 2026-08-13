from datetime import date
from decimal import Decimal

import pytest
from app.domain.accounting.vat.rules import VATRules


def test_calculates_vat_with_decimal_precision_and_half_up_rounding() -> None:
    assert VATRules.calculate_vat(Decimal("0.01"), Decimal("50.00")) == Decimal("0.01")
    assert VATRules.calculate_vat(Decimal("19.99"), Decimal("18.00")) == Decimal("3.60")


@pytest.mark.parametrize(
    ("taxable_amount", "rate", "message"),
    [
        (Decimal("-0.01"), Decimal("18.00"), "Taxable amount"),
        (Decimal("1.00"), Decimal("-0.01"), "VAT rate"),
        (Decimal("1.00"), Decimal("100.01"), "VAT rate"),
    ],
)
def test_rejects_amounts_or_rates_outside_permitted_bounds(
    taxable_amount: Decimal, rate: Decimal, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        VATRules.calculate_vat(taxable_amount, rate)


def test_rejects_reversed_declaration_period() -> None:
    with pytest.raises(ValueError, match="Start date"):
        VATRules.validate_period(date(2026, 2, 1), date(2026, 1, 31))
