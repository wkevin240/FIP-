from datetime import date

import pytest
from fastapi import HTTPException

from app.services.accounting.ledger_service import LedgerService


def test_posting_filters_are_tenant_scoped_and_period_aware() -> None:
    filters = LedgerService._posting_filters(
        "org-1",
        fiscal_period_id="period-1",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
    )

    assert len(filters) == 4
    rendered = {str(condition) for condition in filters}
    assert any("ledger_postings.organization_id" in condition for condition in rendered)
    assert any("ledger_postings.fiscal_period_id" in condition for condition in rendered)
    assert any("ledger_postings.posting_date" in condition for condition in rendered)


def test_posting_filters_allow_open_ended_date_range() -> None:
    filters = LedgerService._posting_filters(
        "org-1",
        start_date=date(2026, 1, 1),
    )

    assert len(filters) == 2


def test_invalid_date_range_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc_info:
        LedgerService._validate_dates(date(2026, 4, 1), date(2026, 3, 31))

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "start_date must be on or before end_date"
