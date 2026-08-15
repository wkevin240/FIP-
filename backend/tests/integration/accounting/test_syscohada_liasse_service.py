import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.audit.audit_event import AuditEvent
from app.models.organization import Organization
from app.schemas.accounting.cash_flow import CashFlowAccountMappingCreate
from app.schemas.accounting.journal import JournalCreate
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.schemas.accounting.professional_reporting import (
    FinancialStatementMappingCreate,
)
from app.schemas.accounting.syscohada_liasse import LiasseReadinessStatus
from app.services.accounting.cash_flow_configuration_service import (
    CashFlowConfigurationService,
)
from app.services.accounting.financial_statement_mapping_service import (
    FinancialStatementMappingService,
)
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.accounting.journal_service import JournalService
from app.services.accounting.syscohada_liasse_service import SyscohadaLiasseService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_context(
    session: AsyncSession,
) -> tuple[Organization, FiscalPeriod, dict[str, Account], str]:
    organization = Organization(name=f"Liasse test organization {uuid4().hex[:12]}")
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
        organization.id, JournalCreate(code="OD", name="General journal")
    )
    return organization, period, accounts, journal.id


async def _post(
    session: AsyncSession,
    organization_id: str,
    period_id: str,
    journal_id: str,
    entry_number: str,
    entry_date: date,
    lines: list[JournalEntryLineCreate],
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
    await JournalEntryService(session).post_entry(organization_id, entry.id)


async def _map_professional(
    session: AsyncSession,
    organization_id: str,
    account_id: str,
    statement_code: str,
    presentation_role: str,
    line_code: str,
) -> None:
    await FinancialStatementMappingService(session).create(
        organization_id,
        "liasse-test-user",
        FinancialStatementMappingCreate(
            account_id=account_id,
            statement_code=statement_code,
            presentation_role=presentation_role,
            section_code=presentation_role,
            section_label=presentation_role.replace("_", " ").title(),
            line_code=line_code,
            line_label=line_code,
            display_order=10,
        ),
    )


@pytest.mark.asyncio
async def test_liasse_returns_not_ready_without_real_posted_data(
    db_session: AsyncSession,
) -> None:
    organization = Organization(name=f"Empty liasse organization {uuid4().hex[:12]}")
    db_session.add(organization)
    await db_session.commit()

    service = SyscohadaLiasseService(db_session)
    liasse = await service.get_liasse(
        organization.id, date(2026, 1, 1), date(2026, 1, 31)
    )

    assert liasse.readiness.status == LiasseReadinessStatus.NOT_READY
    assert liasse.readiness.reasons == ["NO_POSTED_ENTRIES_FOR_PERIOD"]
    assert liasse.readiness.posted_entry_count == 0
    assert liasse.professional_trial_balance is None
    assert liasse.balance_sheet is None
    assert liasse.income_statement is None
    assert liasse.cash_flow is None
    assert len(liasse.annex_notes) == 3
    assert all(note.data == {} for note in liasse.annex_notes)

    exported = json.loads(
        await service.export_json(
            organization.id,
            "liasse-test-user",
            date(2026, 1, 1),
            date(2026, 1, 31),
        )
    )
    assert exported["readiness"]["status"] == "NOT_READY"
    assert exported["professional_trial_balance"] is None
    export_event = await db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.organization_id == organization.id,
            AuditEvent.action == "SYSCOHADA_LIASSE_EXPORTED",
        )
    )
    assert export_event is not None


@pytest.mark.asyncio
async def test_liasse_returns_incomplete_when_real_data_lacks_configuration(
    db_session: AsyncSession,
) -> None:
    organization, period, accounts, journal_id = await _create_context(db_session)
    await _post(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-INCOMPLETE",
        date(2026, 1, 10),
        [
            JournalEntryLineCreate(
                account_id=accounts["cash"].id, debit=Decimal("100.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["equity"].id, credit=Decimal("100.00")
            ),
        ],
    )

    liasse = await SyscohadaLiasseService(db_session).get_liasse(
        organization.id, date(2026, 1, 1), date(2026, 1, 31)
    )

    assert liasse.readiness.status == LiasseReadinessStatus.INCOMPLETE
    assert "REPORTING_RECONCILIATION_FAILED" in liasse.readiness.reasons
    assert "UNMAPPED_BALANCE_SHEET_ACCOUNTS" in liasse.readiness.reasons
    assert "CASH_FLOW_NOT_CONFIGURED" in liasse.readiness.reasons
    assert liasse.balance_sheet is not None
    assert liasse.balance_sheet.unmapped_account_codes == ["101000", "571000"]


@pytest.mark.asyncio
async def test_liasse_returns_ready_only_from_complete_real_configuration(
    db_session: AsyncSession,
) -> None:
    organization, period, accounts, journal_id = await _create_context(db_session)
    await _post(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-CAPITAL",
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
    await _post(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-REVENUE",
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
    await _post(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-EXPENSE",
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

    for account_key, role, line_code in (
        ("cash", "ASSETS", "BA-CASH"),
        ("equity", "LIABILITIES_EQUITY", "BE-EQUITY"),
        ("revenue", "LIABILITIES_EQUITY", "BE-RESULT-REVENUE"),
        ("expense", "LIABILITIES_EQUITY", "BE-RESULT-EXPENSE"),
    ):
        await _map_professional(
            db_session,
            organization.id,
            accounts[account_key].id,
            "BALANCE_SHEET",
            role,
            line_code,
        )
    await _map_professional(
        db_session,
        organization.id,
        accounts["revenue"].id,
        "INCOME_STATEMENT",
        "REVENUE",
        "IS-REVENUE",
    )
    await _map_professional(
        db_session,
        organization.id,
        accounts["expense"].id,
        "INCOME_STATEMENT",
        "EXPENSE",
        "IS-EXPENSE",
    )
    cash_configuration = CashFlowConfigurationService(db_session)
    await cash_configuration.create(
        organization.id,
        "liasse-test-user",
        CashFlowAccountMappingCreate(
            account_id=accounts["cash"].id, is_cash_account=True
        ),
    )
    for account_key, category in (
        ("equity", "FINANCING"),
        ("revenue", "OPERATING"),
        ("expense", "OPERATING"),
    ):
        await cash_configuration.create(
            organization.id,
            "liasse-test-user",
            CashFlowAccountMappingCreate(
                account_id=accounts[account_key].id,
                cash_flow_category=category,
            ),
        )

    service = SyscohadaLiasseService(db_session)
    liasse = await service.get_liasse(
        organization.id, date(2026, 1, 1), date(2026, 1, 31)
    )

    assert liasse.readiness.status == LiasseReadinessStatus.READY
    assert liasse.readiness.reasons == []
    assert liasse.readiness.posted_entry_count == 3
    assert liasse.balance_sheet is not None
    assert liasse.balance_sheet.total_assets == Decimal("1300.00")
    assert liasse.income_statement is not None
    assert liasse.income_statement.net_result == Decimal("300.00")
    assert liasse.cash_flow is not None
    assert liasse.cash_flow.closing_cash == Decimal("1300.00")
    assert all(
        note.status == LiasseReadinessStatus.READY for note in liasse.annex_notes
    )
