from datetime import date

import pytest
from fastapi import HTTPException

from app.api.dependencies import CurrentTenant
from app.api.v1.accounting.profitability_mappings import (
    create_profitability_mapping,
    list_profitability_mappings,
)
from app.schemas.accounting.profitability import ProfitabilityMappingCreateRequest
from app.services.permission_service import PermissionService


class StubMapping:
    id = "mapping-1"
    organization_id = "org-authenticated"
    account_id = "account-1"
    category = "REVENUE"
    rule_version = "2026.1"
    effective_from = date(2026, 1, 1)
    effective_to = None


class StubMappingRepository:
    def __init__(self):
        self.created = None

    async def create(self, **kwargs):
        self.created = kwargs
        return StubMapping()

    async def list_for_period(self, organization_id, rule_version, period_start, period_end):
        self.list_args = (organization_id, rule_version, period_start, period_end)
        return [StubMapping()]


@pytest.mark.asyncio
async def test_create_mapping_uses_authenticated_tenant():
    tenant = CurrentTenant("user-1", "org-authenticated", "accountant", False)
    repository = StubMappingRepository()
    payload = ProfitabilityMappingCreateRequest(
        account_id="account-1",
        category="REVENUE",
        rule_version="2026.1",
        effective_from=date(2026, 1, 1),
    )

    response = await create_profitability_mapping(
        payload=payload,
        tenant=tenant,
        repository=repository,
    )

    assert repository.created["organization_id"] == "org-authenticated"
    assert response.organization_id == "org-authenticated"
    assert response.category == "REVENUE"


@pytest.mark.asyncio
async def test_list_mapping_is_tenant_scoped():
    tenant = CurrentTenant("user-1", "org-authenticated", "manager", False)
    repository = StubMappingRepository()

    response = await list_profitability_mappings(
        rule_version="2026.1",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        tenant=tenant,
        repository=repository,
    )

    assert repository.list_args == (
        "org-authenticated",
        "2026.1",
        date(2026, 1, 1),
        date(2026, 12, 31),
    )
    assert response[0].organization_id == "org-authenticated"


def test_accountant_can_manage_profitability_mappings_but_manager_is_read_only():
    assert PermissionService.role_allows("accountant", "profitability_mapping:create")
    assert PermissionService.role_allows("accountant", "profitability_mapping:read")
    assert PermissionService.role_allows("manager", "profitability_mapping:read")
    assert not PermissionService.role_allows("manager", "profitability_mapping:create")
