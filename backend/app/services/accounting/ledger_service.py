from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting.account import Account
from app.models.accounting.ledger_posting import LedgerPosting


class LedgerService:
    """Read-only financial reporting over immutable posted ledger movements."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def account_balance(self, organization_id: str, account_id: str) -> Decimal:
        account_exists = await self.db.scalar(
            select(Account.id).where(Account.id == account_id, Account.organization_id == organization_id)
        )
        if account_exists is None:
            raise HTTPException(status_code=404, detail="Account not found")
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

    async def general_ledger(self, organization_id: str, account_id: str) -> list[dict[str, object]]:
        account_exists = await self.db.scalar(
            select(Account.id).where(Account.id == account_id, Account.organization_id == organization_id)
        )
        if account_exists is None:
            raise HTTPException(status_code=404, detail="Account not found")
        result = await self.db.execute(
            select(LedgerPosting)
            .where(
                LedgerPosting.organization_id == organization_id,
                LedgerPosting.account_id == account_id,
            )
            .order_by(LedgerPosting.posting_date, LedgerPosting.journal_entry_id, LedgerPosting.line_number)
        )
        running = Decimal("0.00")
        rows: list[dict[str, object]] = []
        for posting in result.scalars():
            running += Decimal(str(posting.debit)) - Decimal(str(posting.credit))
            rows.append({
                "id": posting.id,
                "journal_entry_id": posting.journal_entry_id,
                "posting_date": posting.posting_date,
                "line_number": posting.line_number,
                "description": posting.description,
                "debit": Decimal(str(posting.debit)),
                "credit": Decimal(str(posting.credit)),
                "balance": running,
            })
        return rows
