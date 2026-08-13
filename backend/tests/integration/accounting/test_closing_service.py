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
from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.journal_entry_line import JournalEntryLine
from app.models.organization import Organization
from app.models.user import User
from app.schemas.accounting.journal import JournalCreate
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.services.accounting.closing_service import ClosingService
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.accounting.journal_service import JournalService
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_closing_context(
    session: AsyncSession,
) -> tuple[Organization, User, FiscalPeriod, Account, Account]:
    organization = Organization(name="Closing test organization")
    user = User(
        email="closer@example.test",
        hashed_password="not-used-by-test",
        is_active=True,
    )
    session.add_all([organization, user])
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
        status=FiscalPeriodStatus.OPEN,
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
    return organization, user, period, debit_account, credit_account


async def _create_entry(
    session: AsyncSession,
    organization: Organization,
    period: FiscalPeriod,
    debit_account: Account,
    credit_account: Account,
    entry_number: str,
) -> str:
    journal = await JournalService(session).create_journal(
        organization.id,
        JournalCreate(code="OD", name="General journal"),
    )
    entry = await JournalEntryService(session).create_entry(
        organization.id,
        JournalEntryCreate(
            journal_id=journal.id,
            fiscal_period_id=period.id,
            entry_number=entry_number,
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
    return entry.id


@pytest.mark.asyncio
async def test_preview_and_close_persist_balanced_control_totals(
    db_session: AsyncSession,
) -> None:
    (
        organization,
        user,
        period,
        debit_account,
        credit_account,
    ) = await _create_closing_context(db_session)
    entry_id = await _create_entry(
        db_session,
        organization,
        period,
        debit_account,
        credit_account,
        "OD-2026-0001",
    )
    await JournalEntryService(db_session).post_entry(organization.id, entry_id)

    service = ClosingService(db_session)
    preview = await service.preview_closing(organization.id, period.id)
    preview_again = await service.preview_closing(organization.id, period.id)
    closing = await service.close_period(organization.id, period.id, user.id)

    assert preview.control_hash == preview_again.control_hash
    assert preview.posted_entry_count == 1
    assert preview.posted_line_count == 2
    assert preview.total_debit == Decimal("100.00")
    assert preview.total_credit == Decimal("100.00")
    assert closing.control_hash == preview.control_hash
    assert closing.total_debit == closing.total_credit == Decimal("100.00")

    refreshed_period = await db_session.get(FiscalPeriod, period.id)
    assert refreshed_period.status == FiscalPeriodStatus.CLOSED

    with pytest.raises(HTTPException, match="Only open fiscal periods") as exc_info:
        await service.close_period(organization.id, period.id, user.id)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_draft_entries_block_period_closing(db_session: AsyncSession) -> None:
    (
        organization,
        user,
        period,
        debit_account,
        credit_account,
    ) = await _create_closing_context(db_session)
    await _create_entry(
        db_session,
        organization,
        period,
        debit_account,
        credit_account,
        "OD-2026-0002",
    )

    with pytest.raises(HTTPException, match="Draft journal entries") as exc_info:
        await ClosingService(db_session).close_period(
            organization.id, period.id, user.id
        )

    assert exc_info.value.status_code == 422
    await db_session.refresh(period, attribute_names=["status"])
    assert period.status == FiscalPeriodStatus.OPEN


@pytest.mark.asyncio
async def test_invalid_posted_entry_blocks_period_closing(
    db_session: AsyncSession,
) -> None:
    (
        organization,
        user,
        period,
        debit_account,
        credit_account,
    ) = await _create_closing_context(db_session)
    journal = await JournalService(db_session).create_journal(
        organization.id,
        JournalCreate(code="OD", name="General journal"),
    )
    invalid_entry = JournalEntry(
        organization_id=organization.id,
        journal_id=journal.id,
        fiscal_period_id=period.id,
        entry_number="OD-2026-0003",
        entry_date=date(2026, 1, 15),
        description="Corrupted entry",
        status=JournalEntryStatus.POSTED,
    )
    db_session.add(invalid_entry)
    await db_session.flush()
    db_session.add_all(
        [
            JournalEntryLine(
                journal_entry_id=invalid_entry.id,
                account_id=debit_account.id,
                line_number=1,
                debit=Decimal("100.00"),
                credit=Decimal("0.00"),
            ),
            JournalEntryLine(
                journal_entry_id=invalid_entry.id,
                account_id=credit_account.id,
                line_number=2,
                debit=Decimal("0.00"),
                credit=Decimal("90.00"),
            ),
        ]
    )
    await db_session.commit()

    with pytest.raises(HTTPException, match="is invalid") as exc_info:
        await ClosingService(db_session).close_period(
            organization.id, period.id, user.id
        )

    assert exc_info.value.status_code == 422
    await db_session.refresh(period, attribute_names=["status"])
    assert period.status == FiscalPeriodStatus.OPEN
