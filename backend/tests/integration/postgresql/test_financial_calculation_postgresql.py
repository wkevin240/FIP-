import os
from datetime import date
from uuid import uuid4

import pytest
from app.models.accounting.account import Account
from app.models.accounting.profitability_mapping import ProfitabilityAccountMapping
from app.models.organization import Organization
from app.services.accounting.financial_calculation_service import (
    FinancialCalculationService,
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
async def test_profitability_mapping_is_tenant_scoped_on_postgresql(
    postgres_session: AsyncSession,
):
    suffix = uuid4().hex
    organization_a = Organization(name=f"Profitability A {suffix}")
    organization_b = Organization(name=f"Profitability B {suffix}")
    postgres_session.add_all([organization_a, organization_b])
    await postgres_session.flush()
    account = Account(
        organization_id=organization_b.id,
        code=f"70{suffix[:8]}",
        name="Tenant B revenue",
        account_type="REVENUE",
        path="/",
    )
    postgres_session.add(account)
    await postgres_session.flush()
    postgres_session.add(
        ProfitabilityAccountMapping(
            organization_id=organization_b.id,
            account_id=account.id,
            category="REVENUE",
        )
    )
    await postgres_session.commit()

    result = await FinancialCalculationService(postgres_session).profitability(
        organization_a.id, date(2026, 1, 1), date(2026, 1, 31)
    )
    assert result.status == "NOT_READY"
    assert result.source_line_count == 0
    assert result.metrics[0].value is None


@pytest.mark.asyncio
async def test_profitability_rejects_inverted_period_before_database_aggregation(
    postgres_session: AsyncSession,
):
    service = FinancialCalculationService(postgres_session)
    with pytest.raises(HTTPException, match="period_start must be before period_end"):
        await service.profitability("missing-org", date(2026, 2, 1), date(2026, 1, 31))
