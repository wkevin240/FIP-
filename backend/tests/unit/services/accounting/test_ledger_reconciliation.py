from datetime import date
from decimal import Decimal

import pytest

from app.models.accounting.journal_entry import JournalEntry, JournalEntryLine, JournalEntryStatus
from app.models.accounting.ledger_posting import LedgerPosting
from app.services.accounting.ledger_service import LedgerService


@pytest.mark.asyncio
async def test_reconcile_postings_passes_when_posted_lines_match(db_session):
    entry = JournalEntry(
        id="e-reconcile-1",
        organization_id="org-r",
        fiscal_period_id="period-r",
        entry_date=date(2026, 1, 10),
        description="Posted entry",
        status=JournalEntryStatus.POSTED,
        idempotency_key="reconcile-1",
        idempotency_hash="hash-1",
    )
    line = JournalEntryLine(
        id="line-reconcile-1",
        journal_entry_id=entry.id,
        line_number=1,
        account_id="account-r",
        debit=Decimal("125.00"),
        credit=Decimal("0.00"),
    )
    posting = LedgerPosting(
        id="posting-reconcile-1",
        organization_id="org-r",
        fiscal_period_id="period-r",
        journal_entry_id=entry.id,
        journal_entry_line_id=line.id,
        account_id=line.account_id,
        posting_date=entry.entry_date,
        line_number=line.line_number,
        debit=line.debit,
        credit=line.credit,
    )
    db_session.add_all([entry, line, posting])
    await db_session.commit()

    result = await LedgerService(db_session).reconcile_postings("org-r")

    assert result["is_reconciled"] is True
    assert result["expected_journal_lines"] == 1
    assert result["actual_ledger_postings"] == 1
    assert result["missing_postings"] == []
    assert result["orphan_postings"] == []
    assert result["mismatched_postings"] == []


@pytest.mark.asyncio
async def test_reconcile_postings_reports_missing_posting(db_session):
    entry = JournalEntry(
        id="e-reconcile-2",
        organization_id="org-r2",
        fiscal_period_id="period-r2",
        entry_date=date(2026, 2, 10),
        description="Posted entry without ledger posting",
        status=JournalEntryStatus.POSTED,
        idempotency_key="reconcile-2",
        idempotency_hash="hash-2",
    )
    line = JournalEntryLine(
        id="line-reconcile-2",
        journal_entry_id=entry.id,
        line_number=1,
        account_id="account-r2",
        debit=Decimal("90.00"),
        credit=Decimal("0.00"),
    )
    db_session.add_all([entry, line])
    await db_session.commit()

    result = await LedgerService(db_session).reconcile_postings("org-r2")

    assert result["is_reconciled"] is False
    assert result["expected_journal_lines"] == 1
    assert result["actual_ledger_postings"] == 0
    assert result["missing_postings"] == [line.id]
