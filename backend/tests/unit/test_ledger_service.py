from decimal import Decimal

import pytest

from app.models.accounting.account import Account
from app.models.accounting.ledger_posting import LedgerPosting
from app.services.accounting.ledger_service import LedgerService


@pytest.mark.asyncio
async def test_account_balance_is_scoped_to_organization(db_session):
    a1 = Account(id="a-1", organization_id="org-1", code="512", name="Bank", account_type="ASSET")
    a2 = Account(id="a-2", organization_id="org-2", code="512", name="Bank", account_type="ASSET")
    db_session.add_all([a1, a2])
    await db_session.flush()
    db_session.add_all([
        LedgerPosting(id="lp-1", organization_id="org-1", fiscal_period_id="p-1", journal_entry_id="e-1", journal_entry_line_id="l-1", account_id="a-1", posting_date="2026-01-10", line_number=1, debit=Decimal("100.00"), credit=Decimal("0.00")),
        LedgerPosting(id="lp-2", organization_id="org-2", fiscal_period_id="p-2", journal_entry_id="e-2", journal_entry_line_id="l-2", account_id="a-2", posting_date="2026-01-10", line_number=1, debit=Decimal("900.00"), credit=Decimal("0.00")),
    ])
    await db_session.commit()

    assert await LedgerService(db_session).account_balance("org-1", "a-1") == Decimal("100.00")


@pytest.mark.asyncio
async def test_trial_balance_preserves_double_entry(db_session):
    debit = Account(id="a-3", organization_id="org-3", code="601", name="Purchases", account_type="EXPENSE")
    credit = Account(id="a-4", organization_id="org-3", code="401", name="Suppliers", account_type="LIABILITY")
    db_session.add_all([debit, credit])
    await db_session.flush()
    db_session.add_all([
        LedgerPosting(id="lp-3", organization_id="org-3", fiscal_period_id="p-3", journal_entry_id="e-3", journal_entry_line_id="l-3", account_id="a-3", posting_date="2026-01-10", line_number=1, debit=Decimal("250.00"), credit=Decimal("0.00")),
        LedgerPosting(id="lp-4", organization_id="org-3", fiscal_period_id="p-3", journal_entry_id="e-3", journal_entry_line_id="l-4", account_id="a-4", posting_date="2026-01-10", line_number=2, debit=Decimal("0.00"), credit=Decimal("250.00")),
    ])
    await db_session.commit()

    rows = await LedgerService(db_session).trial_balance("org-3")
    assert sum(row["debit"] for row in rows) == sum(row["credit"] for row in rows) == Decimal("250.00")
