from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.ledger_posting import LedgerPosting


class LedgerService:
    """Read-only financial reporting over immutable posted ledger movements."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _validate_period(self, organization_id: str, fiscal_period_id: str | None) -> FiscalPeriod | None:
        if fiscal_period_id is None:
            return None
        period = await self.db.scalar(
            select(FiscalPeriod).where(
                FiscalPeriod.id == fiscal_period_id,
                FiscalPeriod.organization_id == organization_id,
            )
        )
        if period is None:
            raise HTTPException(status_code=404, detail="Fiscal period not found")
        return period

    @staticmethod
    def _validate_dates(start_date: date | None, end_date: date | None) -> None:
        if start_date is not None and end_date is not None and start_date > end_date:
            raise HTTPException(status_code=422, detail="start_date must be on or before end_date")

    @staticmethod
    def _posting_filters(
        organization_id: str,
        fiscal_period_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[object]:
        filters: list[object] = [LedgerPosting.organization_id == organization_id]
        if fiscal_period_id is not None:
            filters.append(LedgerPosting.fiscal_period_id == fiscal_period_id)
        if start_date is not None:
            filters.append(LedgerPosting.posting_date >= start_date)
        if end_date is not None:
            filters.append(LedgerPosting.posting_date <= end_date)
        return filters

    async def account_balance(
        self,
        organization_id: str,
        account_id: str,
        *,
        fiscal_period_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> Decimal:
        await self._validate_period(organization_id, fiscal_period_id)
        self._validate_dates(start_date, end_date)
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
                *self._posting_filters(organization_id, fiscal_period_id, start_date, end_date),
                LedgerPosting.account_id == account_id,
            )
        )
        return Decimal(str(result.scalar_one()))

    async def trial_balance(
        self,
        organization_id: str,
        *,
        fiscal_period_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, object]]:
        await self._validate_period(organization_id, fiscal_period_id)
        self._validate_dates(start_date, end_date)
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
                *self._posting_filters(organization_id, fiscal_period_id, start_date, end_date),
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

    async def general_ledger(
        self,
        organization_id: str,
        account_id: str,
        *,
        fiscal_period_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, object]]:
        await self._validate_period(organization_id, fiscal_period_id)
        self._validate_dates(start_date, end_date)
        account_exists = await self.db.scalar(
            select(Account.id).where(Account.id == account_id, Account.organization_id == organization_id)
        )
        if account_exists is None:
            raise HTTPException(status_code=404, detail="Account not found")
        result = await self.db.execute(
            select(LedgerPosting)
            .where(
                *self._posting_filters(organization_id, fiscal_period_id, start_date, end_date),
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
                "account_id": posting.account_id,
                "journal_entry_id": posting.journal_entry_id,
                "journal_entry_line_id": posting.journal_entry_line_id,
                "fiscal_period_id": posting.fiscal_period_id,
                "posting_date": posting.posting_date,
                "line_number": posting.line_number,
                "description": posting.description,
                "debit": Decimal(str(posting.debit)),
                "credit": Decimal(str(posting.credit)),
                "balance": running,
            })
        return rows
