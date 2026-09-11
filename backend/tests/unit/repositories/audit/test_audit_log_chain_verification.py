from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.repositories.audit.audit_log_repository import AuditLogRepository


def row(sequence_no: int, organization_id: str = "org-1", previous_hash: str | None = None, record_hash: str = "hash"):
    return SimpleNamespace(
        organization_id=organization_id,
        sequence_no=sequence_no,
        actor_id="user-1",
        action="BALANCE_SHEET_MAPPING_CREATED",
        entity_type="BalanceSheetAccountMapping",
        entity_id=f"mapping-{sequence_no}",
        payload_json='{"category":"ASSET"}',
        occurred_at=datetime(2026, 9, 11, 19, sequence_no, tzinfo=timezone.utc),
        previous_hash=previous_hash,
        record_hash=record_hash,
        request_id=None,
    )


def repository_for(rows):
    db = SimpleNamespace(
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: rows)),
    )
    return AuditLogRepository(db)


@pytest.mark.asyncio
async def test_verify_empty_persisted_chain_is_valid() -> None:
    assert await repository_for([]).verify_organization_chain("org-1") is True


@pytest.mark.asyncio
async def test_verify_rejects_sequence_gap_before_hash_validation() -> None:
    rows = [row(1, record_hash="first"), row(3, previous_hash="first", record_hash="third")]
    assert await repository_for(rows).verify_organization_chain("org-1") is False


@pytest.mark.asyncio
async def test_verify_rejects_cross_tenant_rows_even_when_sequence_is_contiguous() -> None:
    rows = [row(1, organization_id="org-1", record_hash="first"), row(2, organization_id="org-2", previous_hash="first", record_hash="second")]
    assert await repository_for(rows).verify_organization_chain("org-1") is False
