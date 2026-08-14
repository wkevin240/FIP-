from datetime import date
from decimal import Decimal

import pytest
from app.core.enums.accounting import (
    FiscalPeriodStatus,
    FiscalYearStatus,
    JournalEntryStatus,
)
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.organization import Organization
from app.schemas.accounting.journal import JournalCreate
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.accounting.journal_service import JournalService
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_context(
    session: AsyncSession, period_status: FiscalPeriodStatus = FiscalPeriodStatus.OPEN
) -> tuple[Organization, FiscalPeriod, Account, Account]:
    organization = Organization(name="Test organization")
    session.add(organization)
    await session.flush()

    fiscal_year = FiscalYear(
        organization_id=organization.id,
        name="FY 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status=FiscalYearStatus.OPEN,
    )
    session.add(fiscal_year)
    await session.flush()

    period = FiscalPeriod(
        organization_id=organization.id,
        fiscal_year_id=fiscal_year.id,
        name="January 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status=period_status,
    )
    debit_account = Account(
        organization_id=organization.id,
        code="571000",
        name="Cash",
        account_type="ASSET",
        level=1,
        path="/571000/",
    )
    credit_account = Account(
        organization_id=organization.id,
        code="701000",
        name="Sales revenue",
        account_type="REVENUE",
        level=1,
        path="/701000/",
    )
    session.add_all([period, debit_account, credit_account])
    await session.commit()
    return organization, period, debit_account, credit_account


@pytest.mark.asyncio
async def test_balanced_entry_can_be_created_and_posted(
    db_session: AsyncSession,
) -> None:
    organization, period, debit_account, credit_account = await _create_context(
        db_session
    )
    journal = await JournalService(db_session).create_journal(
        organization.id,
        JournalCreate(code="OD", name="General journal"),
    )

    entry = await JournalEntryService(db_session).create_entry(
        organization.id,
        JournalEntryCreate(
            journal_id=journal.id,
            fiscal_period_id=period.id,
            entry_number="OD-2026-0001",
            entry_date=date(2026, 1, 15),
            description="Cash sale",
            lines=[
                JournalEntryLineCreate(
                    account_id=debit_account.id, debit=Decimal("100.00")
                ),
                JournalEntryLineCreate(
                    account_id=credit_account.id, credit=Decimal("100.00")
                ),
            ],
        ),
    )

    assert entry.status == JournalEntryStatus.DRAFT
    assert [line.line_number for line in entry.lines] == [1, 2]

    posted_entry = await JournalEntryService(db_session).post_entry(
        organization.id, entry.id
    )

    assert posted_entry.status == JournalEntryStatus.POSTED
    assert posted_entry.posted_at is not None

    audit_events = await AuditService(db_session).list_events(
        organization.id, 0, 100, transaction_id=entry.id
    )
    assert [event.action for event in reversed(audit_events)] == [
        "JOURNAL_ENTRY_CREATED",
        "JOURNAL_ENTRY_POSTED",
    ]
    assert audit_events[0].previous_hash == audit_events[1].event_hash


@pytest.mark.asyncio
async def test_unbalanced_entry_is_rejected(db_session: AsyncSession) -> None:
    organization, period, debit_account, credit_account = await _create_context(
        db_session
    )
    journal = await JournalService(db_session).create_journal(
        organization.id,
        JournalCreate(code="OD", name="General journal"),
    )

    with pytest.raises(HTTPException, match="totals must balance") as exc_info:
        await JournalEntryService(db_session).create_entry(
            organization.id,
            JournalEntryCreate(
                journal_id=journal.id,
                fiscal_period_id=period.id,
                entry_number="OD-2026-0002",
                entry_date=date(2026, 1, 15),
                description="Invalid sale",
                lines=[
                    JournalEntryLineCreate(
                        account_id=debit_account.id, debit=Decimal("100.00")
                    ),
                    JournalEntryLineCreate(
                        account_id=credit_account.id, credit=Decimal("99.00")
                    ),
                ],
            ),
        )

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_closed_period_rejects_entry_creation(db_session: AsyncSession) -> None:
    organization, period, debit_account, credit_account = await _create_context(
        db_session, FiscalPeriodStatus.CLOSED
    )
    journal = await JournalService(db_session).create_journal(
        organization.id,
        JournalCreate(code="OD", name="General journal"),
    )

    with pytest.raises(HTTPException, match="Fiscal period is not open") as exc_info:
        await JournalEntryService(db_session).create_entry(
            organization.id,
            JournalEntryCreate(
                journal_id=journal.id,
                fiscal_period_id=period.id,
                entry_number="OD-2026-0003",
                entry_date=date(2026, 1, 15),
                description="Closed period sale",
                lines=[
                    JournalEntryLineCreate(
                        account_id=debit_account.id, debit=Decimal("100.00")
                    ),
                    JournalEntryLineCreate(
                        account_id=credit_account.id, credit=Decimal("100.00")
                    ),
                ],
            ),
        )

    assert exc_info.value.status_code == 422
