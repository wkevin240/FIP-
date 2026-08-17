import asyncio
import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.core.enums.invoicing import PaymentMethod
from app.models.accounting.account import Account
from app.models.audit.audit_event import AuditEvent
from app.models.invoicing.settlement_accounting import (
    CreditNoteAccountingPosting,
    PaymentAccountingPosting,
)
from app.schemas.invoicing.credit_note import CreditNoteCreate
from app.schemas.invoicing.payment import PaymentCreate
from app.schemas.invoicing.settlement_accounting import PaymentPostingCreate
from app.services.invoicing.credit_note_service import CreditNoteService
from app.services.invoicing.payment_service import PaymentService
from app.services.invoicing.settlement_accounting_service import (
    SettlementAccountingService,
)
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from tests.integration.postgresql.test_invoice_accounting_postgresql import (
    _create_invoice_context,
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


async def _create_settlement_account(
    session: AsyncSession, organization_id: str, suffix: str
) -> Account:
    account = Account(
        organization_id=organization_id,
        code=f"512{suffix[:8]}",
        name="PostgreSQL settlement account",
        account_type="ASSET",
        level=1,
        path=f"/512{suffix[:8]}/",
    )
    session.add(account)
    await session.commit()
    return account


@pytest.mark.asyncio
async def test_postgresql_enforces_settlement_source_uniqueness_and_tenant_foreign_keys(
    postgres_session: AsyncSession,
) -> None:
    organization_id, invoice_id, _ = await _create_invoice_context(postgres_session)
    credit = await CreditNoteService(postgres_session).create_credit_note(
        organization_id,
        CreditNoteCreate(
            invoice_id=invoice_id,
            credit_note_number=f"CN-PG-{uuid4().hex[:12]}",
            credit_date=date(2026, 2, 20),
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("18.00"),
            amount=Decimal("118.00"),
            reason="PostgreSQL settlement integrity",
        ),
    )
    posting = await SettlementAccountingService(postgres_session).post_credit_note(
        organization_id,
        "postgres-settlement-tester",
        credit.id,
        "postgres-credit-source-001",
    )
    assert posting is not None
    credit_id = credit.id
    journal_entry_id = posting.journal_entry_id

    with pytest.raises(IntegrityError):
        await postgres_session.execute(
            text(
                """
                INSERT INTO public.credit_note_accounting_postings (
                    id, created_at, updated_at, organization_id, source_module,
                    source_type, source_id, journal_entry_id, idempotency_key, status
                ) VALUES (
                    :id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :organization_id,
                    'INVOICING', 'CREDIT_NOTE', :source_id, :journal_entry_id,
                    'postgres-credit-source-duplicate', 'POSTED'
                )
                """
            ),
            {
                "id": uuid4().hex,
                "organization_id": organization_id,
                "source_id": credit_id,
                "journal_entry_id": journal_entry_id,
            },
        )
        await postgres_session.commit()
    await postgres_session.rollback()

    other_organization_id, _, _ = await _create_invoice_context(postgres_session)
    with pytest.raises(IntegrityError):
        await postgres_session.execute(
            text(
                """
                INSERT INTO public.credit_note_accounting_postings (
                    id, created_at, updated_at, organization_id, source_module,
                    source_type, source_id, journal_entry_id, idempotency_key, status
                ) VALUES (
                    :id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :organization_id,
                    'INVOICING', 'CREDIT_NOTE', :source_id, :journal_entry_id,
                    'postgres-credit-cross-tenant', 'POSTED'
                )
                """
            ),
            {
                "id": uuid4().hex,
                "organization_id": other_organization_id,
                "source_id": credit_id,
                "journal_entry_id": journal_entry_id,
            },
        )
        await postgres_session.commit()
    await postgres_session.rollback()


@pytest.mark.asyncio
async def test_postgresql_concurrent_payment_posting_is_serialized_and_audited_once(
    postgres_session: AsyncSession,
) -> None:
    organization_id, invoice_id, _ = await _create_invoice_context(postgres_session)
    settlement_account = await _create_settlement_account(
        postgres_session, organization_id, uuid4().hex
    )
    payment = await PaymentService(postgres_session).create_payment(
        organization_id,
        PaymentCreate(
            invoice_id=invoice_id,
            payment_date=date(2026, 2, 20),
            amount=Decimal("50.00"),
            method=PaymentMethod.BANK_TRANSFER,
            external_reference=f"PAY-PG-{uuid4().hex[:12]}",
        ),
    )
    payment_id = payment.id
    settlement_account_id = settlement_account.id
    engine = create_async_engine(POSTGRES_TEST_DATABASE_URL, echo=False)

    async def post_once(key: str) -> str:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            posting = await SettlementAccountingService(session).post_payment(
                organization_id,
                "postgres-concurrent-tester",
                payment_id,
                key,
                PaymentPostingCreate(settlement_account_id=settlement_account_id),
            )
            assert posting is not None
            return posting.id

    try:
        first_id, second_id = await asyncio.gather(
            post_once("postgres-payment-concurrent-001"),
            post_once("postgres-payment-concurrent-002"),
        )
    finally:
        await engine.dispose()

    assert first_id == second_id
    assert (
        await postgres_session.scalar(
            select(func.count(PaymentAccountingPosting.id)).where(
                PaymentAccountingPosting.organization_id == organization_id,
                PaymentAccountingPosting.source_id == payment_id,
            )
        )
        == 1
    )
    assert (
        await postgres_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.action == "PAYMENT_POSTED_TO_ACCOUNTING",
                AuditEvent.resource_id == payment_id,
            )
        )
        == 1
    )
    assert (
        await postgres_session.scalar(
            select(func.count(CreditNoteAccountingPosting.id)).where(
                CreditNoteAccountingPosting.organization_id == organization_id
            )
        )
        == 0
    )
