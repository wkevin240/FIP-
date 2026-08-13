from datetime import date
from decimal import Decimal

import pytest
from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.organization import Organization
from app.schemas.accounting.journal import JournalCreate
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.accounting.journal_service import JournalService
from app.services.accounting.reporting_service import ReportingService
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_reporting_context(
    session: AsyncSession,
) -> tuple[Organization, FiscalPeriod, dict[str, Account], str]:
    organization = Organization(name="Reporting test organization")
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
        status=FiscalPeriodStatus.OPEN,
    )
    accounts = {
        "cash": Account(
            organization_id=organization.id,
            code="571000",
            name="Cash",
            account_type="ASSET",
            level=1,
            path="/571000/",
        ),
        "equity": Account(
            organization_id=organization.id,
            code="101000",
            name="Share capital",
            account_type="EQUITY",
            level=1,
            path="/101000/",
        ),
        "revenue": Account(
            organization_id=organization.id,
            code="701000",
            name="Sales revenue",
            account_type="REVENUE",
            level=1,
            path="/701000/",
        ),
        "expense": Account(
            organization_id=organization.id,
            code="611000",
            name="Supplies expense",
            account_type="EXPENSE",
            level=1,
            path="/611000/",
        ),
    }
    session.add_all([period, *accounts.values()])
    await session.commit()

    journal = await JournalService(session).create_journal(
        organization.id,
        JournalCreate(code="OD", name="General journal"),
    )
    return organization, period, accounts, journal.id


async def _create_and_post_entry(
    session: AsyncSession,
    organization_id: str,
    period_id: str,
    journal_id: str,
    entry_number: str,
    entry_date: date,
    lines: list[JournalEntryLineCreate],
    post: bool = True,
) -> None:
    entry = await JournalEntryService(session).create_entry(
        organization_id,
        JournalEntryCreate(
            journal_id=journal_id,
            fiscal_period_id=period_id,
            entry_number=entry_number,
            entry_date=entry_date,
            description=entry_number,
            lines=lines,
        ),
    )
    if post:
        await JournalEntryService(session).post_entry(organization_id, entry.id)


@pytest.mark.asyncio
async def test_balance_sheet_and_income_statement_use_posted_entries_only(
    db_session: AsyncSession,
) -> None:
    organization, period, accounts, journal_id = await _create_reporting_context(
        db_session
    )
    await _create_and_post_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-2026-0001",
        date(2026, 1, 1),
        [
            JournalEntryLineCreate(
                account_id=accounts["cash"].id, debit=Decimal("1000.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["equity"].id, credit=Decimal("1000.00")
            ),
        ],
    )
    await _create_and_post_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-2026-0002",
        date(2026, 1, 15),
        [
            JournalEntryLineCreate(
                account_id=accounts["cash"].id, debit=Decimal("500.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("500.00")
            ),
        ],
    )
    await _create_and_post_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-2026-0003",
        date(2026, 1, 20),
        [
            JournalEntryLineCreate(
                account_id=accounts["expense"].id, debit=Decimal("200.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["cash"].id, credit=Decimal("200.00")
            ),
        ],
    )
    await _create_and_post_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-2026-0004",
        date(2026, 1, 25),
        [
            JournalEntryLineCreate(
                account_id=accounts["cash"].id, debit=Decimal("999.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("999.00")
            ),
        ],
        post=False,
    )

    service = ReportingService(db_session)
    balance_sheet = await service.balance_sheet(organization.id, date(2026, 1, 31))
    income_statement = await service.income_statement(
        organization.id, date(2026, 1, 1), date(2026, 1, 31)
    )

    assert balance_sheet.total_assets == Decimal("1300.00")
    assert balance_sheet.total_equity == Decimal("1000.00")
    assert balance_sheet.current_earnings == Decimal("300.00")
    assert balance_sheet.total_liabilities_and_equity == Decimal("1300.00")
    assert balance_sheet.is_balanced is True
    assert income_statement.total_revenue == Decimal("500.00")
    assert income_statement.total_expenses == Decimal("200.00")
    assert income_statement.net_income == Decimal("300.00")


@pytest.mark.asyncio
async def test_balance_sheet_respects_as_of_date(db_session: AsyncSession) -> None:
    organization, period, accounts, journal_id = await _create_reporting_context(
        db_session
    )
    await _create_and_post_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-2026-0101",
        date(2026, 1, 1),
        [
            JournalEntryLineCreate(
                account_id=accounts["cash"].id, debit=Decimal("1000.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["equity"].id, credit=Decimal("1000.00")
            ),
        ],
    )
    await _create_and_post_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-2026-0102",
        date(2026, 1, 15),
        [
            JournalEntryLineCreate(
                account_id=accounts["cash"].id, debit=Decimal("500.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("500.00")
            ),
        ],
    )

    balance_sheet = await ReportingService(db_session).balance_sheet(
        organization.id, date(2026, 1, 10)
    )

    assert balance_sheet.total_assets == Decimal("1000.00")
    assert balance_sheet.current_earnings == Decimal("0.00")
    assert balance_sheet.total_liabilities_and_equity == Decimal("1000.00")
