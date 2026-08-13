from decimal import Decimal

import pytest
from app.domain.inventory.stock.rules import StockValuationRules, ValuedStockBalance


def test_receipts_compute_weighted_average_cost() -> None:
    empty = ValuedStockBalance(
        quantity=Decimal("0.000"),
        total_value=Decimal("0.00"),
        average_unit_cost=Decimal("0.0000"),
    )
    after_first, first_value = StockValuationRules.receipt(
        empty, Decimal("10.000"), Decimal("10.0000")
    )
    after_second, second_value = StockValuationRules.receipt(
        after_first, Decimal("5.000"), Decimal("16.0000")
    )

    assert first_value == Decimal("100.00")
    assert second_value == Decimal("80.00")
    assert after_second.quantity == Decimal("15.000")
    assert after_second.total_value == Decimal("180.00")
    assert after_second.average_unit_cost == Decimal("12.0000")


def test_issue_uses_average_cost_and_resets_empty_balance() -> None:
    balance = ValuedStockBalance(
        quantity=Decimal("2.000"),
        total_value=Decimal("25.00"),
        average_unit_cost=Decimal("12.5000"),
    )

    remaining, unit_cost, issued_value = StockValuationRules.issue(
        balance, Decimal("2.000")
    )

    assert unit_cost == Decimal("12.5000")
    assert issued_value == Decimal("25.00")
    assert remaining == ValuedStockBalance(
        quantity=Decimal("0.000"),
        total_value=Decimal("0.00"),
        average_unit_cost=Decimal("0.0000"),
    )


@pytest.mark.parametrize(
    ("quantity", "unit_cost", "message"),
    [
        (Decimal("0.000"), Decimal("1.0000"), "quantity"),
        (Decimal("1.000"), Decimal("-0.0001"), "cost"),
    ],
)
def test_receipt_rejects_invalid_quantity_or_cost(
    quantity: Decimal, unit_cost: Decimal, message: str
) -> None:
    empty = ValuedStockBalance(
        quantity=Decimal("0.000"),
        total_value=Decimal("0.00"),
        average_unit_cost=Decimal("0.0000"),
    )

    with pytest.raises(ValueError, match=message):
        StockValuationRules.receipt(empty, quantity, unit_cost)


def test_issue_rejects_insufficient_quantity() -> None:
    balance = ValuedStockBalance(
        quantity=Decimal("1.000"),
        total_value=Decimal("10.00"),
        average_unit_cost=Decimal("10.0000"),
    )

    with pytest.raises(ValueError, match="Insufficient stock"):
        StockValuationRules.issue(balance, Decimal("1.001"))
