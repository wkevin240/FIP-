import os
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from app.models.invoicing.payment_allocation import PaymentAllocation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from tests.integration.treasury.test_treasury_accounting_service import _context

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
async def test_payment_allocation_database_constraints(postgres_session: AsyncSession):
    organization, _, _, _, invoice, _ = await _context(postgres_session)
    from app.models.invoicing.payment import Payment

    payment = Payment(
        organization_id=organization.id,
        invoice_id=invoice.id,
        payment_date=date(2026, 8, 21),
        amount=Decimal("100.00"),
        method="BANK_TRANSFER",
        external_reference=f"PAY-{uuid4().hex}",
        received_at=datetime(2026, 8, 21, 10, 0, 0, tzinfo=UTC).replace(tzinfo=None),
    )
    postgres_session.add(payment)
    await postgres_session.flush()
    allocation = PaymentAllocation(
        organization_id=organization.id,
        payment_id=payment.id,
        invoice_id=invoice.id,
        allocated_amount=Decimal("40.00"),
        idempotency_key=f"ALLOC-{uuid4().hex}",
    )
    postgres_session.add(allocation)
    await postgres_session.commit()

    duplicate = PaymentAllocation(
        organization_id=organization.id,
        payment_id=payment.id,
        invoice_id=invoice.id,
        allocated_amount=Decimal("10.00"),
        idempotency_key=f"ALLOC-{uuid4().hex}",
    )
    postgres_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await postgres_session.commit()
    await postgres_session.rollback()

    negative = PaymentAllocation(
        organization_id=organization.id,
        payment_id=payment.id,
        invoice_id=invoice.id,
        allocated_amount=Decimal("-1.00"),
        idempotency_key=f"ALLOC-{uuid4().hex}",
    )
    postgres_session.add(negative)
    with pytest.raises(IntegrityError):
        await postgres_session.commit()
    await postgres_session.rollback()
