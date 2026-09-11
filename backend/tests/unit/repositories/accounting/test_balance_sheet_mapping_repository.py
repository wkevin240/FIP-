from datetime import date
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.repositories.accounting.balance_sheet_mapping_repository import (
    BALANCE_SHEET_OVERLAP_CONSTRAINT,
    BalanceSheetMappingConflictError,
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


def test_overlap_integrity_error_is_identified_by_postgresql_constraint_name() -> None:
    class Diagnostic:
        constraint_name = BALANCE_SHEET_OVERLAP_CONSTRAINT

    class Original:
        diag = Diagnostic()

    error = IntegrityError("insert", {}, Original())

    assert BalanceSheetMappingRepository._is_overlap_integrity_error(error) is True


def test_other_integrity_errors_are_not_misclassified_as_mapping_conflicts() -> None:
    error = IntegrityError("insert", {}, RuntimeError("different constraint"))

    assert BalanceSheetMappingRepository._is_overlap_integrity_error(error) is False
    assert not isinstance(error, BalanceSheetMappingConflictError)


@pytest.mark.asyncio
async def test_create_translates_concurrent_overlap_and_rolls_back_transaction() -> None:
    session = AsyncMock()
    session.scalar.side_effect = ["account-1", None]

    class Diagnostic:
        constraint_name = BALANCE_SHEET_OVERLAP_CONSTRAINT

    class Original:
        diag = Diagnostic()

    session.flush.side_effect = IntegrityError("insert", {}, Original())
    repository = BalanceSheetMappingRepository(session)

    with pytest.raises(BalanceSheetMappingConflictError, match="effective range overlaps"):
        await repository.create(
            organization_id="org-1",
            account_id="account-1",
            category="ASSET",
            rule_version="2026.1",
            effective_from=date(2026, 1, 1),
        )

    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_preserves_unrelated_integrity_error_after_rollback() -> None:
    session = AsyncMock()
    session.scalar.side_effect = ["account-1", None]
    error = IntegrityError("insert", {}, RuntimeError("different constraint"))
    session.flush.side_effect = error
    repository = BalanceSheetMappingRepository(session)

    with pytest.raises(IntegrityError) as raised:
        await repository.create(
            organization_id="org-1",
            account_id="account-1",
            category="ASSET",
            rule_version="2026.1",
            effective_from=date(2026, 1, 1),
        )

    assert raised.value is error
    session.rollback.assert_awaited_once()
