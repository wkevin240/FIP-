from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.invoicing.customer_invoice import CustomerInvoiceCreate, CustomerInvoiceUpdate


def payload():
    return {
        "customer_id": "customer-1",
        "invoice_number": "INV-001",
        "invoice_date": date(2026, 11, 1),
        "due_date": date(2026, 11, 30),
        "currency_code": " xaf ",
        "subtotal": Decimal("100.00"),
        "tax_amount": Decimal("19.25"),
        "total_amount": Decimal("119.25"),
    }


def test_create_normalizes_currency_and_text():
    invoice = CustomerInvoiceCreate(**payload())
    assert invoice.invoice_number == "INV-001"
    assert invoice.currency_code == "XAF"


@pytest.mark.parametrize("changes", [
    {"due_date": date(2026, 10, 31)},
    {"total_amount": Decimal("120.00")},
    {"subtotal": Decimal("-0.01")},
    {"tax_amount": Decimal("19.999")},
    {"total_amount": Decimal("1.001")},
    {"currency_code": "€AF"},
    {"currency_code": "XA"},
    {"invoice_number": " "},
])
def test_create_rejects_invalid_invoice_values(changes):
    data = payload()
    data.update(changes)
    with pytest.raises(ValidationError):
        CustomerInvoiceCreate(**data)


def test_create_rejects_caller_controlled_status():
    data = payload()
    data["status"] = "ISSUED"
    with pytest.raises(ValidationError):
        CustomerInvoiceCreate(**data)


def test_update_rejects_unknown_fields_and_blank_invoice_number():
    with pytest.raises(ValidationError):
        CustomerInvoiceUpdate(invoice_number=" ")
    with pytest.raises(ValidationError):
        CustomerInvoiceUpdate(status="ISSUED")


def test_update_supports_partial_changes():
    update = CustomerInvoiceUpdate(invoice_number=" INV-002 ", currency_code="xaf")
    assert update.invoice_number == "INV-002"
    assert update.currency_code == "XAF"
