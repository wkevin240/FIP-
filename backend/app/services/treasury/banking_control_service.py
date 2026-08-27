from datetime import datetime, timezone

from app.models.accounting.bank_reconciliation import BankReconciliation
from app.models.treasury.bank_accounting_rule import BankTransactionAccountingProposal
from app.models.treasury.bank_statement_import import (
    BankStatementImport,
    BankStatementImportLine,
)
from app.models.treasury.banking_control import (
    BankingControlException,
    BankStatementClosure,
)
from app.schemas.treasury.bank_accounting_rule import BankAccountingProposalPreview
from app.services.audit.audit_service import AuditService
from app.services.treasury.bank_rules_accounting_service import (
    BankRulesAccountingService,
)
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

UNRESOLVED = {
    "NO_MATCH",
    "AMBIGUOUS",
    "PENDING",
    "REJECTED",
    "INVALID_RULE",
    "POSTED_UNRECONCILED",
}


class BankingControlService:
    """Operational supervision for imported statements without a parallel ledger."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)
        self.rules = BankRulesAccountingService(session)

    async def refresh_import(
        self, organization_id: str, actor_user_id: str, statement_import_id: str
    ) -> dict[str, int | str]:
        statement = await self.session.scalar(
            select(BankStatementImport)
            .options(
                selectinload(BankStatementImport.lines).selectinload(
                    BankStatementImportLine.bank_transaction
                )
            )
            .where(
                BankStatementImport.organization_id == organization_id,
                BankStatementImport.id == statement_import_id,
            )
        )
        if statement is None:
            raise HTTPException(
                status_code=404, detail="Bank statement import not found"
            )
        now = datetime.now(timezone.utc)
        counts: dict[str, int] = {
            "RECONCILED": 0,
            "NO_MATCH": 0,
            "AMBIGUOUS": 0,
            "PENDING": 0,
            "REJECTED": 0,
            "INVALID_RULE": 0,
            "POSTED_UNRECONCILED": 0,
        }
        for line in statement.lines:
            if line.status != "IMPORTED" or line.bank_transaction is None:
                continue
            current = await self._derive_status(
                organization_id, actor_user_id, line.bank_transaction.id
            )
            counts[current] = counts.get(current, 0) + 1
            exception = await self.session.scalar(
                select(BankingControlException)
                .where(
                    BankingControlException.organization_id == organization_id,
                    BankingControlException.bank_transaction_id
                    == line.bank_transaction.id,
                )
                .with_for_update()
            )
            if exception is None:
                exception = BankingControlException(
                    organization_id=organization_id,
                    bank_transaction_id=line.bank_transaction.id,
                    statement_import_id=statement.id,
                    status=current,
                    reason=self._reason(current),
                    last_seen_at=now,
                    resolved_at=now if current == "RECONCILED" else None,
                    resolved_by_user_id=actor_user_id
                    if current == "RECONCILED"
                    else None,
                )
                self.session.add(exception)
            else:
                exception.statement_import_id = statement.id
                exception.status = current
                exception.reason = self._reason(current)
                exception.last_seen_at = now
                if current == "RECONCILED":
                    exception.resolved_at = now
                    exception.resolved_by_user_id = actor_user_id
                else:
                    exception.resolved_at = None
                    exception.resolved_by_user_id = None
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="BANKING_CONTROL_REFRESHED",
            resource_type="BankStatementImport",
            resource_id=statement.id,
            new_value=counts,
        )
        await self.session.commit()
        return {
            "statement_import_id": statement.id,
            "total_imported": sum(counts.values()),
            **counts,
        }

    async def list_exceptions(
        self,
        organization_id: str,
        *,
        statement_import_id: str | None = None,
        exception_status: str | None = None,
        unresolved_only: bool = True,
        offset: int = 0,
        limit: int = 100,
    ) -> list[BankingControlException]:
        if offset < 0:
            raise ValueError("offset must be non-negative")
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        query = select(BankingControlException).where(
            BankingControlException.organization_id == organization_id
        )
        if statement_import_id:
            query = query.where(
                BankingControlException.statement_import_id == statement_import_id
            )
        if exception_status:
            query = query.where(BankingControlException.status == exception_status)
        if unresolved_only:
            query = query.where(BankingControlException.status.in_(UNRESOLVED))
        return list(
            await self.session.scalars(
                query.order_by(
                    BankingControlException.last_seen_at.desc(),
                    BankingControlException.id.asc(),
                )
                .offset(offset)
                .limit(limit)
            )
        )

    async def close_import(
        self, organization_id: str, actor_user_id: str, statement_import_id: str
    ) -> BankStatementClosure:
        existing = await self.session.scalar(
            select(BankStatementClosure).where(
                BankStatementClosure.organization_id == organization_id,
                BankStatementClosure.statement_import_id == statement_import_id,
            )
        )
        if existing is not None:
            return existing
        await self.refresh_import(organization_id, actor_user_id, statement_import_id)
        imported_count = await self.session.scalar(
            select(func.count(BankStatementImportLine.id)).where(
                BankStatementImportLine.organization_id == organization_id,
                BankStatementImportLine.statement_import_id == statement_import_id,
                BankStatementImportLine.status == "IMPORTED",
            )
        )
        reconciled_count = await self.session.scalar(
            select(func.count(BankingControlException.id)).where(
                BankingControlException.organization_id == organization_id,
                BankingControlException.statement_import_id == statement_import_id,
                BankingControlException.status == "RECONCILED",
            )
        )
        unresolved_count = int(imported_count or 0) - int(reconciled_count or 0)
        if unresolved_count != 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Statement cannot be closed with {unresolved_count} unresolved transaction(s)",
            )
        closure = BankStatementClosure(
            organization_id=organization_id,
            statement_import_id=statement_import_id,
            closed_by_user_id=actor_user_id,
            closed_at=datetime.now(timezone.utc),
            imported_count=int(imported_count or 0),
            reconciled_count=int(reconciled_count or 0),
            unresolved_count=0,
        )
        self.session.add(closure)
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="BANK_STATEMENT_CLOSED",
            resource_type="BankStatementImport",
            resource_id=statement_import_id,
            new_value={
                "imported_count": closure.imported_count,
                "reconciled_count": closure.reconciled_count,
            },
        )
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            existing = await self.session.scalar(
                select(BankStatementClosure).where(
                    BankStatementClosure.organization_id == organization_id,
                    BankStatementClosure.statement_import_id == statement_import_id,
                )
            )
            if existing is not None:
                return existing
            raise
        return closure

    async def _derive_status(
        self, organization_id: str, actor_user_id: str, transaction_id: str
    ) -> str:
        reconciled = await self.session.scalar(
            select(BankReconciliation).where(
                BankReconciliation.organization_id == organization_id,
                BankReconciliation.bank_transaction_id == transaction_id,
            )
        )
        if reconciled is not None:
            return "RECONCILED"
        proposal = await self.session.scalar(
            select(BankTransactionAccountingProposal)
            .where(
                BankTransactionAccountingProposal.organization_id == organization_id,
                BankTransactionAccountingProposal.bank_transaction_id == transaction_id,
            )
            .order_by(BankTransactionAccountingProposal.created_at.desc())
        )
        if proposal is not None:
            if proposal.status == "VALIDATED":
                return "POSTED_UNRECONCILED"
            if proposal.status == "REJECTED":
                return "REJECTED"
            return "PENDING"
        preview: BankAccountingProposalPreview = await self.rules.evaluate_transaction(
            organization_id, actor_user_id, transaction_id
        )
        return {
            "NO_MATCH": "NO_MATCH",
            "AMBIGUOUS": "AMBIGUOUS",
            "INVALID_RULE_CONFIGURATION": "INVALID_RULE",
            "EXISTING_PROPOSAL": "PENDING",
            "ALREADY_POSTED": "POSTED_UNRECONCILED",
        }.get(preview.outcome, "NO_MATCH")

    @staticmethod
    def _reason(value: str) -> str:
        return {
            "NO_MATCH": "No active recognition rule matches this transaction",
            "AMBIGUOUS": "Multiple rules have the best priority",
            "PENDING": "Accounting proposal awaits explicit decision",
            "REJECTED": "Accounting proposal was explicitly rejected",
            "INVALID_RULE": "Matched rule configuration is invalid",
            "POSTED_UNRECONCILED": "Accounting entry exists but bank reconciliation is pending",
            "RECONCILED": "Transaction is reconciled with a posted journal entry",
        }[value]
