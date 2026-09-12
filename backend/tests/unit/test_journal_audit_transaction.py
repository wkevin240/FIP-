from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.models import Account, FiscalPeriod, Organization
from app.models.audit.audit_log import AuditLog
from app.models.accounting.journal_entry import JournalEntry
from app.schemas.accounting.journal_entry import JournalEntryCreate, JournalEntryLineCreate
from app.services.accounting.journal_entry_service import JournalEntryService


@pytest.mark.asyncio
async def test_journal_creation_rolls_back_when_audit_append_fails(db_session):
    organization_id = "org-audit-rollback"
    period_id = "period-audit-rollback"
    debit_account_id = "account-audit-rollback-debit"
    credit_account_id = "account-audit-rollback-credit"

    db_session.add_all(
        [
            Organization(id=organization_id, name=organization_id),
            FiscalPeriod(
                id=period_id,
                organization_id=organization_id,
                fiscal_year_id="year-audit-rollback",
                name="January 2026",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
            ),
            Account(
                id=debit_account_id,
                organization_id=organization_id,
                code="AUD-RB-D",
                name="Audit rollback debit",
                account_type="EXPENSE",
            ),
            Account(
                id=credit_account_id,
                organization_id=organization_id,
                code="AUD-RB-C",
                name="Audit rollback credit",
                account_type="LIABILITY",
            ),
        ]
    )
    await db_session.commit()

    service = JournalEntryService(db_session)
    service.audit_repository.append = AsyncMock(side_effect=RuntimeError("audit persistence unavailable"))
    data = JournalEntryCreate(
        fiscal_period_id=period_id,
        entry_date=date(2026, 1, 15),
        description="Transaction boundary proof",
        idempotency_key="audit-rollback-create-1",
        lines=[
            JournalEntryLineCreate(account_id=debit_account_id, debit=Decimal("10.00")),
            JournalEntryLineCreate(account_id=credit_account_id, credit=Decimal("10.00")),
        ],
    )

    with pytest.raises(RuntimeError, match="audit persistence unavailable"):
        await service.create(organization_id, "actor-audit-rollback", data)

    journal_count = await db_session.scalar(
        select(func.count(JournalEntry.id)).where(
            JournalEntry.organization_id == organization_id,
            JournalEntry.idempotency_key == data.idempotency_key,
        )
    )
    audit_count = await db_session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.organization_id == organization_id,
            AuditLog.action == "JOURNAL_ENTRY_CREATED",
        )
    )

    assert journal_count == 0
    assert audit_count == 0
    service.audit_repository.append.assert_awaited_once()
