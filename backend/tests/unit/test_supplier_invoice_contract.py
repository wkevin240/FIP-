from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.supplier_invoice import SupplierInvoiceCreate


def valid_payload() -> dict:
    return {
        "supplier_id": "supplier-1",
        "invoice_number": " FAC-2026-001 ",
        "invoice_date": date(2026, 9, 1),
        "due_date": date(2026, 10, 1),
        "currency_code": "xaf",
        "subtotal": Decimal("100000.00"),
        "tax_amount": Decimal("19000.00"),
        "total_amount": Decimal("119000.00"),
    }


def test_invoice_contract_normalizes_identity_fields() -> None:
    invoice = SupplierInvoiceCreate(**valid_payload())
    assert invoice.invoice_number == "FAC-2026-001"
    assert invoice.currency_code == "XAF"


def test_invoice_contract_rejects_total_mismatch() -> None:
    payload = valid_payload()
    payload["total_amount"] = Decimal("120000.00")
    with pytest.raises(ValidationError, match="Total amount must equal"):
        SupplierInvoiceCreate(**payload)


def test_invoice_contract_rejects_due_date_before_invoice_date() -> None:
    payload = valid_payload()
    payload["due_date"] = date(2026, 8, 31)
    with pytest.raises(ValidationError, match="Due date cannot be before"):
        SupplierInvoiceCreate(**payload)


def test_invoice_contract_rejects_invalid_currency_code() -> None:
    payload = valid_payload()
    payload["currency_code"] = "123"
    with pytest.raises(ValidationError, match="three-letter code"):
        SupplierInvoiceCreate(**payload)
