from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.supplier_invoice import SupplierInvoiceStatus
from app.services.supplier_invoice_service import SupplierInvoiceService


@pytest.mark.asyncio
async def test_creator_cannot_approve_own_invoice() -> None:
    service = SupplierInvoiceService.__new__(SupplierInvoiceService)
    service.repository = SimpleNamespace(get_for_update=_get_invoice)

    with pytest.raises(HTTPException) as exc_info:
        await service.approve("org-1", "invoice-1", "actor-1")

    assert exc_info.value.status_code == 403
    assert "cannot approve" in exc_info.value.detail


async def _get_invoice(organization_id: str, invoice_id: str):
    return SimpleNamespace(
        id="invoice-1",
        created_by="actor-1",
        supplier_id="supplier-1",
        status=SupplierInvoiceStatus.DRAFT,
    )
