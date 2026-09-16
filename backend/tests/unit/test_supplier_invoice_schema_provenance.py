from datetime import date
from decimal import Decimal

from app.schemas.supplier_invoice import SupplierInvoiceResponse


def test_supplier_invoice_response_allows_missing_optional_approval_provenance() -> None:
    response = SupplierInvoiceResponse(
        supplier_id="supplier-1",
        invoice_number="INV-001",
        invoice_date=date(2026, 9, 1),
        due_date=date(2026, 9, 30),
        currency_code="XAF",
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("19.25"),
        total_amount=Decimal("119.25"),
        id="invoice-1",
        organization_id="org-1",
        status="DRAFT",
        created_by="user-1",
        updated_by="user-1",
    )

    assert response.approved_by is None
    assert response.approved_at is None
