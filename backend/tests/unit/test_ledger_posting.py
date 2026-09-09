from datetime import date
from decimal import Decimal

import pytest

from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.journal_entry import JournalEntry, JournalEntryLine, JournalEntryStatus
from app.models.accounting.ledger_posting import LedgerPosting
from app.core.enums.accounting import FiscalPeriodStatus
from app.services.accounting.ledger_service import LedgerService


@pytest.mark.asyncio
async def test_ledger_is_created_from_posted_entry(db_session):
    organization_id = "org-ledger"
    period = FiscalPeriod(
        id="period-ledger",
        organization_id=organization_id,
        fiscal_year_id="year-ledger",
        name="March 2026",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        status=FiscalPeriodStatus.OPEN,
    )
    cash = Account(id="account-cash", organization_id=organization_id, code="521", name="Cash", account_type="ASSET", is_active=True)
    revenue = Account(id="account-revenue", organization_id=organization_id, code="701", name="Revenue", account_type="REVENUE", is_active=True)
    entry = JournalEntry(
        id="entry-ledger",
        organization_id=organization_id,
        fiscal_period_id=period.id,
        entry_date=date(2026, 3, 10),
        description="Cash sale",
        idempotency_key="ledger-test",
        idempotency_hash="a" * 64,
        status=JournalEntryStatus.POSTED,
        lines=[
            JournalEntryLine(id="line-cash", line_number=1, account_id=cash.id, debit=Decimal("100.00"), credit=Decimal("0.00")),
            JournalEntryLine(id="line-revenue", line_number=2, account_id=revenue.id, debit=Decimal("0.00"), credit=Decimal("100.00")),
        ],
    )
    db_session.add_all([period, cash, revenue, entry])
    await db_session.commit()

    db_session.add_all([
        LedgerPosting(
            organization_id=organization_id,
            fiscal_period_id=period.id,
            journal_entry_id=entry.id,
            journal_entry_line_id="line-cash",
            account_id=cash.id,
            posting_date=entry.entry_date,
            line_number=1,
            description="Cash sale",
            debit=Decimal("100.00"),
            credit=Decimal("0.00"),
        ),
        LedgerPosting(
            organization_id=organization_id,
            fiscal_period_id=period.id,
            journal_entry_id=entry.id,
            journal_entry_line_id="line-revenue",
            account_id=revenue.id,
            posting_date=entry.entry_date,
            line_number=2,
            description="Cash sale",
            debit=Decimal("0.00"),
            credit=Decimal("100.00"),
        ),
    ])
    await db_session.commit()

    ledger = LedgerService(db_session)
    assert await ledger.account_balance(organization_id, cash.id) == Decimal("100.00")
    assert await ledger.account_balance(organization_id, revenue.id) == Decimal("-100.00")
    rows = await ledger.trial_balance(organization_id)
    assert sum(row["debit"] for row in rows) == Decimal("100.00")
    assert sum(row["credit"] for row in rows) == Decimal("100.00")
