from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.core.enums.accounting import FiscalPeriodStatus
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.journal_entry import JournalEntry, JournalEntryStatus
from app.models.accounting.ledger_posting import LedgerPosting
from app.services.accounting.fiscal_period_service import FiscalPeriodService


@pytest.mark.asyncio
async def test_close_period_rejects_unposted_entries(db_session):
    year = FiscalYear(id="fy-1", organization_id="org-1", name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
    period = FiscalPeriod(id="p-1", organization_id="org-1", fiscal_year_id="fy-1", name="January", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))
    entry = JournalEntry(id="e-1", organization_id="org-1", fiscal_period_id="p-1", entry_date=date(2026, 1, 10), description="Unposted", idempotency_key="key-1", idempotency_hash="hash-1", status=JournalEntryStatus.DRAFT)
    db_session.add_all([year, period, entry])
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await FiscalPeriodService(db_session).close_period("org-1", "p-1")
    assert exc.value.status_code == 409
    assert period.status == FiscalPeriodStatus.OPEN


@pytest.mark.asyncio
async def test_close_period_requires_balanced_ledger(db_session):
    year = FiscalYear(id="fy-2", organization_id="org-2", name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
    period = FiscalPeriod(id="p-2", organization_id="org-2", fiscal_year_id="fy-2", name="January", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))
    posting = LedgerPosting(id="lp-1", organization_id="org-2", fiscal_period_id="p-2", journal_entry_id="e-2", journal_entry_line_id="l-1", account_id="a-1", posting_date=date(2026, 1, 10), line_number=1, debit=Decimal("100.00"), credit=Decimal("0.00"))
    db_session.add_all([year, period, posting])
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await FiscalPeriodService(db_session).close_period("org-2", "p-2")
    assert exc.value.status_code == 409
    assert period.status == FiscalPeriodStatus.OPEN


@pytest.mark.asyncio
async def test_close_period_transitions_only_after_controls_pass(db_session):
    year = FiscalYear(id="fy-3", organization_id="org-3", name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
    period = FiscalPeriod(id="p-3", organization_id="org-3", fiscal_year_id="fy-3", name="January", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))
    db_session.add_all([
        year,
        period,
        LedgerPosting(id="lp-3", organization_id="org-3", fiscal_period_id="p-3", journal_entry_id="e-3", journal_entry_line_id="l-3", account_id="a-3", posting_date=date(2026, 1, 10), line_number=1, debit=Decimal("250.00"), credit=Decimal("0.00")),
        LedgerPosting(id="lp-4", organization_id="org-3", fiscal_period_id="p-3", journal_entry_id="e-3", journal_entry_line_id="l-4", account_id="a-4", posting_date=date(2026, 1, 10), line_number=2, debit=Decimal("0.00"), credit=Decimal("250.00")),
    ])
    await db_session.commit()

    closed = await FiscalPeriodService(db_session).close_period("org-3", "p-3")
    assert closed.status == FiscalPeriodStatus.CLOSED
