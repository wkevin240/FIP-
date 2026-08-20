import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.models.organization import Organization
from app.models.procurement import PurchaseInvoice, Supplier, SupplierPayment
from app.schemas.procurement import SupplierPaymentAllocationCreate
from app.services.supplier_payment_allocation_service import (
    SupplierPaymentAllocationService,
)
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

POSTGRES_TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_DATABASE_URL,
    reason="PostgreSQL integration database is not configured",
)


@pytest.fixture
async def postgres_session():
    engine = create_async_engine(POSTGRES_TEST_DATABASE_URL, echo=False)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_postgresql_supplier_payment_can_allocate_across_invoices_without_overallocation(
    postgres_session: AsyncSession,
):
    organization = Organization(name=f"AP allocation {uuid4().hex}")
    postgres_session.add(organization)
    await postgres_session.flush()
    supplier = Supplier(
        organization_id=organization.id,
        supplier_code=f"SUP-{uuid4().hex[:10]}",
        legal_name="Real integration supplier",
    )
    postgres_session.add(supplier)
    await postgres_session.flush()
    invoices = [
        PurchaseInvoice(
            organization_id=organization.id,
            supplier_id=supplier.id,
            invoice_number=f"AP-{uuid4().hex[:10]}-{index}",
            invoice_date=date(2026, 1, 1),
            due_date=date(2026, 2, 1),
            status="VALIDATED",
            subtotal=Decimal("50.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("50.00"),
        )
        for index in (1, 2)
    ]
    postgres_session.add_all(invoices)
    payment = SupplierPayment(
        organization_id=organization.id,
        payment_date=date(2026, 1, 10),
        amount=Decimal("100.00"),
        method="BANK",
        external_reference=f"AP-PAY-{uuid4().hex}",
    )
    postgres_session.add(payment)
    await postgres_session.commit()

    service = SupplierPaymentAllocationService(postgres_session)
    first = await service.allocate(
        organization.id,
        "postgres-ap-tester",
        payment.id,
        SupplierPaymentAllocationCreate(
            invoice_id=invoices[0].id, amount=Decimal("40.00")
        ),
        "ap-allocation-001",
    )
    second = await service.allocate(
        organization.id,
        "postgres-ap-tester",
        payment.id,
        SupplierPaymentAllocationCreate(
            invoice_id=invoices[1].id, amount=Decimal("60.00")
        ),
        "ap-allocation-002",
    )
    assert first.amount == Decimal("40.00")
    assert second.amount == Decimal("60.00")
    reconciliation = await service.reconcile(organization.id, payment.id)
    assert reconciliation.allocated_amount == Decimal("100.00")
    assert reconciliation.unapplied_amount == Decimal("0.00")
    assert reconciliation.status == "FULLY_ALLOCATED"

    duplicate = await service.allocate(
        organization.id,
        "postgres-ap-tester",
        payment.id,
        SupplierPaymentAllocationCreate(
            invoice_id=invoices[0].id, amount=Decimal("40.00")
        ),
        "ap-allocation-001",
    )
    assert duplicate.id == first.id

    with pytest.raises(HTTPException, match="exceeds payment amount"):
        await service.allocate(
            organization.id,
            "postgres-ap-tester",
            payment.id,
            SupplierPaymentAllocationCreate(
                invoice_id=invoices[0].id, amount=Decimal("0.01")
            ),
            "ap-allocation-over",
        )
