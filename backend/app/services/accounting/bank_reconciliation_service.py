from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.domain.accounting.reconciliation.bank_rules import BankReconciliationRules
from app.models.accounting.account import Account
from app.models.accounting.bank_reconciliation import BankReconciliation
from app.models.accounting.bank_transaction import BankTransaction
from app.repositories.accounting.bank_reconciliation_repository import (
    BankReconciliationRepository,
)
from app.schemas.accounting.bank_reconciliation import (
    BankTransactionCreate,
    ReconciliationCandidate,
)
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class BankReconciliationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = BankReconciliationRepository(session)

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
                match_method="MANUAL",
            )
            await self.repository.create_reconciliation(reconciliation)
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
