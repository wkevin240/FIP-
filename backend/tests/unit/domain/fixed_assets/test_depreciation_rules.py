from datetime import date
from decimal import Decimal

import pytest
from app.domain.fixed_assets.depreciation.rules import DepreciationRules


def test_straight_line_schedule_is_deterministic_and_ends_at_residual_value() -> None:
    schedule = DepreciationRules.build_schedule(
        acquisition_cost=Decimal("1200.00"),
        residual_value=Decimal("120.00"),
        start_date=date(2026, 1, 15),
        useful_life_months=12,
        method="STRAIGHT_LINE",
    )

    assert schedule[0].scheduled_date == date(2026, 1, 31)
    assert schedule[-1].closing_net_book_value == Decimal("120.00")
    assert sum(row.depreciation_amount for row in schedule) == Decimal("1080.00")
    assert all(row.depreciation_amount >= 0 for row in schedule)


def test_declining_balance_schedule_never_falls_below_residual_value() -> None:
    schedule = DepreciationRules.build_schedule(
        acquisition_cost=Decimal("1000.00"),
        residual_value=Decimal("100.00"),
        start_date=date(2026, 1, 1),
        useful_life_months=12,
        method="DECLINING_BALANCE",
        declining_rate=Decimal("30.000000"),
    )

    assert schedule[-1].closing_net_book_value == Decimal("100.00")
    assert all(row.closing_net_book_value >= Decimal("100.00") for row in schedule)


def test_disposal_calculation_returns_net_book_value_and_gain_or_loss() -> None:
    net_book_value, gain, loss = DepreciationRules.calculate_disposal(
        Decimal("1000.00"), Decimal("400.00"), Decimal("750.00")
    )

    assert (net_book_value, gain, loss) == (
        Decimal("600.00"),
        Decimal("150.00"),
        Decimal("0.00"),
    )


@pytest.mark.parametrize(
    ("residual_value", "method", "declining_rate"),
    [
        (Decimal("1001.00"), "STRAIGHT_LINE", None),
        (Decimal("0.00"), "UNSUPPORTED", None),
        (Decimal("0.00"), "DECLINING_BALANCE", None),
    ],
)
def test_schedule_rejects_invalid_parameters(
    residual_value: Decimal, method: str, declining_rate: Decimal | None
) -> None:
    with pytest.raises(ValueError):
        DepreciationRules.build_schedule(
            acquisition_cost=Decimal("1000.00"),
            residual_value=residual_value,
            start_date=date(2026, 1, 1),
            useful_life_months=12,
            method=method,
            declining_rate=declining_rate,
        )
