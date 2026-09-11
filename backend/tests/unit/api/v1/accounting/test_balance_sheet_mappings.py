from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.v1.accounting.balance_sheet_mappings import create_mapping
from app.schemas.accounting.balance_sheet_mapping import BalanceSheetMappingCreateRequest


@pytest.mark.asyncio
async def test_create_mapping_records_audit_event_after_persistence() -> None:
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
    audit_service = SimpleNamespace(record=AsyncMock())
    tenant = SimpleNamespace(organization_id="org-1", user_id="user-1")
    payload = BalanceSheetMappingCreateRequest(
        account_id="account-1",
        category="ASSET",
        rule_version="2026.1",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
    )

    result = await create_mapping(payload, tenant, repository, audit_service)

    assert result.id == "mapping-1"
    repository.create.assert_awaited_once_with(
        organization_id="org-1",
        account_id="account-1",
        category="ASSET",
        rule_version="2026.1",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
    )
    audit_service.record.assert_awaited_once_with(
        organization_id="org-1",
        actor_user_id="user-1",
        action="BALANCE_SHEET_MAPPING_CREATED",
        resource_type="BalanceSheetAccountMapping",
        resource_id="mapping-1",
        new_value={
            "account_id": "account-1",
            "category": "ASSET",
            "rule_version": "2026.1",
            "effective_from": "2026-01-01",
            "effective_to": "2026-12-31",
        },
    )


@pytest.mark.asyncio
async def test_create_mapping_does_not_audit_failed_persistence() -> None:
    repository = SimpleNamespace(create=AsyncMock(side_effect=LookupError("account not found")))
    audit_service = SimpleNamespace(record=AsyncMock())
    tenant = SimpleNamespace(organization_id="org-1", user_id="user-1")
    payload = BalanceSheetMappingCreateRequest(
        account_id="missing-account",
        category="ASSET",
        rule_version="2026.1",
        effective_from=date(2026, 1, 1),
    )

    with pytest.raises(HTTPException) as raised:
        await create_mapping(payload, tenant, repository, audit_service)

    assert raised.value.status_code == 404
    audit_service.record.assert_not_awaited()
