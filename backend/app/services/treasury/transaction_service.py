from app.models.accounting.bank_reconciliation import BankReconciliation
from app.models.accounting.bank_transaction import BankTransaction
from app.repositories.treasury.bank_account_repository import (
    TreasuryBankAccountRepository,
)
from app.repositories.treasury.bank_transaction_repository import (
    TreasuryBankTransactionRepository,
)
from app.schemas.accounting.bank_reconciliation import BankTransactionCreate
from app.schemas.treasury.transaction import TreasuryBankTransactionCreate
from app.services.accounting.bank_reconciliation_service import (
    BankReconciliationService,
)
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


class TreasuryTransactionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.bank_accounts = TreasuryBankAccountRepository(session)
        self.transactions = TreasuryBankTransactionRepository(session)
        self.reconciliation = BankReconciliationService(session)

    async def create_transaction(
        self, organization_id: str, data: TreasuryBankTransactionCreate
    ) -> BankTransaction:
        bank_account = await self._get_active_bank_account(
            organization_id, data.treasury_bank_account_id
        )
        return await self.reconciliation.create_transaction(
            organization_id,
            BankTransactionCreate(
                bank_account_id=bank_account.ledger_account_id,
                transaction_date=data.transaction_date,
                value_date=data.value_date,
                amount=data.amount,
                description=data.description,
                reference=data.reference,
                external_id=data.external_id,
            ),
        )

    async def list_transactions(
        self,
        organization_id: str,
        treasury_bank_account_id: str,
        reconciled: bool | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[BankTransaction]:
        bank_account = await self._get_bank_account(
            organization_id, treasury_bank_account_id
        )
        return await self.transactions.list(
            organization_id,
            bank_account.ledger_account_id,
            bank_account.opening_date,
            reconciled,
            max(offset, 0),
            min(max(limit, 1), 100),
        )

    async def candidate_entries(
        self,
        organization_id: str,
        treasury_bank_account_id: str,
        transaction_id: str,
        date_window_days: int = 7,
    ) -> list:
        await self._validate_transaction_profile(
            organization_id, treasury_bank_account_id, transaction_id
        )
        return await self.reconciliation.candidate_entries(
            organization_id, transaction_id, date_window_days
        )

    async def reconcile_transaction(
        self,
        organization_id: str,
        treasury_bank_account_id: str,
        transaction_id: str,
        journal_entry_id: str,
        user_id: str,
    ) -> BankReconciliation:
        await self._validate_transaction_profile(
            organization_id, treasury_bank_account_id, transaction_id
        )
        return await self.reconciliation.reconcile(
            organization_id, transaction_id, journal_entry_id, user_id
        )

    async def _validate_transaction_profile(
        self,
        organization_id: str,
        treasury_bank_account_id: str,
        transaction_id: str,
    ) -> None:
        bank_account = await self._get_bank_account(
            organization_id, treasury_bank_account_id
        )
        transaction = await self.transactions.get_by_id(organization_id, transaction_id)
        if (
            transaction is None
            or transaction.bank_account_id != bank_account.ledger_account_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bank transaction not found for treasury bank account",
            )

    async def _get_active_bank_account(
        self, organization_id: str, bank_account_id: str
    ):
        bank_account = await self._get_bank_account(organization_id, bank_account_id)
        if not bank_account.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Treasury bank account is inactive",
            )
        return bank_account

    async def _get_bank_account(self, organization_id: str, bank_account_id: str):
        bank_account = await self.bank_accounts.get_by_id(
            organization_id, bank_account_id
        )
        if bank_account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Treasury bank account not found",
            )
        return bank_account
