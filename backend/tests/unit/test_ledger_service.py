from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

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
        LedgerPosting(id="lp-1", organization_id="org-1", fiscal_period_id="p-1", journal_entry_id="e-1", journal_entry_line_id="l-1", account_id="a-1", posting_date=date(2026, 1, 10), line_number=1, debit=Decimal("100.00"), credit=Decimal("0.00")),
        LedgerPosting(id="lp-2", organization_id="org-2", fiscal_period_id="p-2", journal_entry_id="e-2", journal_entry_line_id="l-2", account_id="a-2", posting_date=date(2026, 1, 10), line_number=1, debit=Decimal("900.00"), credit=Decimal("0.00")),
    ])
    await db_session.commit()

    assert await LedgerService(db_session).account_balance("org-1", "a-1") == Decimal("100.00")


@pytest.mark.asyncio
async def test_unknown_account_is_not_reported_as_zero(db_session):
    with pytest.raises(HTTPException) as exc_info:
        await LedgerService(db_session).account_balance("org-1", "missing")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_trial_balance_preserves_double_entry(db_session):
    debit = Account(id="a-3", organization_id="org-3", code="601", name="Purchases", account_type="EXPENSE")
    credit = Account(id="a-4", organization_id="org-3", code="401", name="Suppliers", account_type="LIABILITY")
    db_session.add_all([debit, credit])
    await db_session.flush()
    db_session.add_all([
        LedgerPosting(id="lp-3", organization_id="org-3", fiscal_period_id="p-3", journal_entry_id="e-3", journal_entry_line_id="l-3", account_id="a-3", posting_date=date(2026, 1, 10), line_number=1, debit=Decimal("250.00"), credit=Decimal("0.00")),
        LedgerPosting(id="lp-4", organization_id="org-3", fiscal_period_id="p-3", journal_entry_id="e-3", journal_entry_line_id="l-4", account_id="a-4", posting_date=date(2026, 1, 10), line_number=2, debit=Decimal("0.00"), credit=Decimal("250.00")),
    ])
    await db_session.commit()

    rows = await LedgerService(db_session).trial_balance("org-3")
    assert sum(row["debit"] for row in rows) == sum(row["credit"] for row in rows) == Decimal("250.00")


@pytest.mark.asyncio
async def test_profitability_facts_are_tenant_and_date_scoped(db_session):
    own = Account(id="a-7", organization_id="org-7", code="700", name="Sales", account_type="INCOME")
    other = Account(id="a-8", organization_id="org-8", code="700", name="Sales", account_type="INCOME")
    db_session.add_all([own, other])
    await db_session.flush()
    db_session.add_all([
        LedgerPosting(id="lp-7", organization_id="org-7", fiscal_period_id="p-7", journal_entry_id="e-7", journal_entry_line_id="l-7", account_id="a-7", posting_date=date(2026, 1, 10), line_number=1, debit=Decimal("0.00"), credit=Decimal("125.00")),
        LedgerPosting(id="lp-8", organization_id="org-7", fiscal_period_id="p-7", journal_entry_id="e-8", journal_entry_line_id="l-8", account_id="a-7", posting_date=date(2026, 2, 10), line_number=1, debit=Decimal("0.00"), credit=Decimal("50.00")),
        LedgerPosting(id="lp-9", organization_id="org-8", fiscal_period_id="p-8", journal_entry_id="e-9", journal_entry_line_id="l-9", account_id="a-8", posting_date=date(2026, 1, 10), line_number=1, debit=Decimal("0.00"), credit=Decimal("900.00")),
    ])
    await db_session.commit()

    facts = await LedgerService(db_session).profitability_facts(
        "org-7", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)
    )

    assert [(fact.posting_id, fact.account_id, fact.debit, fact.credit) for fact in facts] == [
        ("lp-7", "a-7", Decimal("0.00"), Decimal("125.00"))
    ]


@pytest.mark.asyncio
async def test_general_ledger_reports_opening_balance_for_partial_date_range(db_session):
    account = Account(id="a-5", organization_id="org-5", code="512", name="Bank", account_type="ASSET")
    db_session.add(account)
    await db_session.flush()
    db_session.add_all([
        LedgerPosting(id="lp-5", organization_id="org-5", fiscal_period_id="p-5", journal_entry_id="e-5", journal_entry_line_id="l-5", account_id="a-5", posting_date=date(2026, 1, 5), line_number=1, debit=Decimal("100.00"), credit=Decimal("0.00")),
        LedgerPosting(id="lp-6", organization_id="org-5", fiscal_period_id="p-5", journal_entry_id="e-6", journal_entry_line_id="l-6", account_id="a-5", posting_date=date(2026, 1, 10), line_number=1, debit=Decimal("25.00"), credit=Decimal("0.00")),
    ])
    await db_session.commit()

    report = await LedgerService(db_session).general_ledger(
        "org-5", "a-5", start_date=date(2026, 1, 10), end_date=date(2026, 1, 31)
    )

    assert report["opening_balance"] == Decimal("100.00")
    assert report["closing_balance"] == Decimal("125.00")
    assert len(report["movements"]) == 1
    assert report["movements"][0]["balance"] == Decimal("125.00")


@pytest.mark.asyncio
async def test_general_ledger_rejects_inverted_date_range(db_session):
    with pytest.raises(HTTPException) as exc_info:
        await LedgerService(db_session).general_ledger(
            "org-5", "missing", start_date=date(2026, 2, 1), end_date=date(2026, 1, 1)
        )

    assert exc_info.value.status_code == 422
