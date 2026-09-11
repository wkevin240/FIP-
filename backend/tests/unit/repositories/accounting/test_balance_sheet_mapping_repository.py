from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.repositories.accounting.balance_sheet_mapping_repository import (
    BalanceSheetMappingRepository,
)


@pytest.mark.asyncio
async def test_list_effective_at_rejects_blank_rule_version_without_database_access() -> None:
    session = AsyncMock()
    repository = BalanceSheetMappingRepository(session)

    with pytest.raises(ValueError, match="rule_version must not be blank"):
        await repository.list_effective_at("org-1", " ", date(2026, 12, 31))

    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_effective_at_returns_only_rows_active_on_snapshot_date() -> None:
    session = AsyncMock()
    active_mapping = object()
    session.scalars.return_value = [active_mapping]
    repository = BalanceSheetMappingRepository(session)

    result = await repository.list_effective_at(
        "org-1",
        "2026.1",
        date(2026, 12, 31),
    )

    assert result == [active_mapping]
    session.scalars.assert_awaited_once()
