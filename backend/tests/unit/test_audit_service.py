from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

import pytest

from app.audit.audit_context import AuditContext
from app.audit.audit_service import AuditService
from app.audit.event_bus import DomainEvent, EventBus


def context() -> AuditContext:
    return AuditContext(
        organization_id="org-1",
        actor_id="user-1",
        action="journal.post",
        request_id="req-1",
        occurred_at=datetime(2026, 9, 9, 18, 0, tzinfo=timezone.utc),
    )


def test_audit_record_is_deterministic_and_chainable() -> None:
    first = AuditService.record(
        context(),
        entity_type="journal_entry",
        entity_id="entry-1",
        payload={"amount": Decimal("1250.00"), "accounts": ["401", "512"]},
    )
    second = AuditService.record(
        AuditContext(
            organization_id="org-1",
            actor_id="user-1",
            action="journal.post",
            request_id="req-2",
            occurred_at=datetime(2026, 9, 9, 18, 1, tzinfo=timezone.utc),
        ),
        entity_type="journal_entry",
        entity_id="entry-2",
        payload={"amount": Decimal("300.00")},
        previous_hash=first.record_hash,
    )

    assert AuditService.verify_chain([first, second]) is True


def test_audit_payload_canonicalization_supports_dates_and_enums() -> None:
    class Status(Enum):
        CLOSED = "CLOSED"

    payload = {
        "period": date(2026, 1, 31),
        "status": Status.CLOSED,
        "amount": Decimal("10.50"),
    }

    canonical = AuditService.canonical_payload_json(payload)

    assert canonical == '{"amount":"10.50","period":"2026-01-31","status":"CLOSED"}'

    record = AuditService.record(
        context(),
        entity_type="fiscal_period",
        entity_id="period-1",
        payload=payload,
    )
    assert AuditService.verify_chain([record]) is True


def test_audit_chain_rejects_cross_tenant_records() -> None:
    first = AuditService.record(
        context(),
        entity_type="journal_entry",
        entity_id="entry-1",
        payload={"amount": Decimal("1250.00")},
    )
    second = AuditService.record(
        AuditContext(
            organization_id="org-2",
            actor_id="user-2",
            action="journal.post",
            request_id="req-2",
            occurred_at=datetime(2026, 9, 9, 18, 1, tzinfo=timezone.utc),
        ),
        entity_type="journal_entry",
        entity_id="entry-2",
        payload={"amount": Decimal("300.00")},
        previous_hash=first.record_hash,
    )

    assert AuditService.verify_chain([first, second]) is False


def test_audit_chain_detects_tampering() -> None:
    record = AuditService.record(
        context(), entity_type="account", entity_id="401", payload={"name": "Suppliers"}
    )
    tampered = record.__class__(
        organization_id=record.organization_id,
        actor_id=record.actor_id,
        action=record.action,
        entity_type=record.entity_type,
        entity_id=record.entity_id,
        payload={"name": "Changed"},
        occurred_at=record.occurred_at,
        previous_hash=record.previous_hash,
        record_hash=record.record_hash,
        request_id=record.request_id,
    )

    assert AuditService.verify_chain([tampered]) is False


def test_event_bus_dispatches_subscribers() -> None:
    bus = EventBus()
    received: list[str] = []
    bus.subscribe("journal.posted", lambda event: received.append(event.entity_id))

    bus.publish(
        DomainEvent(
            name="journal.posted",
            organization_id="org-1",
            entity_id="entry-1",
            payload={},
        )
    )

    assert received == ["entry-1"]
