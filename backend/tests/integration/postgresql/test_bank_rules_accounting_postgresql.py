import asyncio
import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.models.accounting.journal_entry import JournalEntry
from app.models.audit.audit_event import AuditEvent
from app.models.treasury.accounting import TreasuryAccountingPosting
from app.models.treasury.bank_accounting_rule import (
    BankTransactionAccountingProposal,
)
from app.models.user import User
from app.schemas.treasury.bank_accounting_rule import (
    BankAccountingProposalDecision,
    BankAccountingRuleCreate,
)
from app.schemas.treasury.transaction import TreasuryBankTransactionCreate
from app.services.treasury.bank_rules_accounting_service import (
    BankRulesAccountingService,
)
from app.services.treasury.transaction_service import TreasuryTransactionService
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from tests.integration.treasury.test_treasury_accounting_service import _context

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


async def _actor(session: AsyncSession) -> User:
    actor = User(
        email=f"bank-rules-{uuid4().hex[:12]}@test.local",
        full_name="Bank rules test actor",
        hashed_password="not-used-in-integration-test",
        is_active=True,
        is_superuser=False,
    )
    session.add(actor)
    await session.commit()
    return actor


async def _transaction(
    session: AsyncSession,
    organization_id: str,
    bank_profile_id: str,
    *,
    amount: Decimal = Decimal("125.50"),
    description: str = "Customer collection",
):
    return await TreasuryTransactionService(session).create_transaction(
        organization_id,
        TreasuryBankTransactionCreate(
            treasury_bank_account_id=bank_profile_id,
            transaction_date=date(2026, 2, 15),
            amount=amount,
            description=description,
            external_id=f"PG-RULE-{uuid4().hex}",
        ),
    )


async def _rule(
    service: BankRulesAccountingService,
    organization_id: str,
    counterpart_account_id: str,
    *,
    name: str,
):
    return await service.create_rule(
        organization_id,
        "rules-tester",
        BankAccountingRuleCreate(
            name=name,
            counterpart_account_id=counterpart_account_id,
            priority=1,
            category="OPERATING",
            description_pattern="Customer collection",
            direction="CREDIT",
        ),
    )


@pytest.mark.asyncio
async def test_postgresql_rules_and_proposals_enforce_tenant_fks_and_decision_state(
    postgres_session: AsyncSession,
) -> None:
    organization, _, bank_profile, receivable, _, _ = await _context(postgres_session)
    actor = await _actor(postgres_session)
    service = BankRulesAccountingService(postgres_session)
    rule = await _rule(
        service, organization.id, receivable.id, name=f"pg-rule-{uuid4().hex}"
    )
    transaction = await _transaction(postgres_session, organization.id, bank_profile.id)
    preview = await service.evaluate_transaction(
        organization.id, actor.id, transaction.id
    )
    assert preview.proposal is not None
    proposal = preview.proposal
    organization_id = organization.id
    transaction_id = transaction.id
    rule_id = rule.id
    counterpart_account_id = receivable.id
    proposal_id = proposal.id
    actor_id = actor.id
    other_organization, _, _, _, _, _ = await _context(postgres_session)
    other_organization_id = other_organization.id

    with pytest.raises(IntegrityError):
        await postgres_session.execute(
            text(
                """
                INSERT INTO public.bank_transaction_accounting_proposals (
                    id, created_at, updated_at, organization_id, bank_transaction_id,
                    rule_id, counterpart_account_id, rule_name, rule_snapshot_hash, status
                ) VALUES (
                    :id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :organization_id,
                    :bank_transaction_id, :rule_id, :counterpart_account_id,
                    'cross-tenant', :snapshot_hash, 'PENDING'
                )
                """
            ),
            {
                "id": uuid4().hex,
                "organization_id": other_organization_id,
                "bank_transaction_id": transaction_id,
                "rule_id": rule_id,
                "counterpart_account_id": counterpart_account_id,
                "snapshot_hash": "0" * 64,
            },
        )
        await postgres_session.commit()
    await postgres_session.rollback()

    with pytest.raises(IntegrityError):
        await postgres_session.execute(
            text(
                """
                UPDATE public.bank_transaction_accounting_proposals
                SET status = 'VALIDATED', decided_by_user_id = :actor_id,
                    decided_at = CURRENT_TIMESTAMP,
                    decision_idempotency_key = 'invalid-direct-state'
                WHERE organization_id = :organization_id AND id = :proposal_id
                """
            ),
            {
                "actor_id": actor_id,
                "organization_id": organization_id,
                "proposal_id": proposal_id,
            },
        )
        await postgres_session.commit()
    await postgres_session.rollback()
    persisted = await service.get_proposal(organization_id, proposal_id)
    assert persisted.status == "PENDING"
    assert persisted.journal_entry_id is None


@pytest.mark.asyncio
async def test_postgresql_concurrent_generation_produces_one_proposal_and_audit(
    postgres_session: AsyncSession,
) -> None:
    organization, _, bank_profile, receivable, _, _ = await _context(postgres_session)
    actor = await _actor(postgres_session)
    await _rule(
        BankRulesAccountingService(postgres_session),
        organization.id,
        receivable.id,
        name=f"pg-generation-{uuid4().hex}",
    )
    transaction = await _transaction(postgres_session, organization.id, bank_profile.id)
    organization_id = organization.id
    transaction_id = transaction.id
    actor_id = actor.id
    engine = create_async_engine(POSTGRES_TEST_DATABASE_URL, echo=False)

    async def generate_once() -> str:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            preview = await BankRulesAccountingService(session).evaluate_transaction(
                organization_id, actor_id, transaction_id
            )
            assert preview.proposal is not None
            return preview.proposal.id

    try:
        first_id, second_id = await asyncio.gather(generate_once(), generate_once())
    finally:
        await engine.dispose()

    assert first_id == second_id
    assert (
        await postgres_session.scalar(
            select(func.count(BankTransactionAccountingProposal.id)).where(
                BankTransactionAccountingProposal.organization_id == organization_id,
                BankTransactionAccountingProposal.bank_transaction_id == transaction_id,
            )
        )
        == 1
    )
    assert (
        await postgres_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.action == "BANK_ACCOUNTING_PROPOSAL_GENERATED",
                AuditEvent.resource_id == first_id,
            )
        )
        == 1
    )


@pytest.mark.asyncio
async def test_postgresql_concurrent_validation_is_idempotent_with_one_posting(
    postgres_session: AsyncSession,
) -> None:
    organization, _, bank_profile, receivable, _, _ = await _context(postgres_session)
    actor = await _actor(postgres_session)
    service = BankRulesAccountingService(postgres_session)
    await _rule(
        service,
        organization.id,
        receivable.id,
        name=f"pg-validation-{uuid4().hex}",
    )
    transaction = await _transaction(postgres_session, organization.id, bank_profile.id)
    preview = await service.evaluate_transaction(
        organization.id, actor.id, transaction.id
    )
    assert preview.proposal is not None
    organization_id = organization.id
    proposal_id = preview.proposal.id
    transaction_id = transaction.id
    actor_id = actor.id
    engine = create_async_engine(POSTGRES_TEST_DATABASE_URL, echo=False)

    async def validate_once() -> tuple[str, str]:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            proposal = await BankRulesAccountingService(session).validate_proposal(
                organization_id,
                actor_id,
                proposal_id,
                BankAccountingProposalDecision(
                    idempotency_key="pg-concurrent-validation-001"
                ),
            )
            assert proposal.journal_entry_id is not None
            return proposal.id, proposal.journal_entry_id

    try:
        first, second = await asyncio.gather(validate_once(), validate_once())
    finally:
        await engine.dispose()

    assert first == second
    assert (
        await postgres_session.scalar(
            select(func.count(TreasuryAccountingPosting.id)).where(
                TreasuryAccountingPosting.organization_id == organization_id,
                TreasuryAccountingPosting.source_id == transaction_id,
            )
        )
        == 1
    )
    assert (
        await postgres_session.scalar(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.organization_id == organization_id,
                JournalEntry.id == first[1],
            )
        )
        == 1
    )
    assert (
        await postgres_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.action == "BANK_ACCOUNTING_PROPOSAL_VALIDATED",
                AuditEvent.resource_id == proposal_id,
            )
        )
        == 1
    )
