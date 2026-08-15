import asyncio
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
from app.models.accounting.vat_declaration import VATDeclaration
from app.models.audit.audit_event import AuditEvent
from app.models.organization import Organization
from app.models.user import User
from app.schemas.accounting.cash_flow import CashFlowAccountMappingCreate
from app.schemas.accounting.journal import JournalCreate
from app.schemas.accounting.journal_entry import (
    JournalEntryCreate,
    JournalEntryReversalCreate,
)
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.schemas.accounting.syscohada_liasse import LiasseReadinessStatus
from app.services.accounting.cash_flow_configuration_service import (
    CashFlowConfigurationService,
)
from app.services.accounting.cash_flow_service import CashFlowService
from app.services.accounting.closing_service import ClosingService
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.accounting.journal_service import JournalService
from app.services.accounting.syscohada_liasse_service import SyscohadaLiasseService
from fastapi import HTTPException
from sqlalchemy import delete, select, text, update
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


async def _create_draft_entry(
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
    return entry


async def _create_posted_entry(
    session: AsyncSession,
    organization: Organization,
    period: FiscalPeriod,
    debit_account: Account,
    credit_account: Account,
) -> JournalEntry:
    entry = await _create_draft_entry(
        session, organization, period, debit_account, credit_account
    )
    return await JournalEntryService(session).post_entry(
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
        with pytest.raises(
            DBAPIError,
            match="immutable|authorized accounting procedure|permission denied",
        ):
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
async def test_postgresql_rejects_forged_posting_session_and_all_posted_mutations(
    postgres_session: AsyncSession,
) -> None:
    organization, period, debit_account, credit_account = await _create_context(
        postgres_session
    )
    draft_entry = await _create_draft_entry(
        postgres_session, organization, period, debit_account, credit_account
    )
    organization_id = organization.id
    period_id = period.id
    debit_account_id = debit_account.id
    draft_entry_id = draft_entry.id

    with pytest.raises(DBAPIError, match="permission denied"):
        await postgres_session.execute(
            update(JournalEntry)
            .where(JournalEntry.id == draft_entry_id)
            .values(status="POSTED")
        )
        await postgres_session.commit()
    await postgres_session.rollback()

    await postgres_session.execute(
        text("SELECT set_config('fip.posting_entry_id', :entry_id, true)"),
        {"entry_id": draft_entry_id},
    )
    with pytest.raises(DBAPIError, match="permission denied"):
        await postgres_session.execute(
            update(JournalEntry)
            .where(JournalEntry.id == draft_entry_id)
            .values(status="POSTED")
        )
        await postgres_session.commit()
    await postgres_session.rollback()

    await postgres_session.execute(
        text("SELECT set_config('fip.posting_entry_id', :entry_id, true)"),
        {"entry_id": draft_entry_id},
    )
    with pytest.raises(DBAPIError, match="authorization failed"):
        await postgres_session.execute(
            text("SELECT post_journal_entry(:entry_id)"),
            {"entry_id": draft_entry_id},
        )
    await postgres_session.rollback()

    await postgres_session.execute(
        text("SELECT set_config('fip.posting_token', 'forged-token', true)")
    )
    with pytest.raises(DBAPIError, match="authorization failed"):
        await postgres_session.execute(
            text("SELECT post_journal_entry(:entry_id)"),
            {"entry_id": draft_entry_id},
        )
    await postgres_session.rollback()

    posted_entry = await JournalEntryService(postgres_session).post_entry(
        organization_id,
        draft_entry_id,
        actor_user_id="postgres-integrity-tester",
    )
    posted_entry_id = posted_entry.id
    posted_line_id = posted_entry.lines[0].id

    forbidden_operations = (
        update(JournalEntry)
        .where(JournalEntry.id == posted_entry_id)
        .values(organization_id="forged-organization"),
        update(JournalEntry)
        .where(JournalEntry.id == posted_entry_id)
        .values(journal_id="forged-journal"),
        update(JournalEntry)
        .where(JournalEntry.id == posted_entry_id)
        .values(fiscal_period_id="forged-period"),
        update(JournalEntryLine)
        .where(JournalEntryLine.id == posted_line_id)
        .values(account_id="forged-account"),
        delete(JournalEntryLine).where(JournalEntryLine.id == posted_line_id),
        delete(JournalEntry).where(JournalEntry.id == posted_entry_id),
    )
    for operation in forbidden_operations:
        with pytest.raises(DBAPIError, match="permission denied|immutable"):
            await postgres_session.execute(operation)
            await postgres_session.commit()
        await postgres_session.rollback()

    posted_line_insert = JournalEntryLine(
        organization_id=organization_id,
        journal_entry_id=posted_entry_id,
        account_id=debit_account_id,
        line_number=3,
        debit=Decimal("1.00"),
        credit=Decimal("0.00"),
    )
    postgres_session.add(posted_line_insert)
    with pytest.raises(DBAPIError, match="immutable"):
        await postgres_session.commit()
    await postgres_session.rollback()

    refreshed = await JournalEntryService(postgres_session).get_entry(
        organization_id, posted_entry_id
    )
    assert refreshed.status.value == "POSTED"
    assert refreshed.fiscal_period_id == period_id
    assert len(refreshed.lines) == 2


@pytest.mark.asyncio
async def test_postgresql_rejects_search_path_shadowing_of_posted_lines(
    postgres_session: AsyncSession,
) -> None:
    organization, period, debit_account, credit_account = await _create_context(
        postgres_session
    )
    posted_entry = await _create_posted_entry(
        postgres_session, organization, period, debit_account, credit_account
    )
    organization_id = organization.id
    posted_entry_id = posted_entry.id
    debit_account_id = debit_account.id
    controlled_schema = f"p0_probe_{uuid4().hex[:12]}"

    with pytest.raises(DBAPIError, match="permission denied for database"):
        await postgres_session.execute(
            text(f"CREATE SCHEMA {controlled_schema} AUTHORIZATION fip_user")
        )
    await postgres_session.rollback()

    await postgres_session.execute(
        text(
            "CREATE TEMP TABLE journal_entries ("
            "id text PRIMARY KEY, organization_id text NOT NULL, "
            "status journalentrystatus NOT NULL)"
        )
    )
    await postgres_session.execute(
        text(
            "INSERT INTO journal_entries (id, organization_id, status) "
            "VALUES (:entry_id, :organization_id, 'DRAFT')"
        ),
        {"entry_id": posted_entry_id, "organization_id": organization_id},
    )
    await postgres_session.execute(text("SET LOCAL search_path TO pg_temp, public"))
    postgres_session.add(
        JournalEntryLine(
            organization_id=organization_id,
            journal_entry_id=posted_entry_id,
            account_id=debit_account_id,
            line_number=3,
            debit=Decimal("1.00"),
            credit=Decimal("0.00"),
        )
    )
    with pytest.raises(DBAPIError, match="immutable"):
        await postgres_session.commit()
    await postgres_session.rollback()


@pytest.mark.asyncio
async def test_postgresql_restricts_application_role_ownership_and_create(
    postgres_session: AsyncSession,
) -> None:
    result = await postgres_session.execute(
        text(
            "SELECT pg_get_userbyid(datdba), "
            "has_database_privilege('fip_user', current_database(), 'CREATE'), "
            "has_schema_privilege('fip_user', 'public', 'CREATE') "
            "FROM pg_database WHERE datname = current_database()"
        )
    )
    database_owner, database_create, schema_create = result.one()
    assert database_owner == "fip_database_owner"
    assert database_create is False
    assert schema_create is False

    membership_result = await postgres_session.execute(
        text(
            "SELECT EXISTS ("
            "SELECT 1 FROM pg_auth_members AS membership "
            "JOIN pg_roles AS member ON member.oid = membership.member "
            "JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid "
            "WHERE member.rolname = 'fip_user' "
            "AND granted_role.rolname IN "
            "('fip_database_owner', 'fip_accounting_owner'))"
        )
    )
    assert membership_result.scalar_one() is False


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


@pytest.mark.asyncio
async def test_postgresql_allows_one_atomic_reversal_and_rejects_direct_void(
    postgres_session: AsyncSession,
) -> None:
    organization, period, debit_account, credit_account = await _create_context(
        postgres_session
    )
    original = await _create_posted_entry(
        postgres_session, organization, period, debit_account, credit_account
    )
    original_id = original.id
    organization_id = organization.id
    period_id = period.id

    with pytest.raises(DBAPIError, match="permission denied|immutable"):
        await postgres_session.execute(
            update(JournalEntry)
            .where(JournalEntry.id == original_id)
            .values(status="VOIDED")
        )
        await postgres_session.commit()
    await postgres_session.rollback()

    original, reversal = await JournalEntryService(postgres_session).reverse_entry(
        organization_id,
        original_id,
        JournalEntryReversalCreate(
            fiscal_period_id=period_id,
            entry_date=date(2026, 1, 16),
            entry_number=f"REV-{uuid4().hex[:8]}",
            reason="Correction of source document",
        ),
        actor_user_id="postgres-integrity-tester",
    )
    assert original.status.value == "VOIDED"
    assert reversal.status.value == "POSTED"
    assert reversal.reversal_of_id == original_id
    assert reversal.reversal_reason == "Correction of source document"
    assert [(line.debit, line.credit) for line in reversal.lines] == [
        (Decimal("0.00"), Decimal("100.00")),
        (Decimal("100.00"), Decimal("0.00")),
    ]

    with pytest.raises(HTTPException, match="Only posted entries can be reversed"):
        await JournalEntryService(postgres_session).reverse_entry(
            organization_id,
            original_id,
            JournalEntryReversalCreate(
                fiscal_period_id=period_id,
                entry_date=date(2026, 1, 17),
                entry_number=f"REV-{uuid4().hex[:8]}",
                reason="Duplicate attempt",
            ),
            actor_user_id="postgres-integrity-tester",
        )


@pytest.mark.asyncio
async def test_postgresql_serializes_two_concurrent_reversals(
    postgres_session: AsyncSession,
) -> None:
    organization, period, debit_account, credit_account = await _create_context(
        postgres_session
    )
    original = await _create_posted_entry(
        postgres_session, organization, period, debit_account, credit_account
    )
    organization_id, period_id, original_id = organization.id, period.id, original.id

    async def reverse_once(sequence: int) -> str:
        engine = create_async_engine(POSTGRES_TEST_DATABASE_URL, echo=False)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                try:
                    await JournalEntryService(session).reverse_entry(
                        organization_id,
                        original_id,
                        JournalEntryReversalCreate(
                            fiscal_period_id=period_id,
                            entry_date=date(2026, 1, 18),
                            entry_number=f"RACE-{sequence}-{uuid4().hex[:6]}",
                            reason="Concurrent reversal test",
                        ),
                        actor_user_id="postgres-integrity-tester",
                    )
                    return "reversed"
                except HTTPException as exc:
                    await session.rollback()
                    return str(exc.status_code)
        finally:
            await engine.dispose()

    results = await asyncio.gather(reverse_once(1), reverse_once(2))
    assert results.count("reversed") == 1
    assert results.count("422") == 1


@pytest.mark.asyncio
async def test_postgresql_professional_reporting_mapping_preserves_acl_and_tenant_scope(
    postgres_session: AsyncSession,
) -> None:
    _, _, debit_account, _ = await _create_context(postgres_session)
    other_organization = Organization(name=f"Other mapping tenant {uuid4().hex[:12]}")
    postgres_session.add(other_organization)
    await postgres_session.commit()

    owner_result = await postgres_session.execute(
        text(
            "SELECT tableowner FROM pg_tables "
            "WHERE schemaname = 'public' "
            "AND tablename = 'financial_statement_mappings'"
        )
    )
    assert owner_result.scalar_one() == "fip_accounting_owner"
    privilege_result = await postgres_session.execute(
        text(
            "SELECT has_table_privilege("
            "'fip_user', 'public.financial_statement_mappings', "
            "'SELECT,INSERT,UPDATE,DELETE')"
        )
    )
    assert privilege_result.scalar_one() is True

    with pytest.raises(DBAPIError):
        await postgres_session.execute(
            text(
                "INSERT INTO public.financial_statement_mappings "
                "(id, organization_id, account_id, framework, statement_code, "
                "presentation_role, section_code, section_label, line_code, "
                "line_label, display_order, is_active, created_at, updated_at) "
                "VALUES (:id, :organization_id, :account_id, 'SYSCOHADA', "
                "'BALANCE_SHEET', 'ASSETS', 'ASSETS', 'Assets', 'BA-CASH', "
                "'Cash', 0, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "id": str(uuid4()),
                "organization_id": other_organization.id,
                "account_id": debit_account.id,
            },
        )
        await postgres_session.commit()
    await postgres_session.rollback()


@pytest.mark.asyncio
async def test_postgresql_cash_flow_mapping_preserves_acl_and_tenant_scope(
    postgres_session: AsyncSession,
) -> None:
    _, _, debit_account, _ = await _create_context(postgres_session)
    other_organization = Organization(name=f"Other cash-flow tenant {uuid4().hex[:12]}")
    postgres_session.add(other_organization)
    await postgres_session.commit()

    owner_result = await postgres_session.execute(
        text(
            "SELECT tableowner FROM pg_tables "
            "WHERE schemaname = 'public' "
            "AND tablename = 'cash_flow_account_mappings'"
        )
    )
    assert owner_result.scalar_one() == "fip_accounting_owner"
    privilege_result = await postgres_session.execute(
        text(
            "SELECT has_table_privilege("
            "'fip_user', 'public.cash_flow_account_mappings', "
            "'SELECT,INSERT,UPDATE,DELETE')"
        )
    )
    assert privilege_result.scalar_one() is True

    with pytest.raises(DBAPIError):
        await postgres_session.execute(
            text(
                "INSERT INTO public.cash_flow_account_mappings "
                "(id, organization_id, account_id, is_cash_account, "
                "cash_flow_category, is_active, created_at, updated_at) "
                "VALUES (:id, :organization_id, :account_id, true, NULL, "
                "true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "id": str(uuid4()),
                "organization_id": other_organization.id,
                "account_id": debit_account.id,
            },
        )
        await postgres_session.commit()
    await postgres_session.rollback()


@pytest.mark.asyncio
async def test_postgresql_cash_flow_reconciles_voided_original_with_posted_reversal(
    postgres_session: AsyncSession,
) -> None:
    organization, period, debit_account, credit_account = await _create_context(
        postgres_session
    )
    original = await _create_posted_entry(
        postgres_session, organization, period, debit_account, credit_account
    )
    await CashFlowConfigurationService(postgres_session).create(
        organization.id,
        "postgres-cash-flow-tester",
        CashFlowAccountMappingCreate(
            account_id=debit_account.id,
            is_cash_account=True,
        ),
    )
    await CashFlowConfigurationService(postgres_session).create(
        organization.id,
        "postgres-cash-flow-tester",
        CashFlowAccountMappingCreate(
            account_id=credit_account.id,
            cash_flow_category="OPERATING",
        ),
    )
    await JournalEntryService(postgres_session).reverse_entry(
        organization.id,
        original.id,
        JournalEntryReversalCreate(
            fiscal_period_id=period.id,
            entry_date=date(2026, 1, 20),
            entry_number=f"CF-VOID-{uuid4().hex[:8]}",
            reason="Cash-flow voided regression",
        ),
        actor_user_id="postgres-cash-flow-tester",
    )

    statement = await CashFlowService(postgres_session).statement(
        organization.id, date(2026, 1, 1), date(2026, 1, 31)
    )

    assert statement.operating_cash_flow == Decimal("0.00")
    assert statement.closing_cash == Decimal("0.00")
    assert statement.is_reconciled is True


@pytest.mark.asyncio
async def test_postgresql_serializes_concurrent_cash_flow_mapping_creation(
    postgres_session: AsyncSession,
) -> None:
    organization, _, debit_account, _ = await _create_context(postgres_session)
    organization_id, account_id = organization.id, debit_account.id

    async def create_mapping_once() -> str:
        engine = create_async_engine(POSTGRES_TEST_DATABASE_URL, echo=False)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                try:
                    await CashFlowConfigurationService(session).create(
                        organization_id,
                        "postgres-cash-flow-tester",
                        CashFlowAccountMappingCreate(
                            account_id=account_id,
                            is_cash_account=True,
                        ),
                    )
                    return "created"
                except HTTPException as exc:
                    await session.rollback()
                    return str(exc.status_code)
        finally:
            await engine.dispose()

    results = await asyncio.gather(create_mapping_once(), create_mapping_once())
    assert results.count("created") == 1
    assert results.count("409") == 1
    audit_events = list(
        await postgres_session.scalars(
            select(AuditEvent).where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.action == "CASH_FLOW_ACCOUNT_MAPPING_CREATED",
            )
        )
    )
    assert len(audit_events) == 1


@pytest.mark.asyncio
async def test_postgresql_vat_declaration_table_preserves_owner_and_acl(
    postgres_session: AsyncSession,
) -> None:
    table_name = VATDeclaration.__tablename__
    result = await postgres_session.execute(
        text(
            "SELECT pg_get_userbyid(c.relowner), "
            "has_table_privilege('fip_user', 'public.vat_declarations', 'SELECT'), "
            "has_table_privilege('fip_user', 'public.vat_declarations', 'INSERT'), "
            "has_table_privilege('fip_user', 'public.vat_declarations', 'UPDATE'), "
            "has_table_privilege('fip_user', 'public.vat_declarations', 'DELETE') "
            "FROM pg_class c WHERE c.relname = :table_name"
        ),
        {"table_name": table_name},
    )
    owner, can_select, can_insert, can_update, can_delete = result.one()
    assert owner == "fip_accounting_owner"
    assert (can_select, can_insert, can_update, can_delete) == (True, True, True, True)


@pytest.mark.asyncio
async def test_postgresql_liasse_remains_not_ready_when_only_another_tenant_has_entries(
    postgres_session: AsyncSession,
) -> None:
    organization_a, _, _, _ = await _create_context(postgres_session)
    organization_b, period_b, debit_account_b, credit_account_b = await _create_context(
        postgres_session
    )
    await _create_posted_entry(
        postgres_session,
        organization_b,
        period_b,
        debit_account_b,
        credit_account_b,
    )

    liasse = await SyscohadaLiasseService(postgres_session).get_liasse(
        organization_a.id, date(2026, 1, 1), date(2026, 1, 31)
    )

    assert liasse.readiness.status == LiasseReadinessStatus.NOT_READY
    assert liasse.readiness.posted_entry_count == 0
    assert liasse.professional_trial_balance is None
