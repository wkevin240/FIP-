from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import Account, FiscalPeriod
from app.models.accounting.journal_entry import JournalEntryStatus
from app.core.enums.accounting import FiscalPeriodStatus
from app.schemas.accounting.journal_entry import JournalEntryCreate, JournalEntryLineCreate
from app.services.accounting.journal_entry_service import JournalEntryService


@pytest.mark.asyncio
async def test_create_and_post_journal_entry(db_session):
    organization_id = "org-1"
    period = FiscalPeriod(
        id="period-1",
        organization_id=organization_id,
        fiscal_year_id="year-1",
        name="January 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status=FiscalPeriodStatus.OPEN,
    )
    debit_account = Account(id="account-1", organization_id=organization_id, code="601", name="Purchases", account_type="EXPENSE")
    credit_account = Account(id="account-2", organization_id=organization_id, code="401", name="Suppliers", account_type="LIABILITY")
    db_session.add_all([period, debit_account, credit_account])
    await db_session.commit()

    data = JournalEntryCreate(
        fiscal_period_id=period.id,
        entry_date=date(2026, 1, 15),
        description="Supplier invoice",
        idempotency_key="invoice-2026-0001",
        lines=[
            JournalEntryLineCreate(account_id=debit_account.id, debit=Decimal("100.00")),
            JournalEntryLineCreate(account_id=credit_account.id, credit=Decimal("100.00")),
        ],
    )

    service = JournalEntryService(db_session)
    entry = await service.create(organization_id, data)
    assert entry.status == JournalEntryStatus.DRAFT
    assert len(entry.lines) == 2

    posted = await service.post(organization_id, entry.id, "user-1")
    assert posted.status == JournalEntryStatus.POSTED
    assert posted.posted_by == "user-1"
    assert posted.posted_at is not None


@pytest.mark.asyncio
async def test_idempotency_rejects_changed_payload(db_session):
    organization_id = "org-2"
    period = FiscalPeriod(
        id="period-2",
        organization_id=organization_id,
        fiscal_year_id="year-2",
        name="February 2026",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
        status=FiscalPeriodStatus.OPEN,
    )
    a1 = Account(id="account-3", organization_id=organization_id, code="602", name="Purchases 2", account_type="EXPENSE")
    a2 = Account(id="account-4", organization_id=organization_id, code="402", name="Suppliers 2", account_type="LIABILITY")
    db_session.add_all([period, a1, a2])
    await db_session.commit()

    service = JournalEntryService(db_session)
    first = JournalEntryCreate(
        fiscal_period_id=period.id,
        entry_date=date(2026, 2, 10),
        description="Invoice A",
        idempotency_key="same-key",
        lines=[
            JournalEntryLineCreate(account_id=a1.id, debit=Decimal("50.00")),
            JournalEntryLineCreate(account_id=a2.id, credit=Decimal("50.00")),
        ],
    )
    await service.create(organization_id, first)

    changed = first.model_copy(update={"description": "Invoice B"})
    with pytest.raises(HTTPException) as exc_info:
        await service.create(organization_id, changed)
    assert exc_info.value.status_code == 409
