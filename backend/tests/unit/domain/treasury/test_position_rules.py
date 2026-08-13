from decimal import Decimal

import pytest
from app.domain.treasury.position.rules import TreasuryPositionRules


def test_calculates_statement_ledger_and_reconciliation_positions() -> None:
    position = TreasuryPositionRules.calculate(
        opening_balance=Decimal("1000.00"),
        statement_amounts=[Decimal("250.105"), Decimal("-50.00")],
        ledger_balance=Decimal("1200.104"),
        unreconciled_amount=Decimal("75.005"),
        unreconciled_transaction_count=2,
    )

    assert position.statement_balance == Decimal("1200.11")
    assert position.ledger_balance == Decimal("1200.10")
    assert position.reconciliation_gap == Decimal("0.01")
    assert position.unreconciled_amount == Decimal("75.01")
    assert position.unreconciled_transaction_count == 2


def test_supports_overdraft_opening_balances() -> None:
    position = TreasuryPositionRules.calculate(
        opening_balance=Decimal("-100.00"),
        statement_amounts=[Decimal("25.00")],
        ledger_balance=Decimal("-75.00"),
        unreconciled_amount=Decimal("0.00"),
        unreconciled_transaction_count=0,
    )

    assert position.statement_balance == Decimal("-75.00")
    assert position.reconciliation_gap == Decimal("0.00")


def test_rejects_negative_unreconciled_transaction_count() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        TreasuryPositionRules.calculate(
            opening_balance=Decimal("0.00"),
            statement_amounts=[],
            ledger_balance=Decimal("0.00"),
            unreconciled_amount=Decimal("0.00"),
            unreconciled_transaction_count=-1,
        )
