from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models import Account, FiscalPeriod, Organization
from app.models.audit.audit_log import AuditLog
from app.models.accounting.journal_entry import JournalEntry, JournalEntryStatus
from app.models.accounting.ledger_posting import LedgerPosting
from app.core.enums.accounting import FiscalPeriodStatus
from app.schemas.accounting.journal_entry import JournalEntryCreate, JournalEntryLineCreate, JournalEntryReverse
from app.services.accounting.journal_entry_service import JournalEntryService


@pytest.mark.asyncio
async def test_create_and_post_journal_entry_persists_audit_events(db_session):
    organization_id = "org-1"
    db_session.add(Organization(id=organization_id, name="org-1"))
    period = FiscalPeriod(id="period-1", organization_id=organization_id, fiscal_year_id="year-1", name="January 2026", start_date=date(2026, 1, 1), end_date=date(2026, 1, 31), status=FiscalPeriodStatus.OPEN)
    debit_account = Account(id="account-1", organization_id=organization_id, code="601", name="Purchases", account_type="EXPENSE")
    credit_account = Account(id="account-2", organization_id=organization_id, code="401", name="Suppliers", account_type="LIABILITY")
    db_session.add_all([period, debit_account, credit_account])
    await db_session.commit()
    data = JournalEntryCreate(fiscal_period_id=period.id, entry_date=date(2026, 1, 15), description="Supplier invoice", idempotency_key="invoice-2026-0001", lines=[JournalEntryLineCreate(account_id=debit_account.id, debit=Decimal("100.00")), JournalEntryLineCreate(account_id=credit_account.id, credit=Decimal("100.00"))])
    service = JournalEntryService(db_session)
    entry = await service.create(organization_id, "creator-1", data)
    assert entry.status == JournalEntryStatus.DRAFT
    assert entry.created_by == "creator-1"
    assert len(entry.lines) == 2

    created_audit = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.organization_id == organization_id,
            AuditLog.entity_type == "journal_entry",
            AuditLog.entity_id == entry.id,
            AuditLog.action == "JOURNAL_ENTRY_CREATED",
        )
    )
    assert created_audit is not None
    assert created_audit.actor_id == "creator-1"
    assert created_audit.sequence_no == 1
    assert created_audit.previous_hash is None
    assert created_audit.record_hash

    posted = await service.post(organization_id, entry.id, "user-1")
    assert posted.status == JournalEntryStatus.POSTED
    assert posted.posted_by == "user-1"
    assert posted.posted_at is not None
    postings = list(await db_session.scalars(select(LedgerPosting).where(LedgerPosting.journal_entry_id == entry.id)))
    assert len(postings) == 2
    assert sum((Decimal(p.debit) for p in postings), Decimal("0")) == Decimal("100.00")
    assert sum((Decimal(p.credit) for p in postings), Decimal("0")) == Decimal("100.00")

    audit_rows = list(
        await db_session.scalars(
            select(AuditLog)
            .where(AuditLog.organization_id == organization_id)
            .order_by(AuditLog.sequence_no)
        )
    )
    assert [row.action for row in audit_rows] == ["JOURNAL_ENTRY_CREATED", "JOURNAL_ENTRY_POSTED"]
    assert audit_rows[1].previous_hash == audit_rows[0].record_hash


@pytest.mark.asyncio
async def test_journal_creator_cannot_post_same_entry(db_session):
    organization_id = "org-segregation-post"
    db_session.add(Organization(id=organization_id, name=organization_id))
    period = FiscalPeriod(id="period-segregation-post", organization_id=organization_id, fiscal_year_id="year-segregation-post", name="May 2026", start_date=date(2026, 5, 1), end_date=date(2026, 5, 31), status=FiscalPeriodStatus.OPEN)
    debit = Account(id="account-segregation-post-debit", organization_id=organization_id, code="605", name="Expense", account_type="EXPENSE")
    credit = Account(id="account-segregation-post-credit", organization_id=organization_id, code="405", name="Payable", account_type="LIABILITY")
    db_session.add_all([period, debit, credit])
    await db_session.commit()
    service = JournalEntryService(db_session)
    entry = await service.create(
        organization_id,
        "creator-1",
        JournalEntryCreate(
            fiscal_period_id=period.id,
            entry_date=date(2026, 5, 12),
            description="Segregation proof",
            idempotency_key="segregation-post-1",
            lines=[
                JournalEntryLineCreate(account_id=debit.id, debit=Decimal("80.00")),
                JournalEntryLineCreate(account_id=credit.id, credit=Decimal("80.00")),
            ],
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.post(organization_id, entry.id, "creator-1")
    assert exc_info.value.status_code == 403

    persisted = await db_session.scalar(select(JournalEntry).where(JournalEntry.id == entry.id))
    assert persisted.status == JournalEntryStatus.DRAFT
    assert persisted.posted_by is None
    assert await db_session.scalar(select(func.count(LedgerPosting.id)).where(LedgerPosting.journal_entry_id == entry.id)) == 0


@pytest.mark.asyncio
async def test_create_idempotency_retry_does_not_duplicate_audit(db_session):
    organization_id = "org-idempotent"
    db_session.add(Organization(id=organization_id, name="org-idempotent"))
    period = FiscalPeriod(id="period-idempotent", organization_id=organization_id, fiscal_year_id="year-idempotent", name="April 2026", start_date=date(2026, 4, 1), end_date=date(2026, 4, 30), status=FiscalPeriodStatus.OPEN)
    a1 = Account(id="account-idempotent-1", organization_id=organization_id, code="604", name="Expense", account_type="EXPENSE")
    a2 = Account(id="account-idempotent-2", organization_id=organization_id, code="404", name="Payable", account_type="LIABILITY")
    db_session.add_all([period, a1, a2])
    await db_session.commit()
    service = JournalEntryService(db_session)
    data = JournalEntryCreate(fiscal_period_id=period.id, entry_date=date(2026, 4, 10), description="Invoice", idempotency_key="same-create-key", lines=[JournalEntryLineCreate(account_id=a1.id, debit=Decimal("75.00")), JournalEntryLineCreate(account_id=a2.id, credit=Decimal("75.00"))])

    first = await service.create(organization_id, "creator-1", data)
    retry = await service.create(organization_id, "creator-2", data)

    assert retry.id == first.id
    assert retry.created_by == "creator-1"
    audit_count = await db_session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.organization_id == organization_id,
            AuditLog.entity_id == first.id,
            AuditLog.action == "JOURNAL_ENTRY_CREATED",
        )
    )
    assert audit_count == 1


@pytest.mark.asyncio
async def test_idempotency_rejects_changed_payload(db_session):
    organization_id = "org-2"
    period = FiscalPeriod(id="period-2", organization_id=organization_id, fiscal_year_id="year-2", name="February 2026", start_date=date(2026, 2, 1), end_date=date(2026, 2, 28), status=FiscalPeriodStatus.OPEN)
    a1 = Account(id="account-3", organization_id=organization_id, code="602", name="Purchases 2", account_type="EXPENSE")
    a2 = Account(id="account-4", organization_id=organization_id, code="402", name="Suppliers 2", account_type="LIABILITY")
    db_session.add_all([Organization(id=organization_id, name="org-2"), period, a1, a2])
    await db_session.commit()
    service = JournalEntryService(db_session)
    first = JournalEntryCreate(fiscal_period_id=period.id, entry_date=date(2026, 2, 10), description="Invoice A", idempotency_key="same-key", lines=[JournalEntryLineCreate(account_id=a1.id, debit=Decimal("50.00")), JournalEntryLineCreate(account_id=a2.id, credit=Decimal("50.00"))])
    await service.create(organization_id, "creator-1", first)
    changed = first.model_copy(update={"description": "Invoice B"})
    with pytest.raises(HTTPException) as exc_info:
        await service.create(organization_id, "creator-1", changed)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_posted_entry_can_be_reversed_once_and_audited(db_session):
    organization_id = "org-reversal"
    db_session.add(Organization(id=organization_id, name="org-reversal"))
    period = FiscalPeriod(id="period-reversal", organization_id=organization_id, fiscal_year_id="year-reversal", name="March 2026", start_date=date(2026, 3, 1), end_date=date(2026, 3, 31), status=FiscalPeriodStatus.OPEN)
    debit_account = Account(id="account-reversal-1", organization_id=organization_id, code="603", name="Expense", account_type="EXPENSE")
    credit_account = Account(id="account-reversal-2", organization_id=organization_id, code="403", name="Payable", account_type="LIABILITY")
    db_session.add_all([period, debit_account, credit_account])
    await db_session.commit()
    service = JournalEntryService(db_session)
    entry = await service.create(
        organization_id,
        "creator-1",
        JournalEntryCreate(
            fiscal_period_id=period.id,
            entry_date=date(2026, 3, 10),
            description="Original",
            idempotency_key="original-1",
            lines=[
                JournalEntryLineCreate(account_id=debit_account.id, debit=Decimal("125.00")),
                JournalEntryLineCreate(account_id=credit_account.id, credit=Decimal("125.00")),
            ],
        ),
    )
    await service.post(organization_id, entry.id, "user-1")

    with pytest.raises(HTTPException) as exc_info:
        await service.reverse(organization_id, entry.id, "creator-1", JournalEntryReverse(idempotency_key="reversal-self"))
    assert exc_info.value.status_code == 403

    reversal = await service.reverse(organization_id, entry.id, "user-2", JournalEntryReverse(idempotency_key="reversal-1", description="Correction"))
    assert reversal.status == JournalEntryStatus.POSTED
    assert reversal.reversal_of_id == entry.id
    assert reversal.created_by == "user-2"
    assert reversal.lines[0].debit == Decimal("0.00") or reversal.lines[0].credit == Decimal("125.00")
    original = await db_session.scalar(select(JournalEntry).where(JournalEntry.id == entry.id))
    assert original.status == JournalEntryStatus.REVERSED
    reversal_postings = list(await db_session.scalars(select(LedgerPosting).where(LedgerPosting.journal_entry_id == reversal.id)))
    assert len(reversal_postings) == 2
    audit_rows = list(
        await db_session.scalars(
            select(AuditLog)
            .where(AuditLog.organization_id == organization_id)
            .order_by(AuditLog.sequence_no)
        )
    )
    assert [row.action for row in audit_rows] == ["JOURNAL_ENTRY_CREATED", "JOURNAL_ENTRY_POSTED", "JOURNAL_ENTRY_REVERSED"]
    assert audit_rows[1].previous_hash == audit_rows[0].record_hash
    assert audit_rows[2].previous_hash == audit_rows[1].record_hash
    with pytest.raises(HTTPException) as exc_info:
        await service.reverse(organization_id, entry.id, "user-2", JournalEntryReverse(idempotency_key="reversal-2"))
    assert exc_info.value.status_code == 409
