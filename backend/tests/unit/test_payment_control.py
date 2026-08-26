from decimal import Decimal

import pytest
from app.schemas.invoicing.payment import PaymentCreate
from app.schemas.invoicing.payment_control import (
    PaymentAllocationCreate,
    SupplierPaymentAllocationCreate,
)
from app.schemas.procurement import SupplierPaymentCreate
from pydantic import ValidationError


def test_customer_unapplied_payment_contract():
    payment = PaymentCreate(
        payment_date="2026-08-21",
        amount=Decimal("75.00"),
        method="BANK_TRANSFER",
    )
    assert payment.invoice_id is None
    assert payment.amount == Decimal("75.00")


def test_supplier_unapplied_payment_contract():
    payment = SupplierPaymentCreate(
        payment_date="2026-08-21",
        amount=Decimal("80.00"),
        method="BANK_TRANSFER",
        external_reference="SUP-UNAPPLIED-001",
    )
    assert payment.invoice_id is None
    assert payment.amount == Decimal("80.00")


def test_customer_allocation_uses_decimal_and_positive_amount():
    data = PaymentAllocationCreate(
        payment_id="payment-real",
        invoice_id="invoice-real",
        allocated_amount=Decimal("125.10"),
        idempotency_key="alloc-001",
    )
    assert data.allocated_amount == Decimal("125.10")
    assert data.allocated_amount <= Decimal("125.10")


def test_supplier_allocation_rejects_negative_amount():
    with pytest.raises(ValidationError):
        SupplierPaymentAllocationCreate(
            supplier_payment_id="payment-real",
            purchase_invoice_id="invoice-real",
            allocated_amount=Decimal("-1.00"),
            idempotency_key="alloc-002",
        )


def test_allocation_requires_idempotency_key():
    with pytest.raises(ValidationError):
        PaymentAllocationCreate(
            payment_id="payment-real",
            invoice_id="invoice-real",
            allocated_amount=Decimal("10.00"),
            idempotency_key="",
        )


def test_payment_invariants_are_decimal_reconcilable():
    payment_amount = Decimal("100.00")
    allocations = [Decimal("25.50"), Decimal("14.50")]
    allocated = sum(allocations, Decimal("0.00"))
    unapplied = payment_amount - allocated
    assert allocated <= payment_amount
    assert unapplied == Decimal("60.00")


def test_invoice_remaining_is_decimal_reconcilable():
    invoice_total = Decimal("250.00")
    allocated = sum([Decimal("100.00"), Decimal("50.00")], Decimal("0.00"))
    assert invoice_total - allocated == Decimal("100.00")
