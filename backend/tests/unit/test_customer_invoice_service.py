from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.models.customer_invoice import CustomerInvoiceStatus
from app.schemas.invoicing.customer_invoice import CustomerInvoiceCreate, CustomerInvoiceUpdate
from app.services.invoicing.customer_invoice_service import CustomerInvoiceService


def invoice_entity(**overrides):
    values = {
        "id": "invoice-1",
        "organization_id": "org-1",
        "customer_id": "customer-1",
        "invoice_number": "INV-001",
        "invoice_date": date(2026, 11, 1),
        "due_date": date(2026, 11, 30),
        "currency_code": "XAF",
        "subtotal": Decimal("100.00"),
        "tax_amount": Decimal("19.25"),
        "total_amount": Decimal("119.25"),
        "status": CustomerInvoiceStatus.DRAFT,
        "issued_at": None,
        "issued_by": None,
        "created_by": "creator-1",
        "updated_by": "creator-1",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_service(invoice=None, customer=None):
    service = CustomerInvoiceService.__new__(CustomerInvoiceService)
    service.session = SimpleNamespace(
        scalar=AsyncMock(return_value=customer),
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    service.repository = SimpleNamespace(
        get=AsyncMock(return_value=invoice),
        get_for_update=AsyncMock(return_value=invoice),
        add=lambda value: None,
        list=AsyncMock(return_value=[]),
    )
    service.audit_repository = SimpleNamespace(append=AsyncMock())
    return service


def valid_invoice():
    return CustomerInvoiceCreate(
        customer_id="customer-1",
        invoice_number="INV-001",
        invoice_date=date(2026, 11, 1),
        due_date=date(2026, 11, 30),
        currency_code="XAF",
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("19.25"),
        total_amount=Decimal("119.25"),
    )


@pytest.mark.asyncio
async def test_create_rejects_customer_not_found_in_current_tenant():
    service = make_service(customer=None)
    with pytest.raises(HTTPException) as error:
        await service.create("org-1", "creator-1", valid_invoice())
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_create_rejects_inactive_customer():
    service = make_service(customer=SimpleNamespace(is_active=False))
    with pytest.raises(HTTPException) as error:
        await service.create("org-1", "creator-1", valid_invoice())
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_issued_invoice_is_immutable():
    service = make_service(invoice=invoice_entity(status=CustomerInvoiceStatus.ISSUED))
    with pytest.raises(HTTPException) as error:
        await service.update(
            "org-1", "invoice-1", "manager-1",
            CustomerInvoiceUpdate(invoice_number="INV-002"),
        )
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_creator_cannot_issue_own_invoice():
    service = make_service(invoice=invoice_entity())
    with pytest.raises(HTTPException) as error:
        await service.issue("org-1", "invoice-1", "creator-1")
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_another_user_can_issue_and_audit_invoice():
    invoice = invoice_entity()
    service = make_service(invoice=invoice)
    result = await service.issue("org-1", "invoice-1", "issuer-1")
    assert result.status == CustomerInvoiceStatus.ISSUED
    assert result.issued_by == "issuer-1"
    assert result.issued_at is not None and result.issued_at.tzinfo is not None
    service.audit_repository.append.assert_awaited_once()
    service.session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_passes_tenant_and_filter_parameters():
    service = make_service()
    await service.list(
        "org-1", skip=5, limit=15, customer_id="customer-1",
        invoice_status=CustomerInvoiceStatus.ISSUED, due_before=date(2026, 11, 30),
    )
    service.repository.list.assert_awaited_once_with(
        "org-1", skip=5, limit=15, customer_id="customer-1",
        status=CustomerInvoiceStatus.ISSUED, due_before=date(2026, 11, 30),
    )
