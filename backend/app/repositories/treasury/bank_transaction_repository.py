from datetime import date
from decimal import Decimal

from app.models.accounting.bank_transaction import BankTransaction
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class TreasuryBankTransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, organization_id: str, transaction_id: str
    ) -> BankTransaction | None:
        return await self.session.scalar(
            select(BankTransaction).where(
                BankTransaction.organization_id == organization_id,
                BankTransaction.id == transaction_id,
            )
        )

    async def list(
        self,
        organization_id: str,
        ledger_account_id: str,
        start_date: date | None,
        reconciled: bool | None,
        offset: int,
        limit: int,
    ) -> list[BankTransaction]:
        statement = select(BankTransaction).where(
            BankTransaction.organization_id == organization_id,
            BankTransaction.bank_account_id == ledger_account_id,
        )
        if start_date is not None:
            statement = statement.where(BankTransaction.transaction_date >= start_date)
        if reconciled is True:
            statement = statement.where(BankTransaction.reconciled_at.is_not(None))
        elif reconciled is False:
            statement = statement.where(BankTransaction.reconciled_at.is_(None))
        result = await self.session.scalars(
            statement.order_by(
                BankTransaction.transaction_date.desc(),
                BankTransaction.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        return list(result)

    async def totals(
        self, organization_id: str, ledger_account_id: str, start_date: date
    ) -> tuple[Decimal, Decimal, int]:
        filters = (
            BankTransaction.organization_id == organization_id,
            BankTransaction.bank_account_id == ledger_account_id,
            BankTransaction.transaction_date >= start_date,
        )
        result = await self.session.execute(
            select(
                func.coalesce(func.sum(BankTransaction.amount), 0).label("total"),
                func.coalesce(
                    func.sum(BankTransaction.amount).filter(
                        BankTransaction.reconciled_at.is_(None)
                    ),
                    0,
                ).label("unreconciled_total"),
                func.count(BankTransaction.id)
                .filter(BankTransaction.reconciled_at.is_(None))
                .label("unreconciled_count"),
            ).where(*filters)
        )
        total, unreconciled_total, unreconciled_count = result.one()
        return (
            Decimal(total),
            Decimal(unreconciled_total),
            int(unreconciled_count),
        )
