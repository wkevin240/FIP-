from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.enums.accounting import FiscalPeriodStatus
from app.models import Account, Organization
from app.models.accounting.audit_log import AuditLog
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.journal_entry import JournalEntry, JournalEntryLine, JournalEntryStatus
from app.models.accounting.ledger_posting import LedgerPosting
from app.services.accounting.fiscal_period_service import FiscalPeriodService


@pytest.mark.asyncio
async def test_close_period_persists_audit_in_same_transaction(db_session):
    organization_id = "org-period-audit"
    db_session.add(Organization(id=organization_id, name=organization_id))
    period = FiscalPeriod(
        id="period-audit",
        organization_id=organization_id,
        fiscal_year_id="year-audit",
        name="January 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )
    year = FiscalYear(
        id="year-audit",
        organization_id=organization_id,
        name="2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    debit_account = Account(
        id="period-audit-debit",
        organization_id=organization_id,
        code="AUD-D",
        name="Audit debit account",
        account_type="TEST",
    )
    credit_account = Account(
        id="period-audit-credit",
        organization_id=organization_id,
        code="AUD-C",
        name="Audit credit account",
        account_type="TEST",
    )
    entry = JournalEntry(
        id="period-audit-entry",
        organization_id=organization_id,
        fiscal_period_id=period.id,
        entry_date=date(2026, 1, 10),
        description="Posted entry",
        idempotency_key="period-audit-entry-key",
        idempotency_hash="period-audit-entry-hash",
        status=JournalEntryStatus.POSTED,
    )
    debit_line = JournalEntryLine(
        id="period-audit-line-debit",
        journal_entry_id=entry.id,
        line_number=1,
        account_id=debit_account.id,
        debit=Decimal("250.00"),
        credit=Decimal("0.00"),
    )
    credit_line = JournalEntryLine(
        id="period-audit-line-credit",
        journal_entry_id=entry.id,
        line_number=2,
        account_id=credit_account.id,
        debit=Decimal("0.00"),
        credit=Decimal("250.00"),
    )
    db_session.add_all(
        [
            year,
            period,
            debit_account,
            credit_account,
            entry,
            debit_line,
            credit_line,
            LedgerPosting(
                id="period-audit-posting-debit",
                organization_id=organization_id,
                fiscal_period_id=period.id,
                journal_entry_id=entry.id,
                journal_entry_line_id=debit_line.id,
                account_id=debit_account.id,
                posting_date=date(2026, 1, 10),
                line_number=1,
                debit=Decimal("250.00"),
                credit=Decimal("0.00"),
            ),
            LedgerPosting(
                id="period-audit-posting-credit",
                organization_id=organization_id,
                fiscal_period_id=period.id,
                journal_entry_id=entry.id,
                journal_entry_line_id=credit_line.id,
                account_id=credit_account.id,
                posting_date=date(2026, 1, 10),
                line_number=2,
                debit=Decimal("0.00"),
                credit=Decimal("250.00"),
            ),
        ]
    )
    await db_session.commit()

    closed = await FiscalPeriodService(db_session).close_period(organization_id, period.id, "closer-1")

    assert closed.status == FiscalPeriodStatus.CLOSED
    audit = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.organization_id == organization_id,
            AuditLog.action == "FISCAL_PERIOD_CLOSED",
            AuditLog.entity_type == "fiscal_period",
            AuditLog.entity_id == period.id,
        )
    )
    assert audit is not None
    assert audit.actor_id == "closer-1"
    assert audit.sequence_no == 1
    assert audit.previous_hash is None
    assert audit.record_hash


@pytest.mark.asyncio
async def test_failed_period_close_does_not_emit_audit_event(db_session):
    organization_id = "org-period-audit-fail"
    db_session.add(Organization(id=organization_id, name=organization_id))
    period = FiscalPeriod(
        id="period-audit-fail",
        organization_id=organization_id,
        fiscal_year_id="year-audit-fail",
        name="January 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )
    year = FiscalYear(
        id="year-audit-fail",
        organization_id=organization_id,
        name="2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    draft = JournalEntry(
        id="period-audit-fail-entry",
        organization_id=organization_id,
        fiscal_period_id=period.id,
        entry_date=date(2026, 1, 10),
        description="Draft entry blocks closure",
        idempotency_key="period-audit-fail-key",
        idempotency_hash="period-audit-fail-hash",
        status=JournalEntryStatus.DRAFT,
    )
    db_session.add_all([year, period, draft])
    await db_session.commit()

    with pytest.raises(Exception):
        await FiscalPeriodService(db_session).close_period(organization_id, period.id, "closer-1")

    audit_count = await db_session.scalar(
        select(AuditLog.id).where(
            AuditLog.organization_id == organization_id,
            AuditLog.action == "FISCAL_PERIOD_CLOSED",
            AuditLog.entity_id == period.id,
        )
    )
    assert audit_count is None
    assert period.status == FiscalPeriodStatus.OPEN
