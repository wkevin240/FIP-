from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.models import Organization
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.journal_entry import JournalEntry, JournalEntryLine, JournalEntryStatus
from app.models.accounting.ledger_posting import LedgerPosting
from app.schemas.accounting.fiscal_period import FiscalPeriodCreate, FiscalPeriodReopen
from app.services.accounting.fiscal_period_service import FiscalPeriodService


@pytest.mark.asyncio
async def test_create_period_rejects_overlapping_dates(db_session):
    year = FiscalYear(id="fy-overlap", organization_id="org-overlap", name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
    existing = FiscalPeriod(
        id="p-overlap-existing",
        organization_id="org-overlap",
        fiscal_year_id="fy-overlap",
        name="January",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )
    db_session.add_all([year, existing])
    await db_session.commit()

    data = FiscalPeriodCreate(
        fiscal_year_id="fy-overlap",
        name="January duplicate range",
        start_date=date(2026, 1, 15),
        end_date=date(2026, 2, 15),
    )
    with pytest.raises(HTTPException) as exc:
        await FiscalPeriodService(db_session).create_fiscal_period("org-overlap", data)

    assert exc.value.status_code == 409
    assert "overlap" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_create_period_allows_adjacent_dates(db_session):
    year = FiscalYear(id="fy-adjacent", organization_id="org-adjacent", name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
    existing = FiscalPeriod(
        id="p-adjacent-existing",
        organization_id="org-adjacent",
        fiscal_year_id="fy-adjacent",
        name="January",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )
    db_session.add_all([year, existing])
    await db_session.commit()

    data = FiscalPeriodCreate(
        fiscal_year_id="fy-adjacent",
        name="February",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
    )
    created = await FiscalPeriodService(db_session).create_fiscal_period("org-adjacent", data)

    assert created.start_date == date(2026, 2, 1)
    assert created.end_date == date(2026, 2, 28)


@pytest.mark.asyncio
async def test_create_period_rejects_closed_fiscal_year(db_session):
    year = FiscalYear(
        id="fy-closed",
        organization_id="org-closed",
        name="2025",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        status=FiscalYearStatus.CLOSED,
    )
    db_session.add(year)
    await db_session.commit()

    data = FiscalPeriodCreate(
        fiscal_year_id="fy-closed",
        name="Late period",
        start_date=date(2025, 12, 1),
        end_date=date(2025, 12, 31),
    )
    with pytest.raises(HTTPException) as exc:
        await FiscalPeriodService(db_session).create_fiscal_period("org-closed", data)

    assert exc.value.status_code == 409
    assert "open fiscal year" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_close_period_rejects_unposted_entries(db_session):
    year = FiscalYear(id="fy-1", organization_id="org-1", name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
    period = FiscalPeriod(id="p-1", organization_id="org-1", fiscal_year_id="fy-1", name="January", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))
    entry = JournalEntry(id="e-1", organization_id="org-1", fiscal_period_id="p-1", entry_date=date(2026, 1, 10), description="Unposted", idempotency_key="key-1", idempotency_hash="hash-1", status=JournalEntryStatus.DRAFT)
    db_session.add_all([year, period, entry])
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await FiscalPeriodService(db_session).close_period("org-1", "p-1", "closer-1")
    assert exc.value.status_code == 409
    assert period.status == FiscalPeriodStatus.OPEN


@pytest.mark.asyncio
async def test_close_readiness_reports_unreconciled_balanced_ledger(db_session):
    year = FiscalYear(id="fy-readiness", organization_id="org-readiness", name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
    period = FiscalPeriod(id="p-readiness", organization_id="org-readiness", fiscal_year_id="fy-readiness", name="January", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))
    db_session.add_all([
        year,
        period,
        LedgerPosting(id="lp-readiness-1", organization_id="org-readiness", fiscal_period_id="p-readiness", journal_entry_id="missing-entry", journal_entry_line_id="missing-line-1", account_id="a-1", posting_date=date(2026, 1, 10), line_number=1, debit=Decimal("100.00"), credit=Decimal("0.00")),
        LedgerPosting(id="lp-readiness-2", organization_id="org-readiness", fiscal_period_id="p-readiness", journal_entry_id="missing-entry", journal_entry_line_id="missing-line-2", account_id="a-2", posting_date=date(2026, 1, 10), line_number=2, debit=Decimal("0.00"), credit=Decimal("100.00")),
    ])
    await db_session.commit()

    readiness = await FiscalPeriodService(db_session).close_readiness("org-readiness", "p-readiness")

    assert readiness["draft_journal_entries"] == 0
    assert readiness["ledger_reconciled"] is False
    assert readiness["ledger_balanced"] is True
    assert readiness["ready_to_close"] is False


@pytest.mark.asyncio
async def test_close_period_rejects_orphan_ledger_postings(db_session):
    year = FiscalYear(id="fy-orphan", organization_id="org-orphan", name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
    period = FiscalPeriod(id="p-orphan", organization_id="org-orphan", fiscal_year_id="fy-orphan", name="January", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))
    posting = LedgerPosting(
        id="lp-orphan",
        organization_id="org-orphan",
        fiscal_period_id="p-orphan",
        journal_entry_id="missing-entry",
        journal_entry_line_id="missing-line",
        account_id="missing-account",
        posting_date=date(2026, 1, 10),
        line_number=1,
        debit=Decimal("100.00"),
        credit=Decimal("0.00"),
    )
    db_session.add_all([year, period, posting])
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await FiscalPeriodService(db_session).close_period("org-orphan", "p-orphan", "closer-1")

    assert exc.value.status_code == 409
    assert "not reconciled" in exc.value.detail.lower()
    assert period.status == FiscalPeriodStatus.OPEN


@pytest.mark.asyncio
async def test_close_period_requires_balanced_ledger(db_session):
    year = FiscalYear(id="fy-2", organization_id="org-2", name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
    period = FiscalPeriod(id="p-2", organization_id="org-2", fiscal_year_id="fy-2", name="January", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))
    posting = LedgerPosting(id="lp-1", organization_id="org-2", fiscal_period_id="p-2", journal_entry_id="e-2", journal_entry_line_id="l-1", account_id="a-1", posting_date=date(2026, 1, 10), line_number=1, debit=Decimal("100.00"), credit=Decimal("0.00"))
    db_session.add_all([year, period, posting])
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await FiscalPeriodService(db_session).close_period("org-2", "p-2", "closer-1")
    assert exc.value.status_code == 409
    assert period.status == FiscalPeriodStatus.OPEN


@pytest.mark.asyncio
async def test_close_period_transitions_only_after_controls_pass(db_session):
    organization_id = "org-3"
    db_session.add(Organization(id=organization_id, name=organization_id))
    year = FiscalYear(id="fy-3", organization_id=organization_id, name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))
    period = FiscalPeriod(id="p-3", organization_id=organization_id, fiscal_year_id="fy-3", name="January", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31))
    debit_account = Account(id="a-3", organization_id=organization_id, code="TEST-D", name="Debit account", account_type="TEST")
    credit_account = Account(id="a-4", organization_id=organization_id, code="TEST-C", name="Credit account", account_type="TEST")
    entry = JournalEntry(
        id="e-3",
        organization_id=organization_id,
        fiscal_period_id="p-3",
        entry_date=date(2026, 1, 10),
        description="Posted entry",
        idempotency_key="key-3",
        idempotency_hash="hash-3",
        status=JournalEntryStatus.POSTED,
    )
    debit_line = JournalEntryLine(id="l-3", journal_entry_id="e-3", line_number=1, account_id="a-3", debit=Decimal("250.00"), credit=Decimal("0.00"))
    credit_line = JournalEntryLine(id="l-4", journal_entry_id="e-3", line_number=2, account_id="a-4", debit=Decimal("0.00"), credit=Decimal("250.00"))
    db_session.add_all([
        year,
        period,
        debit_account,
        credit_account,
        entry,
        debit_line,
        credit_line,
        LedgerPosting(id="lp-3", organization_id=organization_id, fiscal_period_id="p-3", journal_entry_id="e-3", journal_entry_line_id="l-3", account_id="a-3", posting_date=date(2026, 1, 10), line_number=1, debit=Decimal("250.00"), credit=Decimal("0.00")),
        LedgerPosting(id="lp-4", organization_id=organization_id, fiscal_period_id="p-3", journal_entry_id="e-3", journal_entry_line_id="l-4", account_id="a-4", posting_date=date(2026, 1, 10), line_number=2, debit=Decimal("0.00"), credit=Decimal("250.00")),
    ])
    await db_session.commit()

    readiness = await FiscalPeriodService(db_session).close_readiness(organization_id, "p-3")
    assert readiness["ledger_reconciled"] is True
    assert readiness["ledger_balanced"] is True
    assert readiness["ready_to_close"] is True

    closed = await FiscalPeriodService(db_session).close_period(organization_id, "p-3", "closer-1")
    assert closed.status == FiscalPeriodStatus.CLOSED


@pytest.mark.asyncio
async def test_reopen_period_requires_non_blank_reason(db_session):
    period = FiscalPeriod(
        id="p-reopen-blank",
        organization_id="org-reopen-blank",
        fiscal_year_id="fy-reopen-blank",
        name="January",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status=FiscalPeriodStatus.CLOSED,
    )
    db_session.add(period)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await FiscalPeriodService(db_session).reopen_period(
            "org-reopen-blank", "p-reopen-blank", "actor-1", FiscalPeriodReopen(reason="   ")
        )

    assert exc.value.status_code == 422
    assert period.status == FiscalPeriodStatus.CLOSED


@pytest.mark.asyncio
async def test_reopen_period_requires_closed_status(db_session):
    period = FiscalPeriod(
        id="p-reopen-open",
        organization_id="org-reopen-open",
        fiscal_year_id="fy-reopen-open",
        name="January",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status=FiscalPeriodStatus.OPEN,
    )
    db_session.add(period)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await FiscalPeriodService(db_session).reopen_period(
            "org-reopen-open", "p-reopen-open", "actor-1", FiscalPeriodReopen(reason="Correction approved")
        )

    assert exc.value.status_code == 409
    assert period.status == FiscalPeriodStatus.OPEN


@pytest.mark.asyncio
async def test_reopen_period_is_audited_and_committed(db_session):
    organization_id = "org-reopen"
    db_session.add(Organization(id=organization_id, name=organization_id))
    period = FiscalPeriod(
        id="p-reopen",
        organization_id=organization_id,
        fiscal_year_id="fy-reopen",
        name="January",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status=FiscalPeriodStatus.CLOSED,
    )
    db_session.add(period)
    await db_session.commit()

    service = FiscalPeriodService(db_session)
    service.audit_repository.append = AsyncMock()

    reopened = await service.reopen_period(
        organization_id, period.id, "actor-reopen", FiscalPeriodReopen(reason="Approved correction of source document")
    )

    assert reopened.status == FiscalPeriodStatus.OPEN
    service.audit_repository.append.assert_awaited_once()
    context = service.audit_repository.append.await_args.args[0]
    assert context.action == "FISCAL_PERIOD_REOPENED"
    payload = service.audit_repository.append.await_args.kwargs["payload"]
    assert payload["reason"] == "Approved correction of source document"
    assert payload["previous_status"] == FiscalPeriodStatus.CLOSED.value
    assert payload["resulting_status"] == FiscalPeriodStatus.OPEN.value
