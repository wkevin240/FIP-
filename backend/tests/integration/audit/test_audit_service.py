import pytest
from app.models.audit.audit_event import AuditEvent
from app.models.organization import Organization
from app.services.audit.audit_service import AuditService
from sqlalchemy import select


@pytest.mark.asyncio
async def test_audit_events_are_chained_and_isolated_by_organization(
    db_session,
) -> None:
    first_organization = Organization(name="Audit organization one")
    second_organization = Organization(name="Audit organization two")
    db_session.add_all([first_organization, second_organization])
    await db_session.commit()

    audit = AuditService(db_session)
    first = await audit.record(
        first_organization.id,
        "user-one",
        "ACCOUNT_CREATED",
        "Account",
        "account-1",
        new_value={"code": "101"},
    )
    second = await audit.record(
        first_organization.id,
        "user-one",
        "ACCOUNT_UPDATED",
        "Account",
        "account-1",
        previous_value={"name": "Cash"},
        new_value={"name": "Main cash"},
    )
    await audit.record(
        second_organization.id,
        "user-two",
        "ACCOUNT_CREATED",
        "Account",
        "account-2",
        new_value={"code": "102"},
    )
    await db_session.commit()

    assert first.sequence_number == 1
    assert second.sequence_number == 2
    assert second.previous_hash == first.event_hash
    assert len(await audit.list_events(first_organization.id, 0, 100)) == 2
    assert len(await audit.list_events(second_organization.id, 0, 100)) == 1
    assert (await audit.verify_integrity(first_organization.id)).is_valid is True


@pytest.mark.asyncio
async def test_audit_event_is_rolled_back_with_enclosing_transaction(
    db_session,
) -> None:
    organization = Organization(name="Audit rollback organization")
    db_session.add(organization)
    await db_session.commit()
    organization_id = organization.id

    audit = AuditService(db_session)
    await audit.record(
        organization_id,
        "user-one",
        "JOURNAL_ENTRY_CREATED",
        "JournalEntry",
        "entry-rollback",
    )
    await db_session.rollback()

    events = list(
        await db_session.scalars(
            select(AuditEvent).where(AuditEvent.organization_id == organization_id)
        )
    )
    assert events == []
