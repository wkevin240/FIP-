from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.supplier_invoice import SupplierInvoiceStatus
from app.schemas.supplier_invoice import SupplierInvoiceResponse


def _response(**overrides):
    data = {
        "id": "invoice-id",
        "organization_id": "organization-id",
        "supplier_id": "supplier-id",
        "invoice_number": "INV-1",
        "invoice_date": "2026-09-01",
        "due_date": "2026-09-30",
        "currency_code": "XAF",
        "subtotal": "100.00",
        "tax_amount": "0.00",
        "total_amount": "100.00",
        "description": None,
        "status": SupplierInvoiceStatus.APPROVED,
        "created_by": "creator-id",
        "updated_by": "approver-id",
        "approved_by": "approver-id",
        "approved_at": datetime(2026, 9, 16, 20, 0, tzinfo=timezone.utc),
    }
    data.update(overrides)
    return SupplierInvoiceResponse.model_validate(data)


def test_approved_response_preserves_utc_timestamp() -> None:
    response = _response()

    assert response.status is SupplierInvoiceStatus.APPROVED
    assert response.approved_at is not None
    assert response.approved_at.utcoffset() == timezone.utc.utcoffset(None)


def test_approved_response_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _response(approved_at=datetime(2026, 9, 16, 20, 0))
