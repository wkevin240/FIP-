from app.models.accounting.bank_reconciliation import BankReconciliation
from app.services.treasury.transaction_service import TreasuryTransactionService
from sqlalchemy.ext.asyncio import AsyncSession


class TreasuryReconciliationService:
    def __init__(self, session: AsyncSession) -> None:
        self.transactions = TreasuryTransactionService(session)

    async def candidate_entries(
        self,
        organization_id: str,
        treasury_bank_account_id: str,
        transaction_id: str,
        date_window_days: int = 7,
    ) -> list:
        return await self.transactions.candidate_entries(
            organization_id,
            treasury_bank_account_id,
            transaction_id,
            date_window_days,
        )

    async def reconcile(
        self,
        organization_id: str,
        treasury_bank_account_id: str,
        transaction_id: str,
        journal_entry_id: str,
        user_id: str,
    ) -> BankReconciliation:
        return await self.transactions.reconcile_transaction(
            organization_id,
            treasury_bank_account_id,
            transaction_id,
            journal_entry_id,
            user_id,
        )
