from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.journal import Journal
from app.models.accounting.journal_entry import JournalEntry
from app.models.audit.audit_event import AuditEvent
from app.models.organization import Organization
from app.schemas.treasury.accounting import (
    TreasuryAccountingProfileCreate,
    TreasuryTransactionPostingCreate,
)
from app.schemas.treasury.bank_account import TreasuryBankAccountCreate
from app.schemas.treasury.transaction import TreasuryBankTransactionCreate
from app.services.treasury.bank_account_service import TreasuryBankAccountService
from app.services.treasury.transaction_service import TreasuryTransactionService
from app.services.treasury.treasury_accounting_service import TreasuryAccountingService
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def _context(session: AsyncSession):
    suffix = uuid4().hex[:10]
    organization = Organization(name=f"Treasury accounting {suffix}")
    session.add(organization)
    await session.flush()
    year = FiscalYear(
        organization_id=organization.id,
        name=f"FY {suffix}",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status=FiscalYearStatus.OPEN,
    )
    session.add(year)
    await session.flush()
    period = FiscalPeriod(
        organization_id=organization.id,
        fiscal_year_id=year.id,
        name=f"P {suffix}",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status=FiscalPeriodStatus.OPEN,
    )
    journal = Journal(
        organization_id=organization.id,
        code=f"BQ{suffix[:8]}",
        name="Bank journal",
        journal_type="GENERAL",
        is_active=True,
    )
    bank = Account(
        organization_id=organization.id,
        code=f"512{suffix[:7]}",
        name="Bank",
        account_type="ASSET",
        level=1,
        path="/512/",
    )
    receivable = Account(
        organization_id=organization.id,
        code=f"411{suffix[:7]}",
        name="Receivable",
        account_type="ASSET",
        level=1,
        path="/411/",
    )
    expense = Account(
        organization_id=organization.id,
        code=f"627{suffix[:7]}",
        name="Bank charge",
        account_type="EXPENSE",
        level=1,
        path="/627/",
    )
    session.add_all([period, journal, bank, receivable, expense])
    await session.commit()
    bank_profile = await TreasuryBankAccountService(session).create_bank_account(
        organization.id,
        TreasuryBankAccountCreate(
            ledger_account_id=bank.id,
            bank_name="Bank",
            account_name="Operating",
            account_number=f"ACC-{suffix}",
            currency="XOF",
            opening_balance=Decimal("0.00"),
            opening_date=date(2026, 1, 1),
        ),
    )
    accounting = TreasuryAccountingService(session)
    await accounting.configure_profile(
        organization.id,
        "treasury-tester",
        TreasuryAccountingProfileCreate(journal_id=journal.id),
    )
    return organization, period, bank_profile, receivable, expense, accounting


@pytest.mark.asyncio
async def test_treasury_posts_inflow_and_outflow_with_decimal_audit_and_idempotence(
    db_session: AsyncSession,
) -> None:
    organization, _, bank_profile, receivable, expense, accounting = await _context(
        db_session
    )
    transactions = TreasuryTransactionService(db_session)
    inflow = await transactions.create_transaction(
        organization.id,
        TreasuryBankTransactionCreate(
            treasury_bank_account_id=bank_profile.id,
            transaction_date=date(2026, 2, 1),
            amount=Decimal("250.00"),
            description="Customer collection",
            external_id=f"IN-{uuid4().hex}",
        ),
    )
    first = await accounting.post_transaction(
        organization.id,
        "treasury-tester",
        inflow.id,
        TreasuryTransactionPostingCreate(counterpart_account_id=receivable.id),
    )
    again = await accounting.post_transaction(
        organization.id,
        "treasury-tester",
        inflow.id,
        TreasuryTransactionPostingCreate(counterpart_account_id=expense.id),
    )
    assert first.id == again.id
    entry = await db_session.get(JournalEntry, first.journal_entry_id)
    assert entry is not None and entry.status.value == "POSTED"
    assert (
        await db_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization.id,
                AuditEvent.action == "TREASURY_TRANSACTION_POSTED_TO_ACCOUNTING",
                AuditEvent.resource_id == inflow.id,
            )
        )
        == 1
    )
    outflow = await transactions.create_transaction(
        organization.id,
        TreasuryBankTransactionCreate(
            treasury_bank_account_id=bank_profile.id,
            transaction_date=date(2026, 2, 2),
            amount=Decimal("-25.50"),
            description="Bank charge",
            external_id=f"OUT-{uuid4().hex}",
        ),
    )
    posted_outflow = await accounting.post_transaction(
        organization.id,
        "treasury-tester",
        outflow.id,
        TreasuryTransactionPostingCreate(counterpart_account_id=expense.id),
    )
    assert posted_outflow.journal_entry_id != first.journal_entry_id


@pytest.mark.asyncio
async def test_treasury_refuses_closed_period_and_cross_tenant_counterpart(
    db_session: AsyncSession,
) -> None:
    organization, period, bank_profile, _, expense, accounting = await _context(
        db_session
    )
    transaction = await TreasuryTransactionService(db_session).create_transaction(
        organization.id,
        TreasuryBankTransactionCreate(
            treasury_bank_account_id=bank_profile.id,
            transaction_date=date(2026, 2, 1),
            amount=Decimal("50.00"),
            description="Collection",
            external_id=f"C-{uuid4().hex}",
        ),
    )
    period.status = FiscalPeriodStatus.CLOSED
    await db_session.commit()
    with pytest.raises(HTTPException) as closed:
        await accounting.post_transaction(
            organization.id,
            "treasury-tester",
            transaction.id,
            TreasuryTransactionPostingCreate(counterpart_account_id=expense.id),
        )
    assert closed.value.status_code == 422
    assert (
        await db_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization.id,
                AuditEvent.resource_id == transaction.id,
                AuditEvent.action == "TREASURY_TRANSACTION_POSTED_TO_ACCOUNTING",
            )
        )
        == 0
    )
