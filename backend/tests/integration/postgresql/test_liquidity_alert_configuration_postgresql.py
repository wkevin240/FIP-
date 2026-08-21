import os
from datetime import date
from uuid import uuid4

import pytest
from app.models.treasury.liquidity_alert import LiquidityAlertConfiguration
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
async def test_liquidity_alert_configuration_constraints(
    postgres_session: AsyncSession,
):
    organization, _, _, _, _, _ = await _context(postgres_session)
    first = LiquidityAlertConfiguration(
        organization_id=organization.id,
        alert_code="LOW_LIQUIDITY",
        enabled=True,
        threshold_amount="1000.00",
        effective_from=date(2026, 1, 1),
    )
    postgres_session.add(first)
    await postgres_session.commit()

    duplicate = LiquidityAlertConfiguration(
        organization_id=organization.id,
        alert_code="LOW_LIQUIDITY",
        enabled=True,
        threshold_amount="2000.00",
    )
    postgres_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await postgres_session.commit()
    await postgres_session.rollback()

    negative = LiquidityAlertConfiguration(
        organization_id=organization.id,
        alert_code="LIQUIDITY_GAP",
        enabled=True,
        threshold_amount="-1.00",
    )
    postgres_session.add(negative)
    with pytest.raises(IntegrityError):
        await postgres_session.commit()
    await postgres_session.rollback()

    invalid_dates = LiquidityAlertConfiguration(
        organization_id=organization.id,
        alert_code="NEGATIVE_FORECAST",
        enabled=True,
        effective_from=date(2026, 2, 1),
        effective_to=date(2026, 1, 1),
    )
    postgres_session.add(invalid_dates)
    with pytest.raises(IntegrityError):
        await postgres_session.commit()
    await postgres_session.rollback()

    assert first.id
    assert first.organization_id == organization.id
    assert uuid4()
