from datetime import date
from decimal import Decimal

import pytest
from app.core.enums.invoicing import InvoiceStatus
from app.domain.invoicing.invoice.rules import InvoiceRules


def test_calculates_line_with_commercial_rounding_and_vat() -> None:
    line = InvoiceRules.calculate_line(
        Decimal("2.500"), Decimal("10.01"), Decimal("18.00")
    )

    assert line.subtotal == Decimal("25.03")
    assert line.tax_amount == Decimal("4.51")
    assert line.total == Decimal("29.54")


def test_aggregates_invoice_lines() -> None:
    first = InvoiceRules.calculate_line(
        Decimal("1.000"), Decimal("100.00"), Decimal("18.00")
    )
    second = InvoiceRules.calculate_line(
        Decimal("2.000"), Decimal("50.00"), Decimal("0.00")
    )

    totals = InvoiceRules.aggregate([first, second])

    assert totals.subtotal == Decimal("200.00")
    assert totals.tax_amount == Decimal("18.00")
    assert totals.total_amount == Decimal("218.00")


@pytest.mark.parametrize(
    ("quantity", "unit_price", "rate", "message"),
    [
        (Decimal("0.000"), Decimal("10.00"), Decimal("0.00"), "quantity"),
        (Decimal("1.000"), Decimal("-0.01"), Decimal("0.00"), "price"),
        (Decimal("1.000"), Decimal("10.00"), Decimal("100.01"), "rate"),
    ],
)
def test_rejects_invalid_line_values(
    quantity: Decimal, unit_price: Decimal, rate: Decimal, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        InvoiceRules.calculate_line(quantity, unit_price, rate)


def test_rejects_invoice_due_date_before_invoice_date() -> None:
    with pytest.raises(ValueError, match="due date"):
        InvoiceRules.validate_dates(date(2026, 2, 1), date(2026, 1, 31))


def test_payment_and_credit_update_status_without_exceeding_total() -> None:
    status_value, paid_amount, credited_amount = InvoiceRules.apply_payment(
        Decimal("118.00"),
        Decimal("0.00"),
        Decimal("0.00"),
        Decimal("50.00"),
    )
    assert (status_value, paid_amount, credited_amount) == (
        InvoiceStatus.PARTIALLY_PAID,
        Decimal("50.00"),
        Decimal("0.00"),
    )

    status_value, paid_amount, credited_amount = InvoiceRules.apply_credit(
        Decimal("118.00"),
        paid_amount,
        credited_amount,
        Decimal("68.00"),
    )
    assert (status_value, paid_amount, credited_amount) == (
        InvoiceStatus.PAID,
        Decimal("50.00"),
        Decimal("68.00"),
    )

    with pytest.raises(ValueError, match="exceeds"):
        InvoiceRules.apply_payment(
            Decimal("118.00"),
            paid_amount,
            credited_amount,
            Decimal("0.01"),
        )


def test_full_credit_cancels_unpaid_invoice() -> None:
    status_value, paid_amount, credited_amount = InvoiceRules.apply_credit(
        Decimal("100.00"),
        Decimal("0.00"),
        Decimal("0.00"),
        Decimal("100.00"),
    )

    assert (status_value, paid_amount, credited_amount) == (
        InvoiceStatus.CANCELLED,
        Decimal("0.00"),
        Decimal("100.00"),
    )
