from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.core.enums.accounting import FiscalPeriodStatus
from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.journal_entry_line import JournalEntryLine
from app.models.audit.audit_event import AuditEvent
from app.models.treasury.accounting import TreasuryAccountingPosting
from app.models.treasury.bank_accounting_rule import (
    BankTransactionAccountingProposal,
)
from app.schemas.treasury.bank_accounting_rule import (
    BankAccountingProposalDecision,
    BankAccountingProposalRejection,
    BankAccountingRuleCreate,
)
from app.schemas.treasury.transaction import TreasuryBankTransactionCreate
from app.services.treasury.bank_rules_accounting_service import (
    BankRulesAccountingService,
)
from app.services.treasury.transaction_service import TreasuryTransactionService
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.integration.treasury.test_treasury_accounting_service import _context


async def _transaction(
    session: AsyncSession,
    organization_id: str,
    bank_profile_id: str,
    *,
    amount: Decimal,
    description: str,
    reference: str | None = None,
):
    return await TreasuryTransactionService(session).create_transaction(
        organization_id,
        TreasuryBankTransactionCreate(
            treasury_bank_account_id=bank_profile_id,
            transaction_date=date(2026, 2, 10),
            amount=amount,
            description=description,
            reference=reference,
            external_id=f"RULE-{uuid4().hex}",
        ),
    )


async def _rule(
    service: BankRulesAccountingService,
    organization_id: str,
    counterpart_account_id: str,
    *,
    name: str,
    priority: int,
    description_pattern: str | None = "Collection",
    reference_pattern: str | None = None,
    direction: str | None = "CREDIT",
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
):
    return await service.create_rule(
        organization_id,
        "rules-tester",
        BankAccountingRuleCreate(
            name=name,
            counterpart_account_id=counterpart_account_id,
            priority=priority,
            category="OPERATING",
            description_pattern=description_pattern,
            reference_pattern=reference_pattern,
            direction=direction,
            amount_min=amount_min,
            amount_max=amount_max,
        ),
    )


@pytest.mark.asyncio
async def test_bank_rule_proposal_uses_best_priority_without_posting_and_audits(
    db_session: AsyncSession,
) -> None:
    organization, _, bank_profile, receivable, expense, _ = await _context(db_session)
    service = BankRulesAccountingService(db_session)
    lower = await _rule(
        service,
        organization.id,
        expense.id,
        name=f"lower-{uuid4().hex}",
        priority=20,
    )
    preferred = await _rule(
        service,
        organization.id,
        receivable.id,
        name=f"preferred-{uuid4().hex}",
        priority=10,
    )
    transaction = await _transaction(
        db_session,
        organization.id,
        bank_profile.id,
        amount=Decimal("125.50"),
        description="Customer Collection February",
        reference="INV-2026-001",
    )

    preview = await service.evaluate_transaction(
        organization.id, "rules-tester", transaction.id
    )
    repeated = await service.evaluate_transaction(
        organization.id, "rules-tester", transaction.id
    )

    assert preview.outcome == "PROPOSED"
    assert preview.proposal is not None
    assert preview.proposal.status == "PENDING"
    assert preview.proposal.rule_id == preferred.id
    assert preview.proposal.counterpart_account_id == receivable.id
    assert preview.matching_rule_ids == [preferred.id]
    assert repeated.outcome == "EXISTING_PROPOSAL"
    assert repeated.proposal is not None and repeated.proposal.id == preview.proposal.id
    assert lower.id != preferred.id
    assert (
        await db_session.scalar(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.organization_id == organization.id
            )
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count(TreasuryAccountingPosting.id)).where(
                TreasuryAccountingPosting.organization_id == organization.id
            )
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization.id,
                AuditEvent.action == "BANK_ACCOUNTING_PROPOSAL_GENERATED",
                AuditEvent.resource_id == preview.proposal.id,
            )
        )
        == 1
    )


@pytest.mark.asyncio
async def test_bank_rule_tie_and_no_match_never_create_proposal(
    db_session: AsyncSession,
) -> None:
    organization, _, bank_profile, receivable, expense, _ = await _context(db_session)
    service = BankRulesAccountingService(db_session)
    first = await _rule(
        service,
        organization.id,
        receivable.id,
        name=f"tie-first-{uuid4().hex}",
        priority=5,
    )
    second = await _rule(
        service,
        organization.id,
        expense.id,
        name=f"tie-second-{uuid4().hex}",
        priority=5,
    )
    tied_transaction = await _transaction(
        db_session,
        organization.id,
        bank_profile.id,
        amount=Decimal("10.00"),
        description="Collection",
    )
    tied = await service.evaluate_transaction(
        organization.id, "rules-tester", tied_transaction.id
    )
    assert tied.outcome == "AMBIGUOUS"
    assert set(tied.matching_rule_ids) == {first.id, second.id}
    assert tied.proposal is None

    unmatched_transaction = await _transaction(
        db_session,
        organization.id,
        bank_profile.id,
        amount=Decimal("-10.00"),
        description="Bank fee",
    )
    unmatched = await service.evaluate_transaction(
        organization.id, "rules-tester", unmatched_transaction.id
    )
    assert unmatched.outcome == "NO_MATCH"
    assert unmatched.proposal is None
    assert (
        await db_session.scalar(
            select(func.count(BankTransactionAccountingProposal.id)).where(
                BankTransactionAccountingProposal.organization_id == organization.id
            )
        )
        == 0
    )


@pytest.mark.asyncio
async def test_validating_proposal_posts_balanced_entry_atomically_and_is_idempotent(
    db_session: AsyncSession,
) -> None:
    organization, _, bank_profile, receivable, _, _ = await _context(db_session)
    service = BankRulesAccountingService(db_session)
    await _rule(
        service,
        organization.id,
        receivable.id,
        name=f"collection-{uuid4().hex}",
        priority=1,
    )
    transaction = await _transaction(
        db_session,
        organization.id,
        bank_profile.id,
        amount=Decimal("125.50"),
        description="Collection",
    )
    preview = await service.evaluate_transaction(
        organization.id, "rules-tester", transaction.id
    )
    assert preview.proposal is not None

    first = await service.validate_proposal(
        organization.id,
        "validator",
        preview.proposal.id,
        BankAccountingProposalDecision(idempotency_key="validate-collection-001"),
    )
    repeated = await service.validate_proposal(
        organization.id,
        "validator",
        preview.proposal.id,
        BankAccountingProposalDecision(idempotency_key="validate-collection-001"),
    )

    assert first.status == "VALIDATED"
    assert first.journal_entry_id is not None
    assert repeated.id == first.id
    assert repeated.journal_entry_id == first.journal_entry_id
    entry = await db_session.get(JournalEntry, first.journal_entry_id)
    assert entry is not None and entry.status.value == "POSTED"
    lines = list(
        await db_session.scalars(
            select(JournalEntryLine).where(
                JournalEntryLine.organization_id == organization.id,
                JournalEntryLine.journal_entry_id == entry.id,
            )
        )
    )
    assert sum((Decimal(line.debit) for line in lines), Decimal("0.00")) == Decimal(
        "125.50"
    )
    assert sum((Decimal(line.credit) for line in lines), Decimal("0.00")) == Decimal(
        "125.50"
    )
    assert (
        await db_session.scalar(
            select(func.count(TreasuryAccountingPosting.id)).where(
                TreasuryAccountingPosting.organization_id == organization.id,
                TreasuryAccountingPosting.source_id == transaction.id,
            )
        )
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization.id,
                AuditEvent.action == "BANK_ACCOUNTING_PROPOSAL_VALIDATED",
                AuditEvent.resource_id == first.id,
            )
        )
        == 1
    )


@pytest.mark.asyncio
async def test_rejection_is_idempotent_and_prevents_posting(
    db_session: AsyncSession,
) -> None:
    organization, _, bank_profile, _, expense, _ = await _context(db_session)
    service = BankRulesAccountingService(db_session)
    await _rule(
        service,
        organization.id,
        expense.id,
        name=f"fee-{uuid4().hex}",
        priority=1,
        description_pattern="Bank fee",
        direction="DEBIT",
    )
    transaction = await _transaction(
        db_session,
        organization.id,
        bank_profile.id,
        amount=Decimal("-10.00"),
        description="Bank fee",
    )
    preview = await service.evaluate_transaction(
        organization.id, "rules-tester", transaction.id
    )
    assert preview.proposal is not None
    first = await service.reject_proposal(
        organization.id,
        "validator",
        preview.proposal.id,
        BankAccountingProposalRejection(
            idempotency_key="reject-fee-001",
            rejection_reason="External evidence pending",
        ),
    )
    repeated = await service.reject_proposal(
        organization.id,
        "validator",
        preview.proposal.id,
        BankAccountingProposalRejection(
            idempotency_key="reject-fee-001",
            rejection_reason="External evidence pending",
        ),
    )
    assert first.status == "REJECTED"
    assert first.journal_entry_id is None
    assert repeated.id == first.id
    with pytest.raises(HTTPException, match="already rejected") as validation:
        await service.validate_proposal(
            organization.id,
            "validator",
            first.id,
            BankAccountingProposalDecision(idempotency_key="validate-rejected-001"),
        )
    assert validation.value.status_code == 409
    assert (
        await db_session.scalar(
            select(func.count(TreasuryAccountingPosting.id)).where(
                TreasuryAccountingPosting.organization_id == organization.id,
                TreasuryAccountingPosting.source_id == transaction.id,
            )
        )
        == 0
    )


@pytest.mark.asyncio
async def test_validation_respects_closed_period_and_rolls_back_decision_audit(
    db_session: AsyncSession,
) -> None:
    organization, period, bank_profile, receivable, _, _ = await _context(db_session)
    service = BankRulesAccountingService(db_session)
    await _rule(
        service,
        organization.id,
        receivable.id,
        name=f"closed-period-{uuid4().hex}",
        priority=1,
    )
    transaction = await _transaction(
        db_session,
        organization.id,
        bank_profile.id,
        amount=Decimal("10.00"),
        description="Collection",
    )
    preview = await service.evaluate_transaction(
        organization.id, "rules-tester", transaction.id
    )
    assert preview.proposal is not None
    period.status = FiscalPeriodStatus.CLOSED
    await db_session.commit()

    with pytest.raises(HTTPException, match="Fiscal period is not open") as closed:
        await service.validate_proposal(
            organization.id,
            "validator",
            preview.proposal.id,
            BankAccountingProposalDecision(idempotency_key="closed-period-001"),
        )
    assert closed.value.status_code == 422
    proposal = await service.get_proposal(organization.id, preview.proposal.id)
    assert proposal.status == "PENDING"
    assert proposal.journal_entry_id is None
    assert (
        await db_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization.id,
                AuditEvent.action == "BANK_ACCOUNTING_PROPOSAL_VALIDATED",
                AuditEvent.resource_id == proposal.id,
            )
        )
        == 0
    )


@pytest.mark.asyncio
async def test_rules_and_proposals_are_isolated_by_organization(
    db_session: AsyncSession,
) -> None:
    organization, _, bank_profile, receivable, _, _ = await _context(db_session)
    other_organization, _, other_bank_profile, other_receivable, _, _ = await _context(
        db_session
    )
    service = BankRulesAccountingService(db_session)
    with pytest.raises(
        HTTPException, match="active counterpart account"
    ) as invalid_account:
        await _rule(
            service,
            organization.id,
            other_receivable.id,
            name=f"cross-account-{uuid4().hex}",
            priority=1,
        )
    assert invalid_account.value.status_code == 422

    await _rule(
        service,
        organization.id,
        receivable.id,
        name=f"tenant-one-{uuid4().hex}",
        priority=1,
    )
    transaction = await _transaction(
        db_session,
        organization.id,
        bank_profile.id,
        amount=Decimal("10.00"),
        description="Collection",
    )
    proposal = await service.evaluate_transaction(
        organization.id, "rules-tester", transaction.id
    )
    assert proposal.proposal is not None
    with pytest.raises(HTTPException, match="proposal not found") as cross_read:
        await service.get_proposal(other_organization.id, proposal.proposal.id)
    assert cross_read.value.status_code == 404
    other_transaction = await _transaction(
        db_session,
        other_organization.id,
        other_bank_profile.id,
        amount=Decimal("10.00"),
        description="Collection",
    )
    with pytest.raises(
        HTTPException, match="Bank transaction not found"
    ) as cross_evaluate:
        await service.evaluate_transaction(
            organization.id, "rules-tester", other_transaction.id
        )
    assert cross_evaluate.value.status_code == 404
