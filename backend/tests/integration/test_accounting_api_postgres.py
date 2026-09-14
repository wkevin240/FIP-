import os
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.core.enums.users import MembershipRole
from app.core.security import create_access_token
from app.main import create_application
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.journal_entry import JournalEntry
from app.models.audit_log import AuditLog
from app.models.ledger_posting import LedgerPosting
from app.models.membership import OrganizationMembership
from app.models.organization import Organization
from app.models.user import User


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
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    organization_id = "api-contract-org"
    creator_id = "api-contract-creator"
    outsider_id = "api-contract-outsider"
    fiscal_year_id = "api-contract-year"
    fiscal_period_id = "api-contract-period"
    debit_id = "api-contract-debit"
    credit_id = "api-contract-credit"

    async with session_factory() as session:
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
                    id=outsider_id,
                    email="api-contract-outsider@example.invalid",
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
                    user_id=outsider_id,
                    organization_id=organization_id,
                    role=MembershipRole.MANAGER.value,
                    is_active=True,
                ),
            ]
        )
        await session.commit()

    application = create_application()
    creator_token = create_access_token(creator_id, organization_id)
    outsider_token = create_access_token(outsider_id, organization_id)
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

    try:
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
                headers={"Authorization": f"Bearer {outsider_token}"},
            )
            assert manager_post.status_code == 403
            assert manager_post.json()["detail"] == "Permission denied"
    finally:
        async with session_factory() as session:
            await session.execute(delete(LedgerPosting).where(LedgerPosting.organization_id == organization_id))
            await session.execute(delete(JournalEntry).where(JournalEntry.organization_id == organization_id))
            await session.execute(delete(AuditLog).where(AuditLog.organization_id == organization_id))
            await session.execute(delete(OrganizationMembership).where(OrganizationMembership.organization_id == organization_id))
            await session.execute(delete(Account).where(Account.organization_id == organization_id))
            await session.execute(delete(FiscalPeriod).where(FiscalPeriod.organization_id == organization_id))
            await session.execute(delete(FiscalYear).where(FiscalYear.organization_id == organization_id))
            await session.execute(delete(User).where(User.id.in_([creator_id, outsider_id])))
            await session.execute(delete(Organization).where(Organization.id == organization_id))
            await session.commit()
        await engine.dispose()
