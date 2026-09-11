from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.audit.audit_service import AuditService
from app.api.v1.accounting.balance_sheet_mappings import create_mapping
from app.schemas.accounting.balance_sheet_mapping import BalanceSheetMappingCreateRequest


@pytest.mark.asyncio
async def test_create_mapping_persists_audit_event_after_mapping_flush() -> None:
    mapping = SimpleNamespace(
        id="mapping-1",
        organization_id="org-1",
        account_id="account-1",
        category="ASSET",
        rule_version="2026.1",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
    )
    repository = SimpleNamespace(create=AsyncMock(return_value=mapping))
    audit_repository = SimpleNamespace(append=AsyncMock(return_value=SimpleNamespace(record_hash="hash-1")))
    tenant = SimpleNamespace(organization_id="org-1", user_id="user-1")
    payload = BalanceSheetMappingCreateRequest(
        account_id="account-1",
        category="ASSET",
        rule_version="2026.1",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
    )

    result = await create_mapping(payload, tenant, repository, audit_repository)

    assert result.id == "mapping-1"
    repository.create.assert_awaited_once_with(
        organization_id="org-1",
        account_id="account-1",
        category="ASSET",
        rule_version="2026.1",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
    )
    audit_repository.append.assert_awaited_once()
    context = audit_repository.append.call_args.args[0]
    assert context.organization_id == "org-1"
    assert context.actor_id == "user-1"
    assert context.action == "BALANCE_SHEET_MAPPING_CREATED"
    assert audit_repository.append.call_args.kwargs == {
        "entity_type": "BalanceSheetAccountMapping",
        "entity_id": "mapping-1",
        "payload": {
            "account_id": "account-1",
            "category": "ASSET",
            "rule_version": "2026.1",
            "effective_from": "2026-01-01",
            "effective_to": "2026-12-31",
        },
    }


@pytest.mark.asyncio
async def test_create_mapping_does_not_audit_failed_persistence() -> None:
    repository = SimpleNamespace(create=AsyncMock(side_effect=LookupError("account not found")))
    audit_repository = SimpleNamespace(append=AsyncMock())
    tenant = SimpleNamespace(organization_id="org-1", user_id="user-1")
    payload = BalanceSheetMappingCreateRequest(
        account_id="missing-account",
        category="ASSET",
        rule_version="2026.1",
        effective_from=date(2026, 1, 1),
    )

    with pytest.raises(HTTPException) as raised:
        await create_mapping(payload, tenant, repository, audit_repository)

    assert raised.value.status_code == 404
    audit_repository.append.assert_not_awaited()


def test_canonical_payload_preserves_hash_input() -> None:
    payload = {"amount": "1250.00", "accounts": ["401", "512"]}
    assert AuditService.canonical_payload_json(payload) == '{"accounts":["401","512"],"amount":"1250.00"}'
