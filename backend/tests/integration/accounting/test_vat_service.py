from datetime import date
from decimal import Decimal

import pytest
from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus, VATDirection
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.organization import Organization
from app.schemas.accounting.journal import JournalCreate
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.schemas.accounting.vat import VATEntryCreate, VATRateCreate, VATRateUpdate
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.accounting.journal_service import JournalService
from app.services.accounting.vat_service import VATService
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_vat_context(
    session: AsyncSession,
) -> tuple[Organization, FiscalPeriod, dict[str, Account], str]:
    organization = Organization(name="VAT test organization")
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
        "bank": Account(
            organization_id=organization.id,
            code="512000",
            name="Bank account",
            account_type="ASSET",
            level=1,
            path="/512000/",
        ),
        "input_vat": Account(
            organization_id=organization.id,
            code="445620",
            name="Recoverable VAT",
            account_type="ASSET",
            level=1,
            path="/445620/",
        ),
        "output_vat": Account(
            organization_id=organization.id,
            code="445710",
            name="Collected VAT",
            account_type="LIABILITY",
            level=1,
            path="/445710/",
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


async def _create_posted_entry(
    session: AsyncSession,
    organization_id: str,
    period_id: str,
    journal_id: str,
    entry_number: str,
    lines: list[JournalEntryLineCreate],
) -> str:
    journal_service = JournalEntryService(session)
    entry = await journal_service.create_entry(
        organization_id,
        JournalEntryCreate(
            journal_id=journal_id,
            fiscal_period_id=period_id,
            entry_number=entry_number,
            entry_date=date(2026, 1, 15),
            description=entry_number,
            lines=lines,
        ),
    )
    posted = await journal_service.post_entry(organization_id, entry.id)
    return posted.id


@pytest.mark.asyncio
async def test_registers_input_and_output_vat_then_builds_net_declaration(
    db_session: AsyncSession,
) -> None:
    organization, period, accounts, journal_id = await _create_vat_context(db_session)
    service = VATService(db_session)
    rate = await service.create_rate(
        organization.id,
        VATRateCreate(
            code="TVA18",
            name="Standard VAT",
            rate=Decimal("18.00"),
            effective_from=date(2026, 1, 1),
            input_vat_account_id=accounts["input_vat"].id,
            output_vat_account_id=accounts["output_vat"].id,
        ),
    )
    sale_entry_id = await _create_posted_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-2026-0001",
        [
            JournalEntryLineCreate(
                account_id=accounts["bank"].id, debit=Decimal("118.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("100.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["output_vat"].id, credit=Decimal("18.00")
            ),
        ],
    )
    purchase_entry_id = await _create_posted_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-2026-0002",
        [
            JournalEntryLineCreate(
                account_id=accounts["expense"].id, debit=Decimal("100.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["input_vat"].id, debit=Decimal("18.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["bank"].id, credit=Decimal("118.00")
            ),
        ],
    )

    calculation = await service.calculate(
        organization.id,
        VATEntryCreate(
            vat_rate_id=rate.id,
            journal_entry_id=sale_entry_id,
            tax_date=date(2026, 1, 15),
            taxable_amount=Decimal("100.00"),
            direction=VATDirection.OUTPUT,
        ),
    )
    output_entry = await service.create_entry(
        organization.id,
        VATEntryCreate(
            vat_rate_id=rate.id,
            journal_entry_id=sale_entry_id,
            tax_date=date(2026, 1, 15),
            taxable_amount=Decimal("100.00"),
            direction=VATDirection.OUTPUT,
        ),
    )
    input_entry = await service.create_entry(
        organization.id,
        VATEntryCreate(
            vat_rate_id=rate.id,
            journal_entry_id=purchase_entry_id,
            tax_date=date(2026, 1, 15),
            taxable_amount=Decimal("100.00"),
            direction=VATDirection.INPUT,
        ),
    )
    declaration = await service.summary(
        organization.id, date(2026, 1, 1), date(2026, 1, 31)
    )

    assert calculation.vat_amount == Decimal("18.00")
    assert calculation.total_amount == Decimal("118.00")
    assert output_entry.vat_amount == Decimal("18.00")
    assert input_entry.vat_amount == Decimal("18.00")
    assert declaration.total_output_vat == Decimal("18.00")
    assert declaration.total_input_vat == Decimal("18.00")
    assert declaration.net_vat_payable == Decimal("0.00")


@pytest.mark.asyncio
async def test_rejects_duplicate_entry_and_rate_outside_effective_period(
    db_session: AsyncSession,
) -> None:
    organization, period, accounts, journal_id = await _create_vat_context(db_session)
    service = VATService(db_session)
    rate = await service.create_rate(
        organization.id,
        VATRateCreate(
            code="TVA18",
            name="Standard VAT",
            rate=Decimal("18.00"),
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 1, 31),
            input_vat_account_id=accounts["input_vat"].id,
            output_vat_account_id=accounts["output_vat"].id,
        ),
    )
    entry_id = await _create_posted_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "OD-2026-0003",
        [
            JournalEntryLineCreate(
                account_id=accounts["bank"].id, debit=Decimal("118.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("100.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["output_vat"].id, credit=Decimal("18.00")
            ),
        ],
    )
    data = VATEntryCreate(
        vat_rate_id=rate.id,
        journal_entry_id=entry_id,
        tax_date=date(2026, 1, 15),
        taxable_amount=Decimal("100.00"),
        direction=VATDirection.OUTPUT,
    )
    await service.create_entry(organization.id, data)

    with pytest.raises(HTTPException, match="already has") as duplicate:
        await service.create_entry(organization.id, data)
    assert duplicate.value.status_code == 409

    with pytest.raises(HTTPException, match="Active VAT rate") as inactive:
        await service.calculate(
            organization.id,
            VATEntryCreate(
                vat_rate_id=rate.id,
                journal_entry_id=entry_id,
                tax_date=date(2026, 2, 1),
                taxable_amount=Decimal("100.00"),
                direction=VATDirection.OUTPUT,
            ),
        )
    assert inactive.value.status_code == 422


@pytest.mark.asyncio
async def test_updates_rate_with_valid_accounts_and_rejects_reversed_effective_dates(
    db_session: AsyncSession,
) -> None:
    organization, _, accounts, _ = await _create_vat_context(db_session)
    service = VATService(db_session)
    rate = await service.create_rate(
        organization.id,
        VATRateCreate(
            code="TVA18",
            name="Standard VAT",
            rate=Decimal("18.00"),
            effective_from=date(2026, 1, 1),
            input_vat_account_id=accounts["input_vat"].id,
            output_vat_account_id=accounts["output_vat"].id,
        ),
    )

    updated = await service.update_rate(
        organization.id,
        rate.id,
        VATRateUpdate(name="Reduced VAT", is_active=False),
    )
    assert updated.name == "Reduced VAT"
    assert updated.is_active is False

    with pytest.raises(HTTPException, match="Effective end date") as invalid_dates:
        await service.update_rate(
            organization.id,
            rate.id,
            VATRateUpdate(effective_to=date(2025, 12, 31)),
        )
    assert invalid_dates.value.status_code == 422
