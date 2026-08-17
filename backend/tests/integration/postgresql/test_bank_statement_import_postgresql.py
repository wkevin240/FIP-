import asyncio
import os
from uuid import uuid4

import pytest
from app.models.accounting.bank_transaction import BankTransaction
from app.models.audit.audit_event import AuditEvent
from app.models.treasury.bank_statement_import import (
    BankStatementImport,
    BankStatementImportLine,
)
from app.models.user import User
from app.services.treasury.bank_statement_import_service import (
    BankStatementImportService,
)
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from tests.integration.treasury.test_treasury_accounting_service import _context

POSTGRES_TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_DATABASE_URL,
    reason="PostgreSQL integration database is not configured",
)

HEADER = "external_id,transaction_date,value_date,amount,description,reference\n"


def _csv(*rows: str) -> bytes:
    return (HEADER + "\n".join(rows) + "\n").encode("utf-8")


@pytest.fixture
async def postgres_session():
    engine = create_async_engine(POSTGRES_TEST_DATABASE_URL, echo=False)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


async def _create_actor(session: AsyncSession) -> User:
    actor = User(
        email=f"bank-import-{uuid4().hex[:12]}@test.local",
        full_name="Bank import test actor",
        hashed_password="not-used-in-integration-test",
        is_active=True,
        is_superuser=False,
    )
    session.add(actor)
    await session.commit()
    return actor


@pytest.mark.asyncio
async def test_postgresql_bank_statement_import_lines_are_tenant_scoped(
    postgres_session: AsyncSession,
) -> None:
    organization, _, bank_profile, _, _, _ = await _context(postgres_session)
    organization_id = organization.id
    bank_profile_id = bank_profile.id
    actor = await _create_actor(postgres_session)
    statement_import = await BankStatementImportService(postgres_session).import_csv(
        organization_id,
        actor.id,
        bank_profile_id,
        "postgres-import-tenant-001",
        "tenant.csv",
        _csv("PG-TENANT-001,2026-02-10,,100.00,Collection,REF-001"),
    )
    transaction_id = statement_import.lines[0].bank_transaction_id
    other_organization, _, _, _, _, _ = await _context(postgres_session)
    with pytest.raises(IntegrityError):
        await postgres_session.execute(
            text(
                """
                INSERT INTO public.bank_statement_import_lines (
                    id, created_at, updated_at, organization_id, statement_import_id,
                    line_number, external_id, bank_transaction_id, row_hash, status
                ) VALUES (
                    :id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :organization_id,
                    :statement_import_id, 99, 'CROSS-TENANT', :bank_transaction_id,
                    :row_hash, 'IMPORTED'
                )
                """
            ),
            {
                "id": uuid4().hex,
                "organization_id": other_organization.id,
                "statement_import_id": statement_import.id,
                "bank_transaction_id": transaction_id,
                "row_hash": "0" * 64,
            },
        )
        await postgres_session.commit()
    await postgres_session.rollback()


@pytest.mark.asyncio
async def test_postgresql_concurrent_bank_statement_import_is_idempotent_and_audited_once(
    postgres_session: AsyncSession,
) -> None:
    organization, _, bank_profile, _, _, _ = await _context(postgres_session)
    organization_id = organization.id
    bank_profile_id = bank_profile.id
    actor = await _create_actor(postgres_session)
    actor_id = actor.id
    content = _csv(
        "PG-CONCURRENT-001,2026-02-11,,210.00,Collection,REF-001",
        "PG-CONCURRENT-002,2026-02-12,, -10.00 ,Bank fee,REF-002",
    )
    engine = create_async_engine(POSTGRES_TEST_DATABASE_URL, echo=False)

    async def import_once() -> str:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            statement_import = await BankStatementImportService(session).import_csv(
                organization_id,
                actor_id,
                bank_profile_id,
                "postgres-import-concurrent-001",
                "concurrent.csv",
                content,
            )
            return statement_import.id

    try:
        first_id, second_id = await asyncio.gather(import_once(), import_once())
    finally:
        await engine.dispose()

    assert first_id == second_id
    assert (
        await postgres_session.scalar(
            select(func.count(BankStatementImport.id)).where(
                BankStatementImport.organization_id == organization_id,
                BankStatementImport.idempotency_key == "postgres-import-concurrent-001",
            )
        )
        == 1
    )
    assert (
        await postgres_session.scalar(
            select(func.count(BankStatementImportLine.id)).where(
                BankStatementImportLine.organization_id == organization_id,
                BankStatementImportLine.statement_import_id == first_id,
            )
        )
        == 2
    )
    assert (
        await postgres_session.scalar(
            select(func.count(BankTransaction.id)).where(
                BankTransaction.organization_id == organization_id,
                BankTransaction.external_id.in_(
                    ["PG-CONCURRENT-001", "PG-CONCURRENT-002"]
                ),
            )
        )
        == 2
    )
    assert (
        await postgres_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.action == "BANK_STATEMENT_IMPORTED",
                AuditEvent.resource_id == first_id,
            )
        )
        == 1
    )
