from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class ValuedStockBalance:
    quantity: Decimal
    total_value: Decimal
    average_unit_cost: Decimal


class StockValuationRules:
    QUANTITY_QUANTUM = Decimal("0.001")
    MONEY_QUANTUM = Decimal("0.01")
    COST_QUANTUM = Decimal("0.0001")

    @classmethod
    def receipt(
        cls,
        balance: ValuedStockBalance,
        quantity: Decimal,
        unit_cost: Decimal,
    ) -> tuple[ValuedStockBalance, Decimal]:
        cls._validate_positive_quantity(quantity)
        cls._validate_non_negative_cost(unit_cost)
        received_value = cls.money(quantity * unit_cost)
        return cls.increase(balance, quantity, received_value), received_value

    @classmethod
    def increase(
        cls,
        balance: ValuedStockBalance,
        quantity: Decimal,
        total_value: Decimal,
    ) -> ValuedStockBalance:
        cls._validate_positive_quantity(quantity)
        cls._validate_non_negative_value(total_value)
        new_quantity = cls.quantity(balance.quantity + quantity)
        new_total_value = cls.money(balance.total_value + total_value)
        return ValuedStockBalance(
            quantity=new_quantity,
            total_value=new_total_value,
            average_unit_cost=cls.average_cost(new_total_value, new_quantity),
        )

    @classmethod
    def issue(
        cls, balance: ValuedStockBalance, quantity: Decimal
    ) -> tuple[ValuedStockBalance, Decimal, Decimal]:
        cls._validate_positive_quantity(quantity)
        if balance.quantity < quantity:
            raise ValueError("Insufficient stock quantity")
        unit_cost = balance.average_unit_cost
        issued_value = cls.money(quantity * unit_cost)
        new_quantity = cls.quantity(balance.quantity - quantity)
        if new_quantity == 0:
            return (
                ValuedStockBalance(
                    quantity=Decimal("0.000"),
                    total_value=Decimal("0.00"),
                    average_unit_cost=Decimal("0.0000"),
                ),
                unit_cost,
                issued_value,
            )
        new_total_value = cls.money(balance.total_value - issued_value)
        if new_total_value < 0:
            raise ValueError("Stock value cannot become negative")
        return (
            ValuedStockBalance(
                quantity=new_quantity,
                total_value=new_total_value,
                average_unit_cost=cls.average_cost(new_total_value, new_quantity),
            ),
            unit_cost,
            issued_value,
        )

    @classmethod
    def quantity(cls, value: Decimal) -> Decimal:
        return value.quantize(cls.QUANTITY_QUANTUM, rounding=ROUND_HALF_UP)

    @classmethod
    def money(cls, value: Decimal) -> Decimal:
        return value.quantize(cls.MONEY_QUANTUM, rounding=ROUND_HALF_UP)

    @classmethod
    def average_cost(cls, total_value: Decimal, quantity: Decimal) -> Decimal:
        if quantity == 0:
            return Decimal("0.0000")
        return (total_value / quantity).quantize(
            cls.COST_QUANTUM, rounding=ROUND_HALF_UP
        )

    @staticmethod
    def _validate_positive_quantity(quantity: Decimal) -> None:
        if quantity <= 0:
            raise ValueError("Stock quantity must be positive")

    @staticmethod
    def _validate_non_negative_cost(unit_cost: Decimal) -> None:
        if unit_cost < 0:
            raise ValueError("Unit cost must be non-negative")

    @staticmethod
    def _validate_non_negative_value(total_value: Decimal) -> None:
        if total_value < 0:
            raise ValueError("Stock value must be non-negative")
