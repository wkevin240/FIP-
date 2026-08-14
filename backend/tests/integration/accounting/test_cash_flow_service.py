from datetime import date
from decimal import Decimal

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
from app.services.accounting.cash_flow_configuration_service import (
    CashFlowConfigurationService,
)
from app.services.accounting.cash_flow_service import CashFlowService
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.accounting.journal_service import JournalService
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_context(
    session: AsyncSession,
) -> tuple[Organization, FiscalPeriod, dict[str, Account], str]:
    organization = Organization(name="Cash-flow reporting organization")
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
        "revenue": Account(
            organization_id=organization.id,
            code="701000",
            name="Sales revenue",
            account_type="REVENUE",
            level=1,
            path="/701000/",
        ),
        "fixed_asset": Account(
            organization_id=organization.id,
            code="241000",
            name="Equipment",
            account_type="ASSET",
            level=1,
            path="/241000/",
        ),
        "equity": Account(
            organization_id=organization.id,
            code="101000",
            name="Share capital",
            account_type="EQUITY",
            level=1,
            path="/101000/",
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
    service: CashFlowConfigurationService,
    organization_id: str,
    account_id: str,
    is_cash_account: bool,
    category: str | None = None,
) -> None:
    await service.create(
        organization_id,
        "cash-flow-user",
        CashFlowAccountMappingCreate(
            account_id=account_id,
            is_cash_account=is_cash_account,
            cash_flow_category=category,
        ),
    )


@pytest.mark.asyncio
async def test_cash_flow_statement_reconciles_opening_and_three_categories(
    db_session: AsyncSession,
) -> None:
    organization, period, accounts, journal_id = await _create_context(db_session)
    await _post(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-OPENING",
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
        "OD-OPERATING",
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
        "OD-INVESTING",
        date(2026, 1, 20),
        [
            JournalEntryLineCreate(
                account_id=accounts["fixed_asset"].id, debit=Decimal("200.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["cash"].id, credit=Decimal("200.00")
            ),
        ],
    )
    await _post(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-FINANCING",
        date(2026, 1, 25),
        [
            JournalEntryLineCreate(
                account_id=accounts["cash"].id, debit=Decimal("300.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["equity"].id, credit=Decimal("300.00")
            ),
        ],
    )

    configuration = CashFlowConfigurationService(db_session)
    await _map(configuration, organization.id, accounts["cash"].id, True)
    await _map(
        configuration, organization.id, accounts["revenue"].id, False, "OPERATING"
    )
    await _map(
        configuration, organization.id, accounts["fixed_asset"].id, False, "INVESTING"
    )
    await _map(
        configuration, organization.id, accounts["equity"].id, False, "FINANCING"
    )

    statement = await CashFlowService(db_session).statement(
        organization.id, date(2026, 1, 15), date(2026, 1, 31)
    )

    assert statement.opening_cash == Decimal("1000.00")
    assert statement.operating_cash_flow == Decimal("500.00")
    assert statement.investing_cash_flow == Decimal("-200.00")
    assert statement.financing_cash_flow == Decimal("300.00")
    assert statement.unclassified_cash_flow == Decimal("0.00")
    assert statement.net_cash_flow == Decimal("600.00")
    assert statement.closing_cash == Decimal("1600.00")
    assert statement.computed_closing_cash == Decimal("1600.00")
    assert statement.is_reconciled is True
    assert statement.is_complete is True
    mapping_events = list(
        await db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.organization_id == organization.id,
                AuditEvent.action == "CASH_FLOW_ACCOUNT_MAPPING_CREATED",
            )
        )
    )
    assert len(mapping_events) == 4


@pytest.mark.asyncio
async def test_cash_flow_statement_marks_unmapped_counterparty_incomplete(
    db_session: AsyncSession,
) -> None:
    organization, period, accounts, journal_id = await _create_context(db_session)
    await _post(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-UNCLASSIFIED",
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
    await _map(
        CashFlowConfigurationService(db_session),
        organization.id,
        accounts["cash"].id,
        True,
    )

    statement = await CashFlowService(db_session).statement(
        organization.id, date(2026, 1, 1), date(2026, 1, 31)
    )

    assert statement.unclassified_cash_flow == Decimal("500.00")
    assert statement.unclassified_entry_numbers == ["OD-UNCLASSIFIED"]
    assert statement.is_complete is False
    assert statement.is_reconciled is True


@pytest.mark.asyncio
async def test_cash_flow_mapping_rejects_cross_tenant_and_non_asset_cash_account(
    db_session: AsyncSession,
) -> None:
    organization, _, accounts, _ = await _create_context(db_session)
    other_organization = Organization(name="Other cash-flow organization")
    db_session.add(other_organization)
    await db_session.commit()
    service = CashFlowConfigurationService(db_session)

    with pytest.raises(HTTPException) as cross_tenant_error:
        await _map(service, other_organization.id, accounts["cash"].id, True)
    assert cross_tenant_error.value.status_code == 422

    with pytest.raises(HTTPException) as account_type_error:
        await _map(service, organization.id, accounts["revenue"].id, True)
    assert account_type_error.value.status_code == 422
