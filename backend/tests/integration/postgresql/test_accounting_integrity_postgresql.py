import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
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
from sqlalchemy import delete, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

POSTGRES_TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_DATABASE_URL,
    reason="PostgreSQL integration database is not configured",
)


@pytest.fixture
async def postgres_session():
    engine = create_async_engine(POSTGRES_TEST_DATABASE_URL, echo=False)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


async def _create_context(
    session: AsyncSession,
) -> tuple[Organization, FiscalPeriod, Account, Account]:
    suffix = uuid4().hex[:12]
    organization = Organization(name=f"Accounting integrity organization {suffix}")
    session.add(organization)
    await session.flush()

    fiscal_year = FiscalYear(
        organization_id=organization.id,
        name=f"FY integrity {suffix}",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status=FiscalYearStatus.OPEN,
    )
    session.add(fiscal_year)
    await session.flush()

    period = FiscalPeriod(
        organization_id=organization.id,
        fiscal_year_id=fiscal_year.id,
        name=f"January integrity {suffix}",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status=FiscalPeriodStatus.OPEN,
    )
    debit_account = Account(
        organization_id=organization.id,
        code=f"571{suffix[:6]}",
        name="Integrity debit account",
        account_type="ASSET",
        level=1,
        path=f"/571{suffix[:6]}/",
    )
    credit_account = Account(
        organization_id=organization.id,
        code=f"701{suffix[:6]}",
        name="Integrity credit account",
        account_type="REVENUE",
        level=1,
        path=f"/701{suffix[:6]}/",
    )
    session.add_all([period, debit_account, credit_account])
    await session.commit()
    return organization, period, debit_account, credit_account


async def _create_posted_entry(
    session: AsyncSession,
    organization: Organization,
    period: FiscalPeriod,
    debit_account: Account,
    credit_account: Account,
) -> JournalEntry:
    suffix = uuid4().hex[:8]
    journal = await JournalService(session).create_journal(
        organization.id,
        JournalCreate(code=f"OD{suffix[:6]}", name=f"Integrity journal {suffix}"),
    )
    service = JournalEntryService(session)
    entry = await service.create_entry(
        organization.id,
        JournalEntryCreate(
            journal_id=journal.id,
            fiscal_period_id=period.id,
            entry_number=f"OD-{suffix}",
            entry_date=date(2026, 1, 15),
            description="Posted entry protected by PostgreSQL",
            lines=[
                JournalEntryLineCreate(
                    account_id=debit_account.id,
                    debit=Decimal("100.00"),
                ),
                JournalEntryLineCreate(
                    account_id=credit_account.id,
                    credit=Decimal("100.00"),
                ),
            ],
        ),
        actor_user_id="postgres-integrity-tester",
    )
    return await service.post_entry(
        organization.id,
        entry.id,
        actor_user_id="postgres-integrity-tester",
    )


@pytest.mark.asyncio
async def test_postgresql_rejects_mutations_of_posted_entries_and_lines(
    postgres_session: AsyncSession,
) -> None:
    organization, period, debit_account, credit_account = await _create_context(
        postgres_session
    )
    entry = await _create_posted_entry(
        postgres_session, organization, period, debit_account, credit_account
    )
    organization_id = organization.id
    entry_id = entry.id
    line_id = entry.lines[0].id

    forbidden_operations = (
        update(JournalEntry)
        .where(JournalEntry.id == entry_id)
        .values(description="Direct mutation"),
        update(JournalEntry)
        .where(JournalEntry.id == entry_id)
        .values(status="DRAFT", posted_at=None),
        update(JournalEntryLine)
        .where(JournalEntryLine.id == line_id)
        .values(debit=Decimal("90.00")),
        delete(JournalEntryLine).where(JournalEntryLine.id == line_id),
        delete(JournalEntry).where(JournalEntry.id == entry_id),
    )

    for operation in forbidden_operations:
        with pytest.raises(DBAPIError, match="immutable|authorized accounting service"):
            await postgres_session.execute(operation)
            await postgres_session.commit()
        await postgres_session.rollback()

    refreshed = await JournalEntryService(postgres_session).get_entry(
        organization_id, entry_id
    )
    assert refreshed.description == "Posted entry protected by PostgreSQL"
    assert refreshed.status.value == "POSTED"
    assert len(refreshed.lines) == 2
    assert sum(line.debit for line in refreshed.lines) == Decimal("100.00")
    assert sum(line.credit for line in refreshed.lines) == Decimal("100.00")


@pytest.mark.asyncio
async def test_postgresql_rejects_cross_tenant_accounting_references(
    postgres_session: AsyncSession,
) -> None:
    organization_a, period_a, _, _ = await _create_context(postgres_session)
    organization_b, period_b, _, account_b_credit = await _create_context(
        postgres_session
    )
    organization_a_id = organization_a.id
    organization_b_id = organization_b.id
    period_a_id = period_a.id
    period_b_id = period_b.id
    account_b_credit_id = account_b_credit.id
    journal_b = await JournalService(postgres_session).create_journal(
        organization_b_id,
        JournalCreate(code=f"ODB{uuid4().hex[:6]}", name="Cross tenant journal"),
    )

    entry = JournalEntry(
        organization_id=organization_a_id,
        journal_id=journal_b.id,
        fiscal_period_id=period_b_id,
        entry_number=f"CROSS-{uuid4().hex[:8]}",
        entry_date=date(2026, 1, 15),
        description="Forbidden cross-tenant entry",
    )
    postgres_session.add(entry)
    with pytest.raises(DBAPIError):
        await postgres_session.commit()
    await postgres_session.rollback()

    valid_journal = await JournalService(postgres_session).create_journal(
        organization_a_id,
        JournalCreate(code=f"ODA{uuid4().hex[:6]}", name="Tenant A journal"),
    )
    valid_entry = JournalEntry(
        organization_id=organization_a_id,
        journal_id=valid_journal.id,
        fiscal_period_id=period_a_id,
        entry_number=f"LINE-{uuid4().hex[:8]}",
        entry_date=date(2026, 1, 15),
        description="Entry for line foreign key test",
    )
    postgres_session.add(valid_entry)
    await postgres_session.flush()
    cross_tenant_line = JournalEntryLine(
        organization_id=organization_a_id,
        journal_entry_id=valid_entry.id,
        account_id=account_b_credit_id,
        line_number=1,
        debit=Decimal("100.00"),
        credit=Decimal("0.00"),
    )
    postgres_session.add(cross_tenant_line)
    with pytest.raises(DBAPIError):
        await postgres_session.commit()
    await postgres_session.rollback()


@pytest.mark.asyncio
async def test_postgresql_enforces_fiscal_period_integrity(
    postgres_session: AsyncSession,
) -> None:
    organization, period, _, _ = await _create_context(postgres_session)
    organization_id = organization.id
    fiscal_year_id = period.fiscal_year_id
    fiscal_year = await postgres_session.get(FiscalYear, fiscal_year_id)
    assert fiscal_year is not None

    with pytest.raises(DBAPIError, match="locked before closing"):
        await postgres_session.execute(
            update(FiscalPeriod)
            .where(FiscalPeriod.id == period.id)
            .values(status=FiscalPeriodStatus.CLOSED)
        )
        await postgres_session.commit()
    await postgres_session.rollback()

    overlapping_period = FiscalPeriod(
        organization_id=organization_id,
        fiscal_year_id=fiscal_year_id,
        name=f"Overlapping {uuid4().hex[:8]}",
        start_date=date(2026, 1, 15),
        end_date=date(2026, 2, 15),
        status=FiscalPeriodStatus.OPEN,
    )
    postgres_session.add(overlapping_period)
    with pytest.raises(DBAPIError, match="overlap"):
        await postgres_session.commit()
    await postgres_session.rollback()

    fiscal_year = await postgres_session.get(FiscalYear, fiscal_year_id)
    assert fiscal_year is not None
    fiscal_year.status = FiscalYearStatus.CLOSED
    await postgres_session.commit()
    closed_year_period = FiscalPeriod(
        organization_id=organization_id,
        fiscal_year_id=fiscal_year_id,
        name=f"Closed year {uuid4().hex[:8]}",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
        status=FiscalPeriodStatus.OPEN,
    )
    postgres_session.add(closed_year_period)
    with pytest.raises(DBAPIError, match="open fiscal years"):
        await postgres_session.commit()
    await postgres_session.rollback()


@pytest.mark.asyncio
async def test_postgresql_allows_authorized_period_closing(
    postgres_session: AsyncSession,
) -> None:
    organization, period, debit_account, credit_account = await _create_context(
        postgres_session
    )
    user = User(
        email=f"postgres-closer-{uuid4().hex[:12]}@example.test",
        hashed_password="not-used-by-test",
        is_active=True,
    )
    postgres_session.add(user)
    await postgres_session.commit()

    await _create_posted_entry(
        postgres_session, organization, period, debit_account, credit_account
    )
    closing = await ClosingService(postgres_session).close_period(
        organization.id, period.id, user.id
    )

    assert closing.fiscal_period_id == period.id
    refreshed_period = await postgres_session.get(FiscalPeriod, period.id)
    assert refreshed_period is not None
    assert refreshed_period.status == FiscalPeriodStatus.CLOSED


@pytest.mark.asyncio
async def test_postgresql_allows_authorized_draft_to_posted_transition(
    postgres_session: AsyncSession,
) -> None:
    organization, period, debit_account, credit_account = await _create_context(
        postgres_session
    )
    entry = await _create_posted_entry(
        postgres_session, organization, period, debit_account, credit_account
    )

    assert entry.status.value == "POSTED"
    assert entry.posted_at is not None
    assert all(line.organization_id == organization.id for line in entry.lines)
