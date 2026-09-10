from decimal import Decimal

import pytest

from app.domain.accounting.ledger.trial_balance_control import trial_balance_control


def test_trial_balance_control_accepts_balanced_ledger_rows() -> None:
    result = trial_balance_control(
        [
            {"debit": Decimal("150.00"), "credit": Decimal("0.00")},
            {"debit": Decimal("0.00"), "credit": Decimal("150.00")},
        ]
    )

    assert result == {
        "row_count": 2,
        "total_debit": Decimal("150.00"),
        "total_credit": Decimal("150.00"),
        "balance_difference": Decimal("0.00"),
        "is_balanced": True,
    }


def test_trial_balance_control_exposes_unbalanced_difference() -> None:
    result = trial_balance_control(
        [
            {"debit": Decimal("150.00"), "credit": Decimal("0.00")},
            {"debit": Decimal("0.00"), "credit": Decimal("149.99")},
        ]
    )

    assert result["balance_difference"] == Decimal("0.01")
    assert result["is_balanced"] is False


def test_trial_balance_control_rejects_float_amounts() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        trial_balance_control([{"debit": 1.0, "credit": Decimal("1.00")}])
