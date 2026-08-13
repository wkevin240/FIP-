from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class TreasuryPosition:
    statement_balance: Decimal
    ledger_balance: Decimal
    reconciliation_gap: Decimal
    unreconciled_amount: Decimal
    unreconciled_transaction_count: int


class TreasuryPositionRules:
    MONEY_QUANTUM = Decimal("0.01")

    @classmethod
    def calculate(
        cls,
        opening_balance: Decimal,
        statement_amounts: Iterable[Decimal],
        ledger_balance: Decimal,
        unreconciled_amount: Decimal,
        unreconciled_transaction_count: int,
    ) -> TreasuryPosition:
        statement_balance = cls.money(
            opening_balance + sum(statement_amounts, Decimal("0.00"))
        )
        normalized_ledger_balance = cls.money(ledger_balance)
        if unreconciled_transaction_count < 0:
            raise ValueError("Unreconciled transaction count must not be negative")
        return TreasuryPosition(
            statement_balance=statement_balance,
            ledger_balance=normalized_ledger_balance,
            reconciliation_gap=cls.money(statement_balance - normalized_ledger_balance),
            unreconciled_amount=cls.money(unreconciled_amount),
            unreconciled_transaction_count=unreconciled_transaction_count,
        )

    @classmethod
    def money(cls, value: Decimal) -> Decimal:
        return value.quantize(cls.MONEY_QUANTUM, rounding=ROUND_HALF_UP)
