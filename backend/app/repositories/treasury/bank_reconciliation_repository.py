from app.models.accounting.bank_reconciliation import BankReconciliation
from app.models.accounting.bank_transaction import BankTransaction
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TreasuryBankReconciliationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_ledger_account(
        self,
        organization_id: str,
        ledger_account_id: str,
        offset: int,
        limit: int,
    ) -> list[BankReconciliation]:
        result = await self.session.scalars(
            select(BankReconciliation)
            .join(
                BankTransaction,
                BankTransaction.id == BankReconciliation.bank_transaction_id,
            )
            .where(
                BankReconciliation.organization_id == organization_id,
                BankTransaction.bank_account_id == ledger_account_id,
            )
            .order_by(BankReconciliation.reconciled_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result)
