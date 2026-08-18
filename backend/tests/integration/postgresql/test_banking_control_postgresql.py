import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from app.models.treasury.bank_statement_import import BankStatementImportLine
from app.models.treasury.banking_control import BankingControlException
from app.services.treasury.bank_statement_import_service import (
    BankStatementImportService,
)
from sqlalchemy import select, text
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


async def _actor(session: AsyncSession):
    from app.models.user import User

    actor = User(
        email=f"bank-control-{uuid4().hex[:12]}@test.local",
        full_name="Bank control test actor",
        hashed_password="not-used-in-integration-test",
        is_active=True,
        is_superuser=False,
    )
    session.add(actor)
    await session.commit()
    return actor


@pytest.mark.asyncio
async def test_postgresql_banking_control_exception_is_tenant_scoped(
    postgres_session: AsyncSession,
):
    organization, _, bank_profile, _, _, _ = await _context(postgres_session)
    actor = await _actor(postgres_session)
    statement = await BankStatementImportService(postgres_session).import_csv(
        organization.id,
        actor.id,
        bank_profile.id,
        f"control-{uuid4().hex[:10]}",
        "control.csv",
        b"external_id,transaction_date,value_date,amount,description,reference\nCTRL-1,2026-03-01,,100.00,Control,REF\n",
    )
    statement_id = statement.id
    line = await postgres_session.scalar(
        select(BankStatementImportLine).where(
            BankStatementImportLine.organization_id == organization.id,
            BankStatementImportLine.statement_import_id == statement_id,
        )
    )
    transaction_id = line.bank_transaction_id
    exception = BankingControlException(
        organization_id=organization.id,
        bank_transaction_id=transaction_id,
        statement_import_id=statement_id,
        status="NO_MATCH",
        reason="No rule",
        last_seen_at=datetime.now(timezone.utc),
    )
    postgres_session.add(exception)
    await postgres_session.commit()
    duplicate = BankingControlException(
        organization_id=organization.id,
        bank_transaction_id=transaction_id,
        statement_import_id=statement_id,
        status="AMBIGUOUS",
        reason="Duplicate",
        last_seen_at=datetime.now(timezone.utc),
    )
    postgres_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await postgres_session.commit()
    await postgres_session.rollback()
    other_organization, _, _, _, _, _ = await _context(postgres_session)
    with pytest.raises(IntegrityError):
        await postgres_session.execute(
            text(
                """
                INSERT INTO banking_control_exceptions
                (id, created_at, updated_at, organization_id, bank_transaction_id,
                 statement_import_id, status, reason, last_seen_at)
                VALUES (:id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :other_org,
                        :transaction_id, :statement_id, 'NO_MATCH', 'cross tenant',
                        CURRENT_TIMESTAMP)
                """
            ),
            {
                "id": uuid4().hex,
                "other_org": other_organization.id,
                "transaction_id": transaction_id,
                "statement_id": statement_id,
            },
        )
        await postgres_session.commit()
