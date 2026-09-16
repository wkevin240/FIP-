from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.supplier_invoice import SupplierInvoiceStatus
from app.services.supplier_invoice_service import SupplierInvoiceService


@pytest.mark.asyncio
async def test_approved_exposure_aging_groups_by_supplier_and_currency() -> None:
    as_of = date(2026, 9, 16)
    supplier = SimpleNamespace(legal_name="Supplier One")
    invoices = [
        SimpleNamespace(
            supplier_id="supplier-1",
            supplier=supplier,
            currency_code="XAF",
            due_date=date(2026, 9, 16),
            total_amount=Decimal("100.00"),
            status=SupplierInvoiceStatus.APPROVED,
        ),
        SimpleNamespace(
            supplier_id="supplier-1",
            supplier=supplier,
            currency_code="XAF",
            due_date=date(2026, 8, 17),
            total_amount=Decimal("50.25"),
            status=SupplierInvoiceStatus.APPROVED,
        ),
        SimpleNamespace(
            supplier_id="supplier-1",
            supplier=supplier,
            currency_code="USD",
            due_date=date(2026, 7, 18),
            total_amount=Decimal("10.00"),
            status=SupplierInvoiceStatus.APPROVED,
        ),
    ]

    class FakeRepository:
        async def list_approved_for_exposure(self, organization_id: str):
            assert organization_id == "org-1"
            return invoices

    service = SupplierInvoiceService(None)  # type: ignore[arg-type]
    service.repository = FakeRepository()

    rows = await service.approved_exposure_aging("org-1", as_of)

    assert rows == [
        {
            "supplier_id": "supplier-1",
            "supplier_name": "Supplier One",
            "currency_code": "USD",
            "current_amount": Decimal("0.00"),
            "overdue_1_30_amount": Decimal("0.00"),
            "overdue_31_60_amount": Decimal("10.00"),
            "overdue_61_90_amount": Decimal("0.00"),
            "overdue_90_plus_amount": Decimal("0.00"),
            "total_amount": Decimal("10.00"),
        },
        {
            "supplier_id": "supplier-1",
            "supplier_name": "Supplier One",
            "currency_code": "XAF",
            "current_amount": Decimal("100.00"),
            "overdue_1_30_amount": Decimal("50.25"),
            "overdue_31_60_amount": Decimal("0.00"),
            "overdue_61_90_amount": Decimal("0.00"),
            "overdue_90_plus_amount": Decimal("0.00"),
            "total_amount": Decimal("150.25"),
        },
    ]
