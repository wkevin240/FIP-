from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.audit.audit_context import AuditContext
from app.audit.audit_service import AuditService
from app.repositories.audit.audit_log_repository import AuditLogRepository


def audit_context() -> AuditContext:
    return AuditContext(
        organization_id="org-1",
        actor_id="user-1",
        action="BALANCE_SHEET_MAPPING_CREATED",
        request_id="req-1",
        occurred_at=datetime(2026, 9, 11, 19, 0, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_append_serializes_with_current_chain_head() -> None:
    latest = SimpleNamespace(sequence_no=4, record_hash="a" * 64)
    db = SimpleNamespace(
        scalar=AsyncMock(side_effect=["org-1", latest]),
        add=Mock(),
        flush=AsyncMock(),
    )
    repository = AuditLogRepository(db)

    record = await repository.append(
        audit_context(),
        entity_type="BalanceSheetAccountMapping",
        entity_id="mapping-1",
        payload={"category": "ASSET", "effective_from": "2026-01-01"},
    )

    assert record.previous_hash == "a" * 64
    assert AuditService.verify_chain([record]) is False
    persisted = db.add.call_args.args[0]
    assert persisted.organization_id == "org-1"
    assert persisted.sequence_no == 5
    assert persisted.previous_hash == "a" * 64
    assert persisted.record_hash == record.record_hash
    assert persisted.payload_json == '{"category":"ASSET","effective_from":"2026-01-01"}'
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_first_append_starts_a_tenant_chain_at_sequence_one() -> None:
    db = SimpleNamespace(
        scalar=AsyncMock(side_effect=["org-1", None]),
        add=Mock(),
        flush=AsyncMock(),
    )
    repository = AuditLogRepository(db)

    record = await repository.append(
        audit_context(),
        entity_type="BalanceSheetAccountMapping",
        entity_id="mapping-1",
        payload={"category": "ASSET"},
    )

    persisted = db.add.call_args.args[0]
    assert record.previous_hash is None
    assert persisted.sequence_no == 1
    assert persisted.previous_hash is None
    assert persisted.record_hash == record.record_hash
