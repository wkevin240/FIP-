import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.models.fixed_assets.asset import FixedAsset
from app.models.organization import Organization
from sqlalchemy import inspect
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
async def test_fixed_assets_migration_creates_tables_and_enforces_cost_constraint(
    postgres_session: AsyncSession,
) -> None:
    table_names = await postgres_session.run_sync(
        lambda sync_session: inspect(sync_session.bind).get_table_names()
    )
    assert {
        "fixed_asset_accounting_profiles",
        "fixed_asset_categories",
        "fixed_assets",
        "fixed_asset_components",
        "fixed_asset_depreciation_plans",
        "fixed_asset_depreciation_schedule_lines",
        "fixed_asset_disposals",
        "fixed_asset_audit_events",
    }.issubset(table_names)

    organization = Organization(name=f"PostgreSQL fixed asset org {uuid4().hex[:12]}")
    postgres_session.add(organization)
    await postgres_session.commit()
    organization_id = organization.id

    invalid_asset = FixedAsset(
        organization_id=organization_id,
        category_id="missing-category",
        asset_code="PG-FA-INVALID",
        name="Invalid fixed asset",
        acquisition_date=date(2026, 1, 1),
        acquisition_cost=Decimal("-1.00"),
        residual_value=Decimal("0.00"),
        currency="XAF",
        status="DRAFT",
    )
    postgres_session.add(invalid_asset)
    with pytest.raises(IntegrityError):
        await postgres_session.commit()
    await postgres_session.rollback()
