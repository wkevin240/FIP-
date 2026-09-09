from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting.account import Account
from app.models.accounting.ledger_posting import LedgerPosting


class LedgerService:
    """Financial read model built only from immutable ledger postings."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def account_balance(self, organization_id: str, account_id: str) -> Decimal:
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(LedgerPosting.debit), 0)
                - func.coalesce(func.sum(LedgerPosting.credit), 0)
            ).where(
                LedgerPosting.organization_id == organization_id,
                LedgerPosting.account_id == account_id,
            )
        )
        return Decimal(str(result.scalar_one()))

    async def trial_balance(self, organization_id: str) -> list[dict[str, object]]:
        result = await self.db.execute(
            select(
                Account.id,
                Account.code,
                Account.name,
                func.coalesce(func.sum(LedgerPosting.debit), 0).label("debit"),
                func.coalesce(func.sum(LedgerPosting.credit), 0).label("credit"),
            )
            .join(LedgerPosting, LedgerPosting.account_id == Account.id)
            .where(
                Account.organization_id == organization_id,
                LedgerPosting.organization_id == organization_id,
            )
            .group_by(Account.id, Account.code, Account.name)
            .order_by(Account.code)
        )
        return [
            {
                "account_id": row.id,
                "code": row.code,
                "name": row.name,
                "debit": Decimal(str(row.debit)),
                "credit": Decimal(str(row.credit)),
                "balance": Decimal(str(row.debit)) - Decimal(str(row.credit)),
            }
            for row in result
        ]
