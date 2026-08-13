from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.core.enums.invoicing import InvoiceStatus
from app.domain.accounting.vat.rules import VATRules


@dataclass(frozen=True)
class InvoiceLineCalculation:
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal


@dataclass(frozen=True)
class InvoiceTotals:
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal


class InvoiceRules:
    MONEY_QUANTUM = Decimal("0.01")

    @classmethod
    def calculate_line(
        cls, quantity: Decimal, unit_price: Decimal, tax_rate: Decimal
    ) -> InvoiceLineCalculation:
        if quantity <= 0:
            raise ValueError("Invoice line quantity must be positive")
        if unit_price < 0:
            raise ValueError("Invoice line unit price must be non-negative")
        subtotal = cls.money(quantity * unit_price)
        tax_amount = VATRules.calculate_vat(subtotal, tax_rate)
        return InvoiceLineCalculation(
            subtotal=subtotal,
            tax_amount=tax_amount,
            total=cls.money(subtotal + tax_amount),
        )

    @classmethod
    def aggregate(cls, lines: list[InvoiceLineCalculation]) -> InvoiceTotals:
        if not lines:
            raise ValueError("Invoice requires at least one line")
        return InvoiceTotals(
            subtotal=cls.money(sum((line.subtotal for line in lines), Decimal("0.00"))),
            tax_amount=cls.money(
                sum((line.tax_amount for line in lines), Decimal("0.00"))
            ),
            total_amount=cls.money(
                sum((line.total for line in lines), Decimal("0.00"))
            ),
        )

    @staticmethod
    def validate_dates(invoice_date: date, due_date: date | None) -> None:
        if due_date is not None and due_date < invoice_date:
            raise ValueError("Invoice due date must not precede invoice date")

    @staticmethod
    def validate_issue_transition(status: InvoiceStatus | str) -> None:
        if status != InvoiceStatus.DRAFT:
            raise ValueError("Only draft invoices can be issued")

    @classmethod
    def apply_payment(
        cls,
        total_amount: Decimal,
        paid_amount: Decimal,
        credited_amount: Decimal,
        amount: Decimal,
    ) -> tuple[InvoiceStatus, Decimal, Decimal]:
        cls._validate_settlement(total_amount, paid_amount, credited_amount, amount)
        return cls._settlement_status(
            total_amount, cls.money(paid_amount + amount), credited_amount
        )

    @classmethod
    def apply_credit(
        cls,
        total_amount: Decimal,
        paid_amount: Decimal,
        credited_amount: Decimal,
        amount: Decimal,
    ) -> tuple[InvoiceStatus, Decimal, Decimal]:
        cls._validate_settlement(total_amount, paid_amount, credited_amount, amount)
        return cls._settlement_status(
            total_amount, paid_amount, cls.money(credited_amount + amount)
        )

    @classmethod
    def outstanding_amount(
        cls, total_amount: Decimal, paid_amount: Decimal, credited_amount: Decimal
    ) -> Decimal:
        outstanding = cls.money(total_amount - paid_amount - credited_amount)
        if outstanding < 0:
            raise ValueError("Invoice settlements exceed total amount")
        return outstanding

    @classmethod
    def money(cls, value: Decimal) -> Decimal:
        return value.quantize(cls.MONEY_QUANTUM, rounding=ROUND_HALF_UP)

    @classmethod
    def _validate_settlement(
        cls,
        total_amount: Decimal,
        paid_amount: Decimal,
        credited_amount: Decimal,
        amount: Decimal,
    ) -> None:
        if amount <= 0:
            raise ValueError("Settlement amount must be positive")
        if amount > cls.outstanding_amount(total_amount, paid_amount, credited_amount):
            raise ValueError("Settlement amount exceeds invoice outstanding amount")

    @classmethod
    def _settlement_status(
        cls, total_amount: Decimal, paid_amount: Decimal, credited_amount: Decimal
    ) -> tuple[InvoiceStatus, Decimal, Decimal]:
        outstanding = cls.outstanding_amount(total_amount, paid_amount, credited_amount)
        if outstanding == 0:
            if paid_amount == 0 and credited_amount == total_amount:
                return InvoiceStatus.CANCELLED, paid_amount, credited_amount
            return InvoiceStatus.PAID, paid_amount, credited_amount
        return InvoiceStatus.PARTIALLY_PAID, paid_amount, credited_amount
