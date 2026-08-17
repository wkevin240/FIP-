from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256

from app.domain.accounting.reconciliation.bank_rules import BankReconciliationRules
from app.models.accounting.account import Account
from app.models.accounting.bank_reconciliation import BankReconciliation
from app.models.accounting.bank_reconciliation_allocation import (
    BankReconciliationAllocation,
    BankReconciliationBatch,
)
from app.models.accounting.bank_transaction import BankTransaction
from app.repositories.accounting.bank_reconciliation_repository import (
    BankReconciliationRepository,
)
from app.schemas.accounting.bank_reconciliation import (
    BankTransactionCreate,
    ReconcileBankTransactionsRequest,
    ReconciliationCandidate,
)
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class BankReconciliationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = BankReconciliationRepository(session)
        self.audit = AuditService(session)

    async def create_transaction(
        self, organization_id: str, data: BankTransactionCreate
    ) -> BankTransaction:
        await self._validate_bank_account(organization_id, data.bank_account_id)
        if await self.repository.get_transaction_by_external_id(
            organization_id, data.bank_account_id, data.external_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bank transaction external ID already exists",
            )

        try:
            transaction = await self.repository.create_transaction(
                organization_id, data
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bank transaction external ID already exists",
            ) from exc
        await self.session.refresh(transaction)
        return transaction

    async def list_transactions(
        self, organization_id: str, bank_account_id: str, reconciled: bool | None
    ) -> list[BankTransaction]:
        await self._validate_bank_account(organization_id, bank_account_id)
        return await self.repository.list_transactions(
            organization_id, bank_account_id, reconciled
        )

    async def candidate_entries(
        self,
        organization_id: str,
        transaction_id: str,
        date_window_days: int = 7,
    ) -> list[ReconciliationCandidate]:
        if date_window_days < 0 or date_window_days > 90:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Date window must be between 0 and 90 days",
            )
        transaction = await self._get_transaction(organization_id, transaction_id)
        if transaction.reconciled_at is not None:
            return []

        entries = await self.repository.candidate_entries(
            organization_id,
            transaction.bank_account_id,
            transaction.transaction_date - timedelta(days=date_window_days),
            transaction.transaction_date + timedelta(days=date_window_days),
        )
        candidates = []
        for entry in entries:
            ledger_amount = self._ledger_amount(
                entry.lines, transaction.bank_account_id
            )
            if ledger_amount == 0:
                continue
            amount_difference = abs(transaction.amount - ledger_amount)
            if amount_difference != 0:
                continue
            if transaction.amount * ledger_amount < 0:
                continue
            candidates.append(
                ReconciliationCandidate(
                    journal_entry_id=entry.id,
                    entry_number=entry.entry_number,
                    entry_date=entry.entry_date,
                    description=entry.description,
                    ledger_amount=ledger_amount,
                    amount_difference=amount_difference,
                    date_difference_days=abs(
                        (entry.entry_date - transaction.transaction_date).days
                    ),
                )
            )
        return sorted(
            candidates,
            key=lambda candidate: (
                candidate.date_difference_days,
                candidate.entry_date,
            ),
        )

    async def reconcile(
        self,
        organization_id: str,
        transaction_id: str,
        journal_entry_id: str,
        user_id: str,
        match_method: str = "MANUAL",
    ) -> BankReconciliation:
        try:
            transaction = await self.repository.get_transaction(
                organization_id, transaction_id, for_update=True
            )
            if transaction is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bank transaction not found",
                )
            if transaction.reconciled_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Bank transaction is already reconciled",
                )
            if await self.repository.has_allocations_for_transaction(
                organization_id, transaction.id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Bank transaction already has partial allocations",
                )

            entry = await self.repository.get_entry(
                organization_id, journal_entry_id, for_update=True
            )
            if entry is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Posted journal entry not found",
                )
            existing_entry_match = await self.session.scalar(
                select(BankReconciliation.id).where(
                    BankReconciliation.journal_entry_id == entry.id
                )
            )
            if existing_entry_match is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Journal entry is already reconciled",
                )
            if await self.repository.has_allocations_for_entry(
                organization_id, entry.id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Journal entry already has partial allocations",
                )

            ledger_amount = self._ledger_amount(
                entry.lines, transaction.bank_account_id
            )
            try:
                BankReconciliationRules.validate_match(
                    transaction.amount, ledger_amount
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
                ) from exc

            transaction.reconciled_at = datetime.now(timezone.utc)
            reconciliation = BankReconciliation(
                organization_id=organization_id,
                bank_transaction_id=transaction.id,
                journal_entry_id=entry.id,
                reconciled_by_user_id=user_id,
                reconciled_at=datetime.now(timezone.utc),
                matched_amount=abs(Decimal(transaction.amount)),
                match_method=match_method,
            )
            await self.repository.create_reconciliation(reconciliation)
            await self.audit.record(
                organization_id=organization_id,
                actor_user_id=user_id,
                action="BANK_TRANSACTION_RECONCILED",
                resource_type="BankReconciliation",
                resource_id=reconciliation.id,
                new_value={
                    "bank_transaction_id": transaction.id,
                    "journal_entry_id": entry.id,
                    "matched_amount": str(reconciliation.matched_amount),
                    "match_method": match_method,
                },
            )
            await self.session.commit()
        except HTTPException:
            await self.session.rollback()
            raise
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bank transaction or journal entry is already reconciled",
            ) from exc

        await self.session.refresh(reconciliation)
        return reconciliation

    async def reconcile_allocations(
        self,
        organization_id: str,
        actor_user_id: str,
        idempotency_key: str,
        data: ReconcileBankTransactionsRequest,
    ) -> BankReconciliationBatch:
        request_fingerprint = self._allocation_request_fingerprint(data)
        existing = await self.repository.get_batch_by_key(
            organization_id, idempotency_key
        )
        if existing is not None:
            self._ensure_matching_idempotency_request(existing, request_fingerprint)
            return existing
        try:
            await self._validate_bank_account(organization_id, data.bank_account_id)
            transaction_ids = {
                allocation.bank_transaction_id for allocation in data.allocations
            }
            entry_ids = {allocation.journal_entry_id for allocation in data.allocations}
            await self.repository.lock_allocation_resources(
                {f"key:{idempotency_key}"}
                | {
                    f"transaction:{transaction_id}"
                    for transaction_id in transaction_ids
                }
                | {f"entry:{entry_id}" for entry_id in entry_ids}
            )
            transactions = await self.repository.get_transactions_for_allocation(
                organization_id, transaction_ids
            )
            entries = await self.repository.get_entries_for_allocation(
                organization_id, entry_ids
            )
            existing = await self.repository.get_batch_by_key(
                organization_id, idempotency_key
            )
            if existing is not None:
                self._ensure_matching_idempotency_request(existing, request_fingerprint)
                return existing
            if len(transactions) != len(transaction_ids):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Bank transaction not found",
                )
            if len(entries) != len(entry_ids):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Posted journal entry not found",
                )

            transaction_allocated = {
                transaction.id: await self.repository.allocation_total_for_transaction(
                    organization_id, transaction.id
                )
                for transaction in transactions.values()
            }
            entry_allocated = {
                entry.id: await self.repository.allocation_total_for_entry(
                    organization_id, data.bank_account_id, entry.id
                )
                for entry in entries.values()
            }
            requested_transaction_totals = dict(transaction_allocated)
            requested_entry_totals = dict(entry_allocated)
            allocation_rows: list[BankReconciliationAllocation] = []
            now = datetime.now(timezone.utc)
            for allocation in data.allocations:
                transaction = transactions[allocation.bank_transaction_id]
                entry = entries[allocation.journal_entry_id]
                if transaction.bank_account_id != data.bank_account_id:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="All bank transactions must belong to the batch bank account",
                    )
                if transaction.reconciliation is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Bank transaction is already reconciled",
                    )
                if entry.bank_reconciliation is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Journal entry is already reconciled",
                    )
                ledger_amount = self._ledger_amount(entry.lines, data.bank_account_id)
                amount = Decimal(allocation.matched_amount)
                BankReconciliationRules.validate_allocation(
                    Decimal(transaction.amount),
                    requested_transaction_totals[transaction.id],
                    ledger_amount,
                    requested_entry_totals[entry.id],
                    amount,
                )
                requested_transaction_totals[transaction.id] += amount
                requested_entry_totals[entry.id] += amount
                allocation_rows.append(
                    BankReconciliationAllocation(
                        organization_id=organization_id,
                        bank_transaction_id=transaction.id,
                        journal_entry_id=entry.id,
                        matched_amount=amount,
                    )
                )

            batch = await self.repository.create_batch(
                BankReconciliationBatch(
                    organization_id=organization_id,
                    bank_account_id=data.bank_account_id,
                    reconciled_by_user_id=actor_user_id,
                    reconciled_at=now,
                    idempotency_key=idempotency_key,
                    request_fingerprint=request_fingerprint,
                    match_method="MANUAL_PARTIAL_GROUPED",
                    allocated_total=sum(
                        (item.matched_amount for item in allocation_rows),
                        Decimal("0.00"),
                    ),
                )
            )
            for allocation in allocation_rows:
                allocation.batch_id = batch.id
            await self.repository.create_allocations(allocation_rows)
            for transaction_id, total in requested_transaction_totals.items():
                transaction = transactions[transaction_id]
                if total == abs(Decimal(transaction.amount)):
                    transaction.reconciled_at = now
            await self.audit.record(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="BANK_RECONCILIATION_BATCH_APPLIED",
                resource_type="BankReconciliationBatch",
                resource_id=batch.id,
                new_value={
                    "bank_account_id": data.bank_account_id,
                    "allocated_total": str(batch.allocated_total),
                    "allocation_count": len(allocation_rows),
                },
                transaction_id=batch.id,
                request_id=idempotency_key,
            )
            await self.session.commit()
        except ValueError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
        except HTTPException:
            await self.session.rollback()
            raise
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.repository.get_batch_by_key(
                organization_id, idempotency_key
            )
            if existing is not None:
                self._ensure_matching_idempotency_request(existing, request_fingerprint)
                return existing
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bank reconciliation allocations changed concurrently",
            ) from exc
        return await self.repository.get_batch(organization_id, batch.id)

    @staticmethod
    def _allocation_request_fingerprint(
        data: ReconcileBankTransactionsRequest,
    ) -> str:
        allocation_parts = sorted(
            (
                allocation.bank_transaction_id,
                allocation.journal_entry_id,
                format(Decimal(allocation.matched_amount), ".2f"),
            )
            for allocation in data.allocations
        )
        payload = "|".join(
            [data.bank_account_id] + [":".join(part) for part in allocation_parts]
        )
        return sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _ensure_matching_idempotency_request(
        batch: BankReconciliationBatch, request_fingerprint: str
    ) -> None:
        if batch.request_fingerprint != request_fingerprint:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key was already used with a different request",
            )

    async def _get_transaction(
        self, organization_id: str, transaction_id: str
    ) -> BankTransaction:
        transaction = await self.repository.get_transaction(
            organization_id, transaction_id
        )
        if transaction is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bank transaction not found",
            )
        return transaction

    async def _validate_bank_account(
        self, organization_id: str, account_id: str
    ) -> None:
        account = await self.session.scalar(
            select(Account).where(
                Account.organization_id == organization_id,
                Account.id == account_id,
                Account.is_active.is_(True),
            )
        )
        if account is None or account.account_type != "ASSET":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Active asset account required for bank transaction",
            )

    @staticmethod
    def _ledger_amount(lines, bank_account_id: str) -> Decimal:
        return sum(
            (
                Decimal(line.debit) - Decimal(line.credit)
                for line in lines
                if line.account_id == bank_account_id
            ),
            Decimal("0.00"),
        )
