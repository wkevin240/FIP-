from collections.abc import Iterable

from app.models.treasury.accounting import TreasuryAccountingPosting
from app.models.treasury.bank_accounting_rule import (
    BankAccountingRule,
    BankTransactionAccountingProposal,
)
from app.schemas.treasury.bank_accounting_rule import (
    BankAccountingRuleCreate,
    BankAccountingRuleUpdate,
)
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


class BankAccountingRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_resources(self, resources: Iterable[str]) -> None:
        """Serialize changes and decisions for the same tenant resources on PostgreSQL."""
        if self.session.bind.dialect.name != "postgresql":
            return
        for resource in sorted(set(resources)):
            await self.session.execute(
                text(
                    "SELECT pg_advisory_xact_lock("
                    "hashtext('fip-bank-accounting-rules'), hashtext(:resource))"
                ),
                {"resource": resource},
            )

    async def get_rule(
        self, organization_id: str, rule_id: str, for_update: bool = False
    ) -> BankAccountingRule | None:
        statement = select(BankAccountingRule).where(
            BankAccountingRule.organization_id == organization_id,
            BankAccountingRule.id == rule_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def list_rules(self, organization_id: str) -> list[BankAccountingRule]:
        result = await self.session.scalars(
            select(BankAccountingRule)
            .where(BankAccountingRule.organization_id == organization_id)
            .order_by(
                BankAccountingRule.priority,
                BankAccountingRule.name,
                BankAccountingRule.id,
            )
        )
        return list(result)

    async def list_active_rules(self, organization_id: str) -> list[BankAccountingRule]:
        result = await self.session.scalars(
            select(BankAccountingRule)
            .where(
                BankAccountingRule.organization_id == organization_id,
                BankAccountingRule.is_active.is_(True),
            )
            .order_by(
                BankAccountingRule.priority,
                BankAccountingRule.name,
                BankAccountingRule.id,
            )
        )
        return list(result)

    async def create_rule(
        self, organization_id: str, data: BankAccountingRuleCreate
    ) -> BankAccountingRule:
        rule = BankAccountingRule(
            organization_id=organization_id,
            **data.model_dump(),
        )
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def update_rule(
        self, rule: BankAccountingRule, data: BankAccountingRuleUpdate
    ) -> BankAccountingRule:
        for field, value in data.model_dump().items():
            setattr(rule, field, value)
        await self.session.flush()
        return rule

    async def get_proposal(
        self, organization_id: str, proposal_id: str, for_update: bool = False
    ) -> BankTransactionAccountingProposal | None:
        statement = select(BankTransactionAccountingProposal).where(
            BankTransactionAccountingProposal.organization_id == organization_id,
            BankTransactionAccountingProposal.id == proposal_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def get_proposal_by_snapshot(
        self, organization_id: str, transaction_id: str, snapshot_hash: str
    ) -> BankTransactionAccountingProposal | None:
        return await self.session.scalar(
            select(BankTransactionAccountingProposal).where(
                BankTransactionAccountingProposal.organization_id == organization_id,
                BankTransactionAccountingProposal.bank_transaction_id == transaction_id,
                BankTransactionAccountingProposal.rule_snapshot_hash == snapshot_hash,
            )
        )

    async def get_proposal_by_decision_key(
        self, organization_id: str, idempotency_key: str
    ) -> BankTransactionAccountingProposal | None:
        return await self.session.scalar(
            select(BankTransactionAccountingProposal).where(
                BankTransactionAccountingProposal.organization_id == organization_id,
                BankTransactionAccountingProposal.decision_idempotency_key
                == idempotency_key,
            )
        )

    async def create_proposal(
        self, proposal: BankTransactionAccountingProposal
    ) -> BankTransactionAccountingProposal:
        self.session.add(proposal)
        await self.session.flush()
        return proposal

    async def get_posting(
        self, organization_id: str, transaction_id: str
    ) -> TreasuryAccountingPosting | None:
        return await self.session.scalar(
            select(TreasuryAccountingPosting).where(
                TreasuryAccountingPosting.organization_id == organization_id,
                TreasuryAccountingPosting.source_id == transaction_id,
                TreasuryAccountingPosting.source_module == "TREASURY",
                TreasuryAccountingPosting.source_type == "BANK_TRANSACTION",
            )
        )
