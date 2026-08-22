import os
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from app.models.invoicing.payment import Payment
from app.models.organization import Organization
from app.services.treasury.accounting_treasury_reconciliation_service import (
    AccountingTreasuryReconciliationService,
)
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
async def test_reconciliation_is_tenant_scoped_on_postgresql(
    postgres_session: AsyncSession,
):
    suffix = uuid4().hex
    organization_a = Organization(name=f"Reconciliation A {suffix}")
    organization_b = Organization(name=f"Reconciliation B {suffix}")
    postgres_session.add_all([organization_a, organization_b])
    await postgres_session.flush()
    postgres_session.add(
        Payment(
            organization_id=organization_b.id,
            payment_date=date(2026, 8, 22),
            amount=Decimal("100.00"),
            method="BANK_TRANSFER",
            external_reference=f"TENANT-B-{suffix}",
            received_at=datetime(2026, 8, 22, tzinfo=UTC).replace(tzinfo=None),
        )
    )
    await postgres_session.commit()

    result = await AccountingTreasuryReconciliationService(postgres_session).report(
        organization_a.id, date(2026, 8, 22)
    )
    assert result.status == "NOT_READY"
    assert result.payments == 0
    assert "NO_PAYMENT_SOURCE" in result.blockers


@pytest.mark.asyncio
async def test_as_of_excludes_future_payment_on_postgresql(
    postgres_session: AsyncSession,
):
    suffix = uuid4().hex
    organization = Organization(name=f"AS OF {suffix}")
    postgres_session.add(organization)
    await postgres_session.flush()
    postgres_session.add(
        Payment(
            organization_id=organization.id,
            payment_date=date(2026, 8, 23),
            amount=Decimal("75.00"),
            method="BANK_TRANSFER",
            external_reference=f"FUTURE-{suffix}",
            received_at=datetime(2026, 8, 23, tzinfo=UTC).replace(tzinfo=None),
        )
    )
    await postgres_session.commit()

    result = await AccountingTreasuryReconciliationService(postgres_session).report(
        organization.id, date(2026, 8, 22)
    )
    assert result.status == "NOT_READY"
    assert result.payments == 0
    assert result.blockers == ["NO_PAYMENT_SOURCE", "NO_BANK_TRANSACTION_SOURCE"]
