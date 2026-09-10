from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.repositories.accounting.profitability_mapping_repository import (
    ProfitabilityMappingConflictError,
    ProfitabilityMappingNotFoundError,
    ProfitabilityMappingRepository,
)


@pytest.mark.asyncio
async def test_create_rejects_unsupported_category() -> None:
    session = AsyncMock()
    repository = ProfitabilityMappingRepository(session)

    with pytest.raises(ValueError, match="unsupported profitability category"):
        await repository.create(
            organization_id="org-1",
            account_id="account-1",
            category="NOT_A_PNL_CATEGORY",
            rule_version="2026.1",
            effective_from=date(2026, 1, 1),
        )

    session.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_rejects_account_from_another_tenant() -> None:
    session = AsyncMock()
    session.scalar.return_value = None
    repository = ProfitabilityMappingRepository(session)

    with pytest.raises(LookupError, match="account not found for organization"):
        await repository.create(
            organization_id="org-1",
            account_id="account-2",
            category="REVENUE",
            rule_version="2026.1",
            effective_from=date(2026, 1, 1),
        )

    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_rejects_overlapping_range() -> None:
    session = AsyncMock()
    session.scalar.side_effect = ["account-1", "mapping-existing"]
    repository = ProfitabilityMappingRepository(session)

    with pytest.raises(ProfitabilityMappingConflictError, match="overlaps"):
        await repository.create(
            organization_id="org-1",
            account_id="account-1",
            category="REVENUE",
            rule_version="2026.1",
            effective_from=date(2026, 6, 1),
            effective_to=date(2026, 12, 31),
        )

    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_persists_non_overlapping_mapping() -> None:
    session = AsyncMock()
    session.scalar.side_effect = ["account-1", None]
    repository = ProfitabilityMappingRepository(session)

    mapping = await repository.create(
        organization_id="org-1",
        account_id="account-1",
        category="COGS",
        rule_version="2026.1",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 5, 31),
    )

    assert mapping.organization_id == "org-1"
    assert mapping.account_id == "account-1"
    assert mapping.category == "COGS"
    assert mapping.rule_version == "2026.1"
    assert mapping.effective_from == date(2026, 1, 1)
    assert mapping.effective_to == date(2026, 5, 31)
    session.add.assert_called_once_with(mapping)
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_excludes_current_mapping_from_overlap_check() -> None:
    session = AsyncMock()
    existing = SimpleNamespace(
        id="mapping-1",
        organization_id="org-1",
        account_id="account-1",
        category="REVENUE",
        rule_version="2026.1",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 3, 31),
    )
    session.scalar.side_effect = [existing, "account-1", None]
    repository = ProfitabilityMappingRepository(session)

    updated = await repository.update(
        "mapping-1",
        organization_id="org-1",
        account_id="account-1",
        category="COGS",
        rule_version="2026.2",
        effective_from=date(2026, 4, 1),
    )

    assert updated is existing
    assert updated.category == "COGS"
    assert updated.rule_version == "2026.2"
    assert updated.effective_from == date(2026, 4, 1)
    assert updated.effective_to is None
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_is_tenant_scoped() -> None:
    session = AsyncMock()
    session.scalar.return_value = None
    repository = ProfitabilityMappingRepository(session)

    with pytest.raises(ProfitabilityMappingNotFoundError, match="mapping not found"):
        await repository.update(
            "mapping-1",
            organization_id="org-other",
            account_id="account-1",
            category="REVENUE",
            rule_version="2026.1",
            effective_from=date(2026, 1, 1),
        )

    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_for_period_rejects_inverted_range_without_database_access() -> None:
    session = AsyncMock()
    repository = ProfitabilityMappingRepository(session)

    with pytest.raises(ValueError, match="period_start"):
        await repository.list_for_period(
            "org-1",
            "2026.1",
            date(2026, 12, 31),
            date(2026, 1, 1),
        )

    session.scalars.assert_not_awaited()
