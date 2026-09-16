import pytest
from pydantic import ValidationError

from app.schemas.supplier_invoice import SupplierInvoiceCreate, SupplierInvoiceUpdate


def _payload(currency_code: str) -> dict:
    return {
        "supplier_id": "supplier-1",
        "invoice_number": "INV-001",
        "invoice_date": "2026-09-15",
        "due_date": "2026-10-15",
        "currency_code": currency_code,
        "subtotal": "100.00",
        "tax_amount": "18.00",
        "total_amount": "118.00",
    }


def test_supplier_invoice_currency_code_is_canonicalized_to_uppercase() -> None:
    invoice = SupplierInvoiceCreate(**_payload(" xaf "))

    assert invoice.currency_code == "XAF"


def test_supplier_invoice_currency_code_rejects_non_ascii_letters() -> None:
    with pytest.raises(ValidationError, match="three-letter code"):
        SupplierInvoiceCreate(**_payload("ÉUR"))


def test_supplier_invoice_update_currency_code_rejects_non_ascii_letters() -> None:
    with pytest.raises(ValidationError, match="three-letter code"):
        SupplierInvoiceUpdate(currency_code="ÉUR")
