from datetime import date
from decimal import Decimal

import pytest
from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.organization import Organization
from app.models.user import User
from app.schemas.accounting.bank_reconciliation import BankTransactionCreate
from app.schemas.accounting.journal import JournalCreate
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.services.accounting.bank_reconciliation_service import (
    BankReconciliationService,
)
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.accounting.journal_service import JournalService
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_reconciliation_context(
    session: AsyncSession,
) -> tuple[Organization, User, FiscalPeriod, dict[str, Account], str]:
    organization = Organization(name="Bank reconciliation test organization")
    user = User(
        email="reconciler@example.test",
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
    accounts = {
        "bank": Account(
            organization_id=organization.id,
            code="512000",
            name="Bank account",
            account_type="ASSET",
            level=1,
            path="/512000/",
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
        JournalCreate(code="BQ", name="Bank journal"),
    )
    return organization, user, period, accounts, journal.id


async def _create_posted_entry(
    session: AsyncSession,
    organization_id: str,
    period_id: str,
    journal_id: str,
    entry_number: str,
    entry_date: date,
    lines: list[JournalEntryLineCreate],
) -> str:
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
    posted = await JournalEntryService(session).post_entry(organization_id, entry.id)
    return posted.id


@pytest.mark.asyncio
async def test_exact_candidate_and_reconciliation_of_incoming_transaction(
    db_session: AsyncSession,
) -> None:
    (
        organization,
        user,
        period,
        accounts,
        journal_id,
    ) = await _create_reconciliation_context(db_session)
    entry_id = await _create_posted_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "BQ-2026-0001",
        date(2026, 1, 15),
        [
            JournalEntryLineCreate(
                account_id=accounts["bank"].id, debit=Decimal("500.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("500.00")
            ),
        ],
    )
    service = BankReconciliationService(db_session)
    transaction = await service.create_transaction(
        organization.id,
        BankTransactionCreate(
            bank_account_id=accounts["bank"].id,
            transaction_date=date(2026, 1, 16),
            amount=Decimal("500.00"),
            description="Customer transfer",
            external_id="BANK-001",
        ),
    )

    candidates = await service.candidate_entries(organization.id, transaction.id)
    reconciliation = await service.reconcile(
        organization.id, transaction.id, entry_id, user.id
    )

    assert [candidate.journal_entry_id for candidate in candidates] == [entry_id]
    assert reconciliation.matched_amount == Decimal("500.00")
    assert reconciliation.match_method == "MANUAL"
    assert await service.candidate_entries(organization.id, transaction.id) == []


@pytest.mark.asyncio
async def test_outgoing_transaction_requires_same_negative_direction(
    db_session: AsyncSession,
) -> None:
    (
        organization,
        user,
        period,
        accounts,
        journal_id,
    ) = await _create_reconciliation_context(db_session)
    entry_id = await _create_posted_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "BQ-2026-0002",
        date(2026, 1, 20),
        [
            JournalEntryLineCreate(
                account_id=accounts["expense"].id, debit=Decimal("100.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["bank"].id, credit=Decimal("100.00")
            ),
        ],
    )
    service = BankReconciliationService(db_session)
    transaction = await service.create_transaction(
        organization.id,
        BankTransactionCreate(
            bank_account_id=accounts["bank"].id,
            transaction_date=date(2026, 1, 20),
            amount=Decimal("-100.00"),
            description="Supplier debit",
            external_id="BANK-002",
        ),
    )

    reconciliation = await service.reconcile(
        organization.id, transaction.id, entry_id, user.id
    )

    assert reconciliation.matched_amount == Decimal("100.00")


@pytest.mark.asyncio
async def test_mismatched_or_already_used_entry_is_rejected(
    db_session: AsyncSession,
) -> None:
    (
        organization,
        user,
        period,
        accounts,
        journal_id,
    ) = await _create_reconciliation_context(db_session)
    entry_id = await _create_posted_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "BQ-2026-0003",
        date(2026, 1, 10),
        [
            JournalEntryLineCreate(
                account_id=accounts["bank"].id, debit=Decimal("250.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("250.00")
            ),
        ],
    )
    service = BankReconciliationService(db_session)
    mismatch = await service.create_transaction(
        organization.id,
        BankTransactionCreate(
            bank_account_id=accounts["bank"].id,
            transaction_date=date(2026, 1, 10),
            amount=Decimal("200.00"),
            description="Wrong amount",
            external_id="BANK-003",
        ),
    )
    with pytest.raises(HTTPException, match="must match exactly") as exc_info:
        await service.reconcile(organization.id, mismatch.id, entry_id, user.id)
    assert exc_info.value.status_code == 422
    await db_session.refresh(organization)
    await db_session.refresh(user)
    await db_session.refresh(accounts["bank"])

    exact = await service.create_transaction(
        organization.id,
        BankTransactionCreate(
            bank_account_id=accounts["bank"].id,
            transaction_date=date(2026, 1, 10),
            amount=Decimal("250.00"),
            description="Exact amount",
            external_id="BANK-004",
        ),
    )
    await service.reconcile(organization.id, exact.id, entry_id, user.id)

    duplicate = await service.create_transaction(
        organization.id,
        BankTransactionCreate(
            bank_account_id=accounts["bank"].id,
            transaction_date=date(2026, 1, 10),
            amount=Decimal("250.00"),
            description="Duplicate candidate",
            external_id="BANK-005",
        ),
    )
    with pytest.raises(HTTPException, match="already reconciled") as exc_info:
        await service.reconcile(organization.id, duplicate.id, entry_id, user.id)
    assert exc_info.value.status_code == 409
