from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domain.calculation.contracts import CalculationContext
from app.services.accounting.balance_sheet_service import LedgerBalanceSheetService


@pytest.mark.asyncio
async def test_calculate_from_persisted_mappings_uses_period_end_snapshot() -> None:
    ledger_service = AsyncMock()
    mapping_repository = AsyncMock()
    service = LedgerBalanceSheetService(ledger_service, mapping_repository)
    service.calculate = AsyncMock(return_value={})

    context = CalculationContext(
        organization_id="org-1",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        rule_version="2026.1",
    )
    mapping = SimpleNamespace(
        account_id="account-1",
        category="ASSET",
    )
    mapping_repository.list_effective_at.return_value = [mapping]

    result = await service.calculate_from_persisted_mappings(context)

    assert result == {}
    mapping_repository.list_effective_at.assert_awaited_once_with(
        "org-1",
        "2026.1",
        date(2026, 12, 31),
    )
    service.calculate.assert_awaited_once()
    rules = service.calculate.await_args.args[1]
    assert [(rule.account_id, rule.category) for rule in rules] == [
        ("account-1", "ASSET")
    ]


@pytest.mark.asyncio
async def test_calculate_from_persisted_mappings_rejects_snapshot_ambiguity() -> None:
    ledger_service = AsyncMock()
    mapping_repository = AsyncMock()
    service = LedgerBalanceSheetService(ledger_service, mapping_repository)
    service.calculate = AsyncMock(return_value={})

    context = CalculationContext(
        organization_id="org-1",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        rule_version="2026.1",
    )
    mapping_repository.list_effective_at.return_value = [
        SimpleNamespace(account_id="account-1", category="ASSET"),
        SimpleNamespace(account_id="account-1", category="LIABILITY"),
    ]

    with pytest.raises(RuntimeError, match="ambiguous at snapshot date"):
        await service.calculate_from_persisted_mappings(context)

    service.calculate.assert_not_awaited()
