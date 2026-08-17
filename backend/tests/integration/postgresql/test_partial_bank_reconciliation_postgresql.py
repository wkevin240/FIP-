import asyncio
import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.models.accounting.bank_reconciliation_allocation import (
    BankReconciliationAllocation,
    BankReconciliationBatch,
)
from app.models.audit.audit_event import AuditEvent
from app.schemas.accounting.bank_reconciliation import (
    BankTransactionCreate,
    ReconcileBankTransactionsRequest,
    ReconciliationAllocationCreate,
)
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.services.accounting.bank_reconciliation_service import (
    BankReconciliationService,
)
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from tests.integration.accounting.test_bank_reconciliation_service import (
    _create_posted_entry,
    _create_reconciliation_context,
)

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


@pytest.mark.asyncio
async def test_postgresql_partial_reconciliation_is_tenant_scoped(
    postgres_session: AsyncSession,
) -> None:
    (
        organization,
        user,
        period,
        accounts,
        journal_id,
    ) = await _create_reconciliation_context(postgres_session)
    organization_id = organization.id
    user_id = user.id
    bank_account_id = accounts["bank"].id
    entry_id = await _create_posted_entry(
        postgres_session,
        organization_id,
        period.id,
        journal_id,
        "PG-PARTIAL-100",
        date(2026, 1, 21),
        [
            JournalEntryLineCreate(account_id=bank_account_id, debit=Decimal("100.00")),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("100.00")
            ),
        ],
    )
    service = BankReconciliationService(postgres_session)
    transaction = await service.create_transaction(
        organization_id,
        BankTransactionCreate(
            bank_account_id=bank_account_id,
            transaction_date=date(2026, 1, 21),
            amount=Decimal("100.00"),
            description="PostgreSQL partial reconciliation",
            external_id=f"PG-PARTIAL-{uuid4().hex[:12]}",
        ),
    )
    transaction_id = transaction.id
    batch = await service.reconcile_allocations(
        organization_id,
        user_id,
        "postgres-partial-tenant-001",
        ReconcileBankTransactionsRequest(
            bank_account_id=bank_account_id,
            allocations=[
                ReconciliationAllocationCreate(
                    bank_transaction_id=transaction_id,
                    journal_entry_id=entry_id,
                    matched_amount=Decimal("100.00"),
                )
            ],
        ),
    )

    other_organization, _, _, _, _ = await _create_reconciliation_context(
        postgres_session
    )
    with pytest.raises(IntegrityError):
        await postgres_session.execute(
            text(
                """
                INSERT INTO public.bank_reconciliation_allocations (
                    id, created_at, updated_at, organization_id, batch_id,
                    bank_transaction_id, journal_entry_id, matched_amount
                ) VALUES (
                    :id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :organization_id,
                    :batch_id, :bank_transaction_id, :journal_entry_id, 1.00
                )
                """
            ),
            {
                "id": uuid4().hex,
                "organization_id": other_organization.id,
                "batch_id": batch.id,
                "bank_transaction_id": transaction_id,
                "journal_entry_id": entry_id,
            },
        )
        await postgres_session.commit()
    await postgres_session.rollback()


@pytest.mark.asyncio
async def test_postgresql_concurrent_partial_reconciliation_is_idempotent_and_audited_once(
    postgres_session: AsyncSession,
) -> None:
    (
        organization,
        user,
        period,
        accounts,
        journal_id,
    ) = await _create_reconciliation_context(postgres_session)
    organization_id = organization.id
    user_id = user.id
    bank_account_id = accounts["bank"].id
    entry_id = await _create_posted_entry(
        postgres_session,
        organization_id,
        period.id,
        journal_id,
        "PG-CONCURRENT-PARTIAL-100",
        date(2026, 1, 22),
        [
            JournalEntryLineCreate(account_id=bank_account_id, debit=Decimal("100.00")),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("100.00")
            ),
        ],
    )
    transaction = await BankReconciliationService(postgres_session).create_transaction(
        organization_id,
        BankTransactionCreate(
            bank_account_id=bank_account_id,
            transaction_date=date(2026, 1, 22),
            amount=Decimal("100.00"),
            description="Concurrent partial reconciliation",
            external_id=f"PG-CONCURRENT-{uuid4().hex[:12]}",
        ),
    )
    transaction_id = transaction.id
    request = ReconcileBankTransactionsRequest(
        bank_account_id=bank_account_id,
        allocations=[
            ReconciliationAllocationCreate(
                bank_transaction_id=transaction_id,
                journal_entry_id=entry_id,
                matched_amount=Decimal("100.00"),
            )
        ],
    )
    engine = create_async_engine(POSTGRES_TEST_DATABASE_URL, echo=False)

    async def allocate_once() -> str:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            batch = await BankReconciliationService(session).reconcile_allocations(
                organization_id,
                user_id,
                "postgres-concurrent-partial-001",
                request,
            )
            assert batch is not None
            return batch.id

    try:
        first_id, second_id = await asyncio.gather(allocate_once(), allocate_once())
    finally:
        await engine.dispose()

    assert first_id == second_id
    assert (
        await postgres_session.scalar(
            select(func.count(BankReconciliationBatch.id)).where(
                BankReconciliationBatch.organization_id == organization_id,
                BankReconciliationBatch.idempotency_key
                == "postgres-concurrent-partial-001",
            )
        )
        == 1
    )
    assert (
        await postgres_session.scalar(
            select(func.count(BankReconciliationAllocation.id)).where(
                BankReconciliationAllocation.organization_id == organization_id,
                BankReconciliationAllocation.bank_transaction_id == transaction_id,
            )
        )
        == 1
    )
    assert (
        await postgres_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.action == "BANK_RECONCILIATION_BATCH_APPLIED",
            )
        )
        == 1
    )
