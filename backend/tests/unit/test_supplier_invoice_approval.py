from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.supplier_invoice import SupplierInvoiceStatus
from app.services.supplier_invoice_service import SupplierInvoiceService


@pytest.mark.asyncio
async def test_creator_cannot_approve_own_invoice() -> None:
    service = SupplierInvoiceService.__new__(SupplierInvoiceService)
    service.repository = SimpleNamespace(
        get_for_update=lambda organization_id, invoice_id: _invoice("actor-1")
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.approve("org-1", "invoice-1", "actor-1")

    assert exc_info.value.status_code == 403
    assert "cannot approve" in exc_info.value.detail


def _invoice(created_by: str):
    return SimpleNamespace(
        id="invoice-1",
        created_by=created_by,
        supplier_id="supplier-1",
        status=SupplierInvoiceStatus.DRAFT,
    )
