import json
from datetime import date
from decimal import Decimal

import pytest
from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.audit.audit_event import AuditEvent
from app.models.organization import Organization
from app.schemas.accounting.journal import JournalCreate
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.schemas.accounting.professional_reporting import (
    FinancialStatementMappingCreate,
)
from app.services.accounting.financial_statement_mapping_service import (
    FinancialStatementMappingService,
)
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.accounting.journal_service import JournalService
from app.services.accounting.regulatory_reporting_export_service import (
    RegulatoryReportingExportService,
)
from app.services.accounting.reporting_service import ReportingService
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_context(
    session: AsyncSession,
) -> tuple[Organization, FiscalPeriod, dict[str, Account], str]:
    organization = Organization(name="Professional reporting organization")
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


async def _map(
    service: FinancialStatementMappingService,
    organization_id: str,
    account_id: str,
    statement_code: str,
    presentation_role: str,
    line_code: str,
) -> None:
    await service.create(
        organization_id,
        "reporting-user",
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
async def test_professional_reporting_reconciles_trial_balance_statements_and_audit(
    db_session: AsyncSession,
) -> None:
    organization, period, accounts, journal_id = await _create_context(db_session)
    await _post(
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
    await _post(
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
    await _post(
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

    mapping_service = FinancialStatementMappingService(db_session)
    await _map(
        mapping_service,
        organization.id,
        accounts["cash"].id,
        "BALANCE_SHEET",
        "ASSETS",
        "BA-CASH",
    )
    await _map(
        mapping_service,
        organization.id,
        accounts["equity"].id,
        "BALANCE_SHEET",
        "LIABILITIES_EQUITY",
        "BE-EQUITY",
    )
    await _map(
        mapping_service,
        organization.id,
        accounts["revenue"].id,
        "BALANCE_SHEET",
        "LIABILITIES_EQUITY",
        "BE-RESULT-REVENUE",
    )
    await _map(
        mapping_service,
        organization.id,
        accounts["expense"].id,
        "BALANCE_SHEET",
        "LIABILITIES_EQUITY",
        "BE-RESULT-EXPENSE",
    )
    await _map(
        mapping_service,
        organization.id,
        accounts["revenue"].id,
        "INCOME_STATEMENT",
        "REVENUE",
        "IS-REVENUE",
    )
    await _map(
        mapping_service,
        organization.id,
        accounts["expense"].id,
        "INCOME_STATEMENT",
        "EXPENSE",
        "IS-EXPENSE",
    )

    reporting = ReportingService(db_session)
    trial = await reporting.professional_trial_balance(
        organization.id, date(2026, 1, 15), date(2026, 1, 31)
    )
    assert trial.total_opening_debit == Decimal("1000.00")
    assert trial.total_opening_credit == Decimal("1000.00")
    assert trial.total_movement_debit == Decimal("700.00")
    assert trial.total_movement_credit == Decimal("700.00")
    assert trial.total_closing_debit == Decimal("1500.00")
    assert trial.total_closing_credit == Decimal("1500.00")
    assert trial.is_opening_balanced is True
    assert trial.is_movement_balanced is True
    assert trial.is_closing_balanced is True

    balance_sheet = await reporting.professional_financial_statement(
        organization.id, "BALANCE_SHEET", date(2026, 1, 31)
    )
    income_statement = await reporting.professional_financial_statement(
        organization.id,
        "INCOME_STATEMENT",
        date(2026, 1, 31),
        date(2026, 1, 1),
    )
    assert balance_sheet.total_assets == Decimal("1300.00")
    assert balance_sheet.total_liabilities_and_equity == Decimal("1300.00")
    assert balance_sheet.is_balanced is True
    assert balance_sheet.unmapped_account_codes == []
    assert income_statement.net_result == Decimal("300.00")
    assert income_statement.unmapped_account_codes == []

    reconciliation = await reporting.reconcile_reporting(
        organization.id, date(2026, 1, 15), date(2026, 1, 31)
    )
    assert reconciliation.is_consistent is True
    assert reconciliation.movement_debit == reconciliation.movement_credit
    assert reconciliation.closing_debit == reconciliation.closing_credit

    export = await reporting.export_professional_trial_balance_csv(
        organization.id, "reporting-user", date(2026, 1, 15), date(2026, 1, 31)
    )
    assert export.splitlines()[0].startswith("account_code,account_name,account_type")
    assert "571000,Cash,ASSET,1000.00,0.00,500.00,200.00,1300.00,0.00" in export
    export_event = await db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.organization_id == organization.id,
            AuditEvent.action == "PROFESSIONAL_TRIAL_BALANCE_EXPORTED",
        )
    )
    assert export_event is not None

    package_content = await RegulatoryReportingExportService(
        db_session
    ).export_syscohada_package(
        organization.id, "reporting-user", date(2026, 1, 15), date(2026, 1, 31)
    )
    package = json.loads(package_content)
    assert package["schema_version"] == "1.0"
    assert package["framework"] == "SYSCOHADA"
    assert package["controls"]["is_consistent"] is True
    assert package["balance_sheet"]["total_assets"] == "1300.00"
    assert package["income_statement"]["net_result"] == "300.00"
    package_event = await db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.organization_id == organization.id,
            AuditEvent.action == "SYSCOHADA_REPORTING_PACKAGE_EXPORTED",
        )
    )
    assert package_event is not None


@pytest.mark.asyncio
async def test_professional_mapping_rejects_cross_tenant_and_incompatible_role(
    db_session: AsyncSession,
) -> None:
    organization, _, accounts, _ = await _create_context(db_session)
    other_organization = Organization(name="Other reporting organization")
    db_session.add(other_organization)
    await db_session.commit()
    service = FinancialStatementMappingService(db_session)

    with pytest.raises(HTTPException) as cross_tenant_error:
        await _map(
            service,
            other_organization.id,
            accounts["cash"].id,
            "BALANCE_SHEET",
            "ASSETS",
            "BA-CASH",
        )
    assert cross_tenant_error.value.status_code == 422

    with pytest.raises(HTTPException) as semantic_error:
        await _map(
            service,
            organization.id,
            accounts["revenue"].id,
            "INCOME_STATEMENT",
            "EXPENSE",
            "IS-INVALID",
        )
    assert semantic_error.value.status_code == 422


@pytest.mark.asyncio
async def test_reconciliation_rejects_incomplete_professional_balance_sheet_mapping(
    db_session: AsyncSession,
) -> None:
    organization, period, accounts, journal_id = await _create_context(db_session)
    await _post(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-2026-UNMAPPED",
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

    reconciliation = await ReportingService(db_session).reconcile_reporting(
        organization.id, date(2026, 1, 1), date(2026, 1, 31)
    )

    assert reconciliation.trial_balance_is_balanced is True
    assert reconciliation.balance_sheet_is_balanced is True
    assert reconciliation.professional_balance_sheet_is_balanced is True
    assert reconciliation.professional_balance_sheet_is_complete is False
    assert reconciliation.unmapped_balance_sheet_account_codes == ["101000", "571000"]
    assert reconciliation.is_consistent is False

    with pytest.raises(HTTPException) as export_error:
        await RegulatoryReportingExportService(db_session).export_syscohada_package(
            organization.id, "reporting-user", date(2026, 1, 1), date(2026, 1, 31)
        )
    assert export_error.value.status_code == 422
    export_event = await db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.organization_id == organization.id,
            AuditEvent.action == "SYSCOHADA_REPORTING_PACKAGE_EXPORTED",
        )
    )
    assert export_event is None
