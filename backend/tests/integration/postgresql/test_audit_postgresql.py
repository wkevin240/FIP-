import os
from uuid import uuid4

import pytest
from app.models.audit.audit_event import AuditEvent
from app.models.organization import Organization
from app.services.audit.audit_service import AuditService
from sqlalchemy import delete, inspect, update
from sqlalchemy.exc import DBAPIError
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
async def test_audit_migration_enforces_append_only_events(
    postgres_session: AsyncSession,
) -> None:
    table_names = await postgres_session.run_sync(
        lambda sync_session: inspect(sync_session.bind).get_table_names()
    )
    assert {"audit_sequences", "audit_events"}.issubset(table_names)

    organization = Organization(
        name=f"PostgreSQL audit organization {uuid4().hex[:12]}"
    )
    postgres_session.add(organization)
    await postgres_session.commit()

    organization_id = organization.id
    audit = AuditService(postgres_session)
    event = await audit.record(
        organization_id,
        "postgres-auditor",
        "JOURNAL_ENTRY_CREATED",
        "JournalEntry",
        "postgres-entry",
        new_value={"status": "DRAFT"},
    )
    await postgres_session.commit()
    event_id = event.id

    with pytest.raises(DBAPIError, match="append-only"):
        await postgres_session.execute(
            update(AuditEvent)
            .where(AuditEvent.id == event_id)
            .values(action="JOURNAL_ENTRY_TAMPERED")
        )
        await postgres_session.commit()
    await postgres_session.rollback()

    with pytest.raises(DBAPIError, match="append-only"):
        await postgres_session.execute(
            delete(AuditEvent).where(AuditEvent.id == event_id)
        )
        await postgres_session.commit()
    await postgres_session.rollback()

    assert (await audit.verify_integrity(organization_id)).is_valid is True
