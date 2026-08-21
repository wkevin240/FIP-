import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.models.organization import Organization
from app.models.procurement import PurchaseInvoice, Supplier
from app.models.procurement_approval import PurchaseInvoiceApproval
from sqlalchemy.exc import IntegrityError
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
async def test_purchase_invoice_approval_constraints(postgres_session: AsyncSession):
    suffix = uuid4().hex
    organization = Organization(name=f"Approval test {suffix}")
    postgres_session.add(organization)
    await postgres_session.flush()
    supplier = Supplier(
        organization_id=organization.id,
        supplier_code=f"SUP-{suffix}",
        legal_name="Isolated supplier",
    )
    postgres_session.add(supplier)
    await postgres_session.flush()
    invoice = PurchaseInvoice(
        organization_id=organization.id,
        supplier_id=supplier.id,
        invoice_number=f"PI-{suffix}",
        invoice_date=date(2026, 8, 21),
        status="VALIDATED",
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
    )
    postgres_session.add(invoice)
    await postgres_session.flush()
    organization_id = organization.id
    invoice_id = invoice.id
    await postgres_session.commit()

    approval = PurchaseInvoiceApproval(
        organization_id=organization_id,
        purchase_invoice_id=invoice_id,
        requester_user_id="requester",
        status="PENDING",
    )
    postgres_session.add(approval)
    await postgres_session.commit()

    duplicate = PurchaseInvoiceApproval(
        organization_id=organization_id,
        purchase_invoice_id=invoice_id,
        requester_user_id="another-requester",
        status="PENDING",
    )
    postgres_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await postgres_session.commit()
    await postgres_session.rollback()

    invalid_separation = PurchaseInvoiceApproval(
        organization_id=organization_id,
        purchase_invoice_id=invoice_id,
        requester_user_id="same-user",
        approver_user_id="same-user",
        status="APPROVED",
    )
    postgres_session.add(invalid_separation)
    with pytest.raises(IntegrityError):
        await postgres_session.commit()
    await postgres_session.rollback()
