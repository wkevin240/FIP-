import os
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.dependencies import get_db
from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.core.enums.users import MembershipRole
from app.core.security import create_access_token
from app.main import create_application
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.organization import Organization
from app.models.membership import OrganizationMembership
from app.models.user import User


class TransactionScopedSession(AsyncSession):
    async def commit(self) -> None:
        await self.flush()


@pytest.mark.asyncio
async def test_journal_api_uses_migrated_postgres_contract() -> None:
    server = os.getenv("POSTGRES_SERVER")
    if not server:
        pytest.skip("PostgreSQL integration environment is not configured")

    database_uri = (
        f"postgresql+asyncpg://{os.getenv('POSTGRES_USER', 'fip_user')}"
        f":{os.getenv('POSTGRES_PASSWORD', 'fip_password')}@{server}"
        f":{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'fip_db')}"
    )
    engine = create_async_engine(database_uri, pool_pre_ping=True)

    organization_id = "api-contract-org"
    creator_id = "api-contract-creator"
    manager_id = "api-contract-manager"
    fiscal_year_id = "api-contract-year"
    fiscal_period_id = "api-contract-period"
    debit_id = "api-contract-debit"
    credit_id = "api-contract-credit"

    application = create_application()

    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = TransactionScopedSession(bind=connection, expire_on_commit=False)

        async def override_get_db():
            yield session

        application.dependency_overrides[get_db] = override_get_db

        try:
            session.add_all(
                [
                    Organization(id=organization_id, name="api-contract-org"),
                    User(
                        id=creator_id,
                        email="api-contract-creator@example.invalid",
                        hashed_password="integration-only",
                        is_active=True,
                        is_superuser=False,
                    ),
                    User(
                        id=manager_id,
                        email="api-contract-manager@example.invalid",
                        hashed_password="integration-only",
                        is_active=True,
                        is_superuser=False,
                    ),
                    FiscalYear(
                        id=fiscal_year_id,
                        organization_id=organization_id,
                        name="API contract year",
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 12, 31),
                        status=FiscalYearStatus.OPEN,
                    ),
                    FiscalPeriod(
                        id=fiscal_period_id,
                        organization_id=organization_id,
                        fiscal_year_id=fiscal_year_id,
                        name="API contract period",
                        start_date=date(2026, 1, 1),
                        end_date=date(2026, 1, 31),
                        status=FiscalPeriodStatus.OPEN,
                    ),
                    Account(
                        id=debit_id,
                        organization_id=organization_id,
                        code="API-D",
                        name="Integration debit",
                        account_type="EXPENSE",
                        level=1,
                        path="/",
                    ),
                    Account(
                        id=credit_id,
                        organization_id=organization_id,
                        code="API-C",
                        name="Integration credit",
                        account_type="LIABILITY",
                        level=1,
                        path="/",
                    ),
                    OrganizationMembership(
                        user_id=creator_id,
                        organization_id=organization_id,
                        role=MembershipRole.ACCOUNTANT.value,
                        is_active=True,
                    ),
                    OrganizationMembership(
                        user_id=manager_id,
                        organization_id=organization_id,
                        role=MembershipRole.MANAGER.value,
                        is_active=True,
                    ),
                ]
            )
            await session.flush()

            creator_token = create_access_token(creator_id, organization_id)
            manager_token = create_access_token(manager_id, organization_id)
            payload = {
                "fiscal_period_id": fiscal_period_id,
                "entry_date": "2026-01-15",
                "description": "API contract integration proof",
                "idempotency_key": "api-contract-entry-1",
                "lines": [
                    {"account_id": debit_id, "debit": "100.00", "credit": "0.00"},
                    {"account_id": credit_id, "debit": "0.00", "credit": "100.00"},
                ],
            }

            transport = httpx.ASGITransport(app=application)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/accounting/journal-entries/",
                    json=payload,
                    headers={"Authorization": f"Bearer {creator_token}"},
                )
                assert response.status_code == 201, response.text
                created = response.json()
                assert created["organization_id"] == organization_id
                assert created["status"] == "DRAFT"
                assert created["created_by"] == creator_id
                assert created["posted_by"] is None
                assert Decimal(created["lines"][0]["debit"]) == Decimal("100.00")

                entry_id = created["id"]
                read_response = await client.get(
                    f"/api/v1/accounting/journal-entries/{entry_id}",
                    headers={"Authorization": f"Bearer {creator_token}"},
                )
                assert read_response.status_code == 200, read_response.text
                assert read_response.json()["created_by"] == creator_id

                forbidden = await client.post(
                    f"/api/v1/accounting/journal-entries/{entry_id}/post",
                    headers={"Authorization": f"Bearer {creator_token}"},
                )
                assert forbidden.status_code == 403
                assert "creator cannot post" in forbidden.json()["detail"]

                manager_post = await client.post(
                    f"/api/v1/accounting/journal-entries/{entry_id}/post",
                    headers={"Authorization": f"Bearer {manager_token}"},
                )
                assert manager_post.status_code == 403
                assert manager_post.json()["detail"] == "Permission denied"
        finally:
            application.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()
            await engine.dispose()
