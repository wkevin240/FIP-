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
