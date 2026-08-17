import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal

from app.models.accounting.account import Account
from app.models.accounting.bank_transaction import BankTransaction
from app.models.treasury.bank_accounting_rule import (
    BankAccountingRule,
    BankTransactionAccountingProposal,
)
from app.repositories.accounting.bank_reconciliation_repository import (
    BankReconciliationRepository,
)
from app.repositories.treasury.bank_accounting_rule_repository import (
    BankAccountingRuleRepository,
)
from app.schemas.treasury.accounting import TreasuryTransactionPostingCreate
from app.schemas.treasury.bank_accounting_rule import (
    BankAccountingProposalDecision,
    BankAccountingProposalPreview,
    BankAccountingProposalRejection,
    BankAccountingRuleCreate,
    BankAccountingRuleUpdate,
)
from app.services.audit.audit_service import AuditService
from app.services.treasury.treasury_accounting_service import TreasuryAccountingService
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class BankRulesAccountingService:
    """Controlled bank-recognition workflow with no automatic accounting effect."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = BankAccountingRuleRepository(session)
        self.reconciliation = BankReconciliationRepository(session)
        self.treasury_accounting = TreasuryAccountingService(session)
        self.audit = AuditService(session)

    async def create_rule(
        self,
        organization_id: str,
        actor_user_id: str,
        data: BankAccountingRuleCreate,
    ) -> BankAccountingRule:
        self._compile_criteria(data.description_pattern, data.reference_pattern)
        await self.repository.lock_resources({f"config:{organization_id}"})
        await self._validate_counterpart_account(
            organization_id, data.counterpart_account_id
        )
        try:
            rule = await self.repository.create_rule(organization_id, data)
            await self.audit.record(
                organization_id,
                actor_user_id,
                "BANK_ACCOUNTING_RULE_CREATED",
                "BankAccountingRule",
                rule.id,
                new_value=self._rule_audit_value(rule),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bank accounting rule conflicts with an existing rule",
            ) from exc
        return rule

    async def update_rule(
        self,
        organization_id: str,
        actor_user_id: str,
        rule_id: str,
        data: BankAccountingRuleUpdate,
    ) -> BankAccountingRule:
        self._compile_criteria(data.description_pattern, data.reference_pattern)
        await self.repository.lock_resources({f"config:{organization_id}"})
        rule = await self.repository.get_rule(organization_id, rule_id, for_update=True)
        if rule is None:
            raise HTTPException(
                status_code=404, detail="Bank accounting rule not found"
            )
        await self._validate_counterpart_account(
            organization_id, data.counterpart_account_id
        )
        old_value = self._rule_audit_value(rule)
        try:
            rule = await self.repository.update_rule(rule, data)
            await self.audit.record(
                organization_id,
                actor_user_id,
                "BANK_ACCOUNTING_RULE_UPDATED",
                "BankAccountingRule",
                rule.id,
                old_value=old_value,
                new_value=self._rule_audit_value(rule),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bank accounting rule conflicts with an existing rule",
            ) from exc
        return rule

    async def list_rules(self, organization_id: str) -> list[BankAccountingRule]:
        return await self.repository.list_rules(organization_id)

    async def get_proposal(
        self, organization_id: str, proposal_id: str
    ) -> BankTransactionAccountingProposal:
        proposal = await self.repository.get_proposal(organization_id, proposal_id)
        if proposal is None:
            raise HTTPException(
                status_code=404, detail="Bank accounting proposal not found"
            )
        return proposal

    async def evaluate_transaction(
        self,
        organization_id: str,
        actor_user_id: str,
        transaction_id: str,
    ) -> BankAccountingProposalPreview:
        """Generate or return one proposal, never an Accounting journal entry.

        A sole matching rule at the best priority is eligible. No matching rule and
        ties are returned as explicit outcomes; choosing a lower-priority rule in a
        tie would silently invent accounting intent.
        """
        await self.repository.lock_resources(
            {
                f"config:{organization_id}",
                f"transaction:{organization_id}:{transaction_id}",
            }
        )
        transaction = await self.reconciliation.get_transaction(
            organization_id, transaction_id, for_update=True
        )
        if transaction is None:
            raise HTTPException(status_code=404, detail="Bank transaction not found")
        if await self.repository.get_posting(organization_id, transaction.id):
            return BankAccountingProposalPreview(
                bank_transaction_id=transaction.id,
                outcome="ALREADY_POSTED",
            )

        matches = [
            rule
            for rule in await self.repository.list_active_rules(organization_id)
            if self._matches(rule, transaction)
        ]
        if not matches:
            return BankAccountingProposalPreview(
                bank_transaction_id=transaction.id,
                outcome="NO_MATCH",
            )

        best_priority = matches[0].priority
        best_matches = [rule for rule in matches if rule.priority == best_priority]
        if len(best_matches) > 1:
            return BankAccountingProposalPreview(
                bank_transaction_id=transaction.id,
                outcome="AMBIGUOUS",
                matching_rule_ids=[rule.id for rule in best_matches],
            )

        rule = best_matches[0]
        if rule.counterpart_account_id == transaction.bank_account_id:
            return BankAccountingProposalPreview(
                bank_transaction_id=transaction.id,
                outcome="INVALID_RULE_CONFIGURATION",
                matching_rule_ids=[rule.id],
            )
        await self._validate_counterpart_account(
            organization_id, rule.counterpart_account_id
        )
        snapshot_hash = self._snapshot_hash(rule, transaction)
        existing = await self.repository.get_proposal_by_snapshot(
            organization_id, transaction.id, snapshot_hash
        )
        if existing is not None:
            return BankAccountingProposalPreview(
                bank_transaction_id=transaction.id,
                outcome="EXISTING_PROPOSAL",
                proposal=existing,
                matching_rule_ids=[rule.id],
            )

        proposal = BankTransactionAccountingProposal(
            organization_id=organization_id,
            bank_transaction_id=transaction.id,
            rule_id=rule.id,
            counterpart_account_id=rule.counterpart_account_id,
            rule_name=rule.name,
            category=rule.category,
            rule_snapshot_hash=snapshot_hash,
            status="PENDING",
        )
        try:
            proposal = await self.repository.create_proposal(proposal)
            await self.audit.record(
                organization_id,
                actor_user_id,
                "BANK_ACCOUNTING_PROPOSAL_GENERATED",
                "BankTransactionAccountingProposal",
                proposal.id,
                new_value={
                    "bank_transaction_id": proposal.bank_transaction_id,
                    "rule_id": proposal.rule_id,
                    "counterpart_account_id": proposal.counterpart_account_id,
                    "category": proposal.category,
                    "status": proposal.status,
                },
                transaction_id=proposal.bank_transaction_id,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.repository.get_proposal_by_snapshot(
                organization_id, transaction.id, snapshot_hash
            )
            if existing is not None:
                return BankAccountingProposalPreview(
                    bank_transaction_id=transaction.id,
                    outcome="EXISTING_PROPOSAL",
                    proposal=existing,
                    matching_rule_ids=[rule.id],
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bank accounting proposal conflicts with an existing proposal",
            ) from exc
        return BankAccountingProposalPreview(
            bank_transaction_id=transaction.id,
            outcome="PROPOSED",
            proposal=proposal,
            matching_rule_ids=[rule.id],
        )

    async def validate_proposal(
        self,
        organization_id: str,
        actor_user_id: str,
        proposal_id: str,
        data: BankAccountingProposalDecision,
    ) -> BankTransactionAccountingProposal:
        await self.repository.lock_resources(
            {
                f"proposal:{organization_id}:{proposal_id}",
                f"decision:{organization_id}:{data.idempotency_key}",
            }
        )
        proposal = await self.repository.get_proposal(
            organization_id, proposal_id, for_update=True
        )
        if proposal is None:
            raise HTTPException(
                status_code=404, detail="Bank accounting proposal not found"
            )
        existing_key = await self.repository.get_proposal_by_decision_key(
            organization_id, data.idempotency_key
        )
        if existing_key is not None and existing_key.id != proposal.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key was already used for another proposal decision",
            )
        if proposal.status == "VALIDATED":
            if proposal.decision_idempotency_key == data.idempotency_key:
                return proposal
            raise HTTPException(status_code=409, detail="Proposal is already validated")
        if proposal.status == "REJECTED":
            raise HTTPException(status_code=409, detail="Proposal is already rejected")

        await self.repository.lock_resources(
            {f"transaction:{organization_id}:{proposal.bank_transaction_id}"}
        )
        transaction = await self.reconciliation.get_transaction(
            organization_id, proposal.bank_transaction_id, for_update=True
        )
        if transaction is None:
            raise HTTPException(
                status_code=409, detail="Source bank transaction is unavailable"
            )
        existing_posting = await self.repository.get_posting(
            organization_id, transaction.id
        )
        try:
            if existing_posting is not None:
                if (
                    existing_posting.counterpart_account_id
                    != proposal.counterpart_account_id
                ):
                    raise HTTPException(
                        status_code=409,
                        detail="Transaction was already posted with a different counterpart account",
                    )
                posting = existing_posting
            else:
                posting = await self.treasury_accounting.post_transaction(
                    organization_id,
                    actor_user_id,
                    transaction.id,
                    TreasuryTransactionPostingCreate(
                        counterpart_account_id=proposal.counterpart_account_id
                    ),
                    commit=False,
                )
            proposal.status = "VALIDATED"
            proposal.journal_entry_id = posting.journal_entry_id
            proposal.decision_idempotency_key = data.idempotency_key
            proposal.decided_by_user_id = actor_user_id
            proposal.decided_at = datetime.now(timezone.utc)
            proposal.rejection_reason = None
            await self.session.flush()
            await self.audit.record(
                organization_id,
                actor_user_id,
                "BANK_ACCOUNTING_PROPOSAL_VALIDATED",
                "BankTransactionAccountingProposal",
                proposal.id,
                new_value={
                    "bank_transaction_id": proposal.bank_transaction_id,
                    "journal_entry_id": proposal.journal_entry_id,
                    "status": proposal.status,
                },
                transaction_id=proposal.journal_entry_id,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.repository.get_proposal_by_decision_key(
                organization_id, data.idempotency_key
            )
            if existing is not None and existing.id == proposal_id:
                return existing
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bank accounting proposal validation conflicts with another decision",
            ) from exc
        return await self.get_proposal(organization_id, proposal_id)

    async def reject_proposal(
        self,
        organization_id: str,
        actor_user_id: str,
        proposal_id: str,
        data: BankAccountingProposalRejection,
    ) -> BankTransactionAccountingProposal:
        await self.repository.lock_resources(
            {
                f"proposal:{organization_id}:{proposal_id}",
                f"decision:{organization_id}:{data.idempotency_key}",
            }
        )
        proposal = await self.repository.get_proposal(
            organization_id, proposal_id, for_update=True
        )
        if proposal is None:
            raise HTTPException(
                status_code=404, detail="Bank accounting proposal not found"
            )
        existing_key = await self.repository.get_proposal_by_decision_key(
            organization_id, data.idempotency_key
        )
        if existing_key is not None and existing_key.id != proposal.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key was already used for another proposal decision",
            )
        if proposal.status == "REJECTED":
            if proposal.decision_idempotency_key == data.idempotency_key:
                return proposal
            raise HTTPException(status_code=409, detail="Proposal is already rejected")
        if proposal.status == "VALIDATED":
            raise HTTPException(
                status_code=409, detail="Validated proposal cannot be rejected"
            )

        try:
            proposal.status = "REJECTED"
            proposal.decision_idempotency_key = data.idempotency_key
            proposal.rejection_reason = data.rejection_reason
            proposal.decided_by_user_id = actor_user_id
            proposal.decided_at = datetime.now(timezone.utc)
            await self.session.flush()
            await self.audit.record(
                organization_id,
                actor_user_id,
                "BANK_ACCOUNTING_PROPOSAL_REJECTED",
                "BankTransactionAccountingProposal",
                proposal.id,
                new_value={
                    "bank_transaction_id": proposal.bank_transaction_id,
                    "status": proposal.status,
                    "rejection_reason": proposal.rejection_reason,
                },
                transaction_id=proposal.bank_transaction_id,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.repository.get_proposal_by_decision_key(
                organization_id, data.idempotency_key
            )
            if existing is not None and existing.id == proposal_id:
                return existing
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bank accounting proposal rejection conflicts with another decision",
            ) from exc
        return await self.get_proposal(organization_id, proposal_id)

    async def _validate_counterpart_account(
        self, organization_id: str, account_id: str
    ) -> Account:
        account = await self.session.scalar(
            select(Account).where(
                Account.organization_id == organization_id,
                Account.id == account_id,
                Account.is_active.is_(True),
            )
        )
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="An active counterpart account in the current organization is required",
            )
        return account

    def _compile_criteria(
        self, description_pattern: str | None, reference_pattern: str | None
    ) -> None:
        for pattern in (description_pattern, reference_pattern):
            if pattern is None:
                continue
            try:
                re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Invalid regular-expression matching criterion",
                ) from exc

    def _matches(self, rule: BankAccountingRule, transaction: BankTransaction) -> bool:
        amount = Decimal(transaction.amount)
        magnitude = abs(amount)
        if rule.direction == "CREDIT" and amount <= 0:
            return False
        if rule.direction == "DEBIT" and amount >= 0:
            return False
        if rule.amount_min is not None and magnitude < Decimal(rule.amount_min):
            return False
        if rule.amount_max is not None and magnitude > Decimal(rule.amount_max):
            return False
        if rule.description_pattern and not re.search(
            rule.description_pattern, transaction.description, re.IGNORECASE
        ):
            return False
        return not rule.reference_pattern or bool(
            re.search(
                rule.reference_pattern, transaction.reference or "", re.IGNORECASE
            )
        )

    def _snapshot_hash(
        self, rule: BankAccountingRule, transaction: BankTransaction
    ) -> str:
        payload = {
            "rule": {
                "id": rule.id,
                "name": rule.name,
                "description_pattern": rule.description_pattern,
                "reference_pattern": rule.reference_pattern,
                "amount_min": self._decimal_string(rule.amount_min),
                "amount_max": self._decimal_string(rule.amount_max),
                "direction": rule.direction,
                "counterpart_account_id": rule.counterpart_account_id,
                "priority": rule.priority,
                "category": rule.category,
                "is_active": rule.is_active,
            },
            "transaction": {
                "id": transaction.id,
                "bank_account_id": transaction.bank_account_id,
                "amount": self._decimal_string(transaction.amount),
                "transaction_date": transaction.transaction_date.isoformat(),
                "description": transaction.description,
                "reference": transaction.reference,
                "external_id": transaction.external_id,
            },
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _decimal_string(value: Decimal | None) -> str | None:
        return None if value is None else format(Decimal(value), ".2f")

    @staticmethod
    def _rule_audit_value(
        rule: BankAccountingRule,
    ) -> dict[str, str | int | bool | None]:
        return {
            "name": rule.name,
            "description_pattern": rule.description_pattern,
            "reference_pattern": rule.reference_pattern,
            "amount_min": BankRulesAccountingService._decimal_string(rule.amount_min),
            "amount_max": BankRulesAccountingService._decimal_string(rule.amount_max),
            "direction": rule.direction,
            "counterpart_account_id": rule.counterpart_account_id,
            "priority": rule.priority,
            "category": rule.category,
            "is_active": rule.is_active,
        }
