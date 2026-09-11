from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.calculation.accounting_balance_sheet import BalanceSheetFact
from app.domain.calculation.ledger_profitability import LedgerProfitabilityFact
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.journal_entry import JournalEntry, JournalEntryLine, JournalEntryStatus
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
    def _validate_dates_within_period(
        period: FiscalPeriod | None,
        start_date: date | None,
        end_date: date | None,
    ) -> None:
        if period is None:
            return
        if start_date is not None and start_date < period.start_date:
            raise HTTPException(status_code=422, detail="start_date must fall within the selected fiscal period")
        if end_date is not None and end_date > period.end_date:
            raise HTTPException(status_code=422, detail="end_date must fall within the selected fiscal period")

    @staticmethod
    def _opening_date(period: FiscalPeriod | None, start_date: date | None) -> date | None:
        if start_date is not None:
            return start_date
        if period is not None:
            return period.start_date
        return None

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

    @staticmethod
    def _journal_reconciliation_filters(
        organization_id: str,
        fiscal_period_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[object]:
        filters: list[object] = [
            JournalEntry.organization_id == organization_id,
            JournalEntry.status == JournalEntryStatus.POSTED,
        ]
        if fiscal_period_id is not None:
            filters.append(JournalEntry.fiscal_period_id == fiscal_period_id)
        if start_date is not None:
            filters.append(JournalEntry.entry_date >= start_date)
        if end_date is not None:
            filters.append(JournalEntry.entry_date <= end_date)
        return filters

    async def profitability_facts(
        self,
        organization_id: str,
        *,
        fiscal_period_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[LedgerProfitabilityFact]:
        period = await self._validate_period(organization_id, fiscal_period_id)
        self._validate_dates(start_date, end_date)
        self._validate_dates_within_period(period, start_date, end_date)
        result = await self.db.execute(
            select(LedgerPosting)
            .where(*self._posting_filters(organization_id, fiscal_period_id, start_date, end_date))
            .order_by(LedgerPosting.posting_date, LedgerPosting.journal_entry_id, LedgerPosting.line_number, LedgerPosting.id)
        )
        return [
            LedgerProfitabilityFact(
                posting_id=posting.id,
                account_id=posting.account_id,
                debit=Decimal(str(posting.debit)),
                credit=Decimal(str(posting.credit)),
            )
            for posting in result.scalars()
        ]

    async def balance_sheet_facts(
        self,
        organization_id: str,
        *,
        fiscal_period_id: str | None = None,
        end_date: date | None = None,
    ) -> list[BalanceSheetFact]:
        """Extract all tenant-scoped postings through the report date.

        Balance-sheet balances are cumulative by nature, so the adapter deliberately
        includes prior posted movements rather than treating the selected period as
        a movement-only statement.
        """
        period = await self._validate_period(organization_id, fiscal_period_id)
        if end_date is None and period is not None:
            end_date = period.end_date
        if end_date is not None and period is not None and end_date > period.end_date:
            raise HTTPException(status_code=422, detail="end_date must fall within the selected fiscal period")
        filters = [LedgerPosting.organization_id == organization_id]
        if end_date is not None:
            filters.append(LedgerPosting.posting_date <= end_date)
        result = await self.db.execute(
            select(LedgerPosting)
            .where(*filters)
            .order_by(LedgerPosting.posting_date, LedgerPosting.journal_entry_id, LedgerPosting.line_number, LedgerPosting.id)
        )
        return [
            BalanceSheetFact(
                posting_id=posting.id,
                account_id=posting.account_id,
                debit=Decimal(str(posting.debit)),
                credit=Decimal(str(posting.credit)),
            )
            for posting in result.scalars()
        ]

    async def account_balance(self, organization_id: str, account_id: str, *, fiscal_period_id: str | None = None, start_date: date | None = None, end_date: date | None = None) -> Decimal:
        period = await self._validate_period(organization_id, fiscal_period_id)
        self._validate_dates(start_date, end_date)
        self._validate_dates_within_period(period, start_date, end_date)
        account_exists = await self.db.scalar(select(Account.id).where(Account.id == account_id, Account.organization_id == organization_id))
        if account_exists is None:
            raise HTTPException(status_code=404, detail="Account not found")
        result = await self.db.execute(
            select(func.coalesce(func.sum(LedgerPosting.debit), 0) - func.coalesce(func.sum(LedgerPosting.credit), 0)).where(
                *self._posting_filters(organization_id, fiscal_period_id, start_date, end_date),
                LedgerPosting.account_id == account_id,
            )
        )
        return Decimal(str(result.scalar_one()))

    async def trial_balance(self, organization_id: str, *, fiscal_period_id: str | None = None, start_date: date | None = None, end_date: date | None = None) -> list[dict[str, object]]:
        period = await self._validate_period(organization_id, fiscal_period_id)
        self._validate_dates(start_date, end_date)
        self._validate_dates_within_period(period, start_date, end_date)
        result = await self.db.execute(
            select(Account.id, Account.code, Account.name, func.coalesce(func.sum(LedgerPosting.debit), 0).label("debit"), func.coalesce(func.sum(LedgerPosting.credit), 0).label("credit"))
            .join(LedgerPosting, LedgerPosting.account_id == Account.id)
            .where(Account.organization_id == organization_id, *self._posting_filters(organization_id, fiscal_period_id, start_date, end_date))
            .group_by(Account.id, Account.code, Account.name)
            .order_by(Account.code)
        )
        return [{"account_id": row.id, "code": row.code, "name": row.name, "debit": Decimal(str(row.debit)), "credit": Decimal(str(row.credit)), "balance": Decimal(str(row.debit)) - Decimal(str(row.credit))} for row in result]

    async def general_ledger(self, organization_id: str, account_id: str, *, fiscal_period_id: str | None = None, start_date: date | None = None, end_date: date | None = None) -> dict[str, object]:
        period = await self._validate_period(organization_id, fiscal_period_id)
        self._validate_dates(start_date, end_date)
        self._validate_dates_within_period(period, start_date, end_date)
        account_exists = await self.db.scalar(select(Account.id).where(Account.id == account_id, Account.organization_id == organization_id))
        if account_exists is None:
            raise HTTPException(status_code=404, detail="Account not found")
        filters = self._posting_filters(organization_id, fiscal_period_id, start_date, end_date)
        opening_balance = Decimal("0.00")
        opening_date = self._opening_date(period, start_date)
        if opening_date is not None:
            opening_result = await self.db.execute(select(func.coalesce(func.sum(LedgerPosting.debit), 0) - func.coalesce(func.sum(LedgerPosting.credit), 0)).where(LedgerPosting.organization_id == organization_id, LedgerPosting.account_id == account_id, LedgerPosting.posting_date < opening_date))
            opening_balance = Decimal(str(opening_result.scalar_one()))
        result = await self.db.execute(select(LedgerPosting).where(*filters, LedgerPosting.account_id == account_id).order_by(LedgerPosting.posting_date, LedgerPosting.journal_entry_id, LedgerPosting.line_number))
        running = opening_balance
        rows: list[dict[str, object]] = []
        for posting in result.scalars():
            running += Decimal(str(posting.debit)) - Decimal(str(posting.credit))
            rows.append({"id": posting.id, "account_id": posting.account_id, "journal_entry_id": posting.journal_entry_id, "journal_entry_line_id": posting.journal_entry_line_id, "fiscal_period_id": posting.fiscal_period_id, "posting_date": posting.posting_date, "line_number": posting.line_number, "description": posting.description, "debit": Decimal(str(posting.debit)), "credit": Decimal(str(posting.credit)), "balance": running})
        return {"account_id": account_id, "fiscal_period_id": fiscal_period_id, "start_date": start_date, "end_date": end_date, "opening_balance": opening_balance, "closing_balance": running, "movements": rows}

    async def reconcile_postings(self, organization_id: str, *, fiscal_period_id: str | None = None, start_date: date | None = None, end_date: date | None = None) -> dict[str, object]:
        period = await self._validate_period(organization_id, fiscal_period_id)
        self._validate_dates(start_date, end_date)
        self._validate_dates_within_period(period, start_date, end_date)
        journal_filters = self._journal_reconciliation_filters(organization_id, fiscal_period_id=fiscal_period_id, start_date=start_date, end_date=end_date)
        posting_filters = self._posting_filters(organization_id, fiscal_period_id, start_date, end_date)
        expected = select(JournalEntryLine.id.label("line_id"), JournalEntryLine.account_id, JournalEntryLine.debit, JournalEntryLine.credit, JournalEntry.fiscal_period_id).join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id).where(*journal_filters).subquery()
        actual = select(LedgerPosting.journal_entry_line_id.label("line_id"), LedgerPosting.account_id, LedgerPosting.debit, LedgerPosting.credit, LedgerPosting.fiscal_period_id).where(*posting_filters).subquery()
        expected_count = await self.db.scalar(select(func.count()).select_from(expected))
        actual_count = await self.db.scalar(select(func.count()).select_from(actual))
        missing_ids = list((await self.db.execute(select(expected.c.line_id).outerjoin(actual, actual.c.line_id == expected.c.line_id).where(actual.c.line_id.is_(None)))).scalars())
        orphan_ids = list((await self.db.execute(select(actual.c.line_id).outerjoin(expected, expected.c.line_id == actual.c.line_id).where(expected.c.line_id.is_(None)))).scalars())
        mismatch_ids = list((await self.db.execute(select(expected.c.line_id).join(actual, actual.c.line_id == expected.c.line_id).where((expected.c.account_id != actual.c.account_id) | (func.coalesce(expected.c.debit, 0) != func.coalesce(actual.c.debit, 0)) | (func.coalesce(expected.c.credit, 0) != func.coalesce(actual.c.credit, 0)) | (expected.c.fiscal_period_id != actual.c.fiscal_period_id)))).scalars())
        return {"organization_id": organization_id, "fiscal_period_id": fiscal_period_id, "start_date": start_date, "end_date": end_date, "expected_journal_lines": int(expected_count or 0), "actual_ledger_postings": int(actual_count or 0), "missing_postings": sorted(missing_ids), "orphan_postings": sorted(orphan_ids), "mismatched_postings": sorted(mismatch_ids), "is_reconciled": not missing_ids and not orphan_ids and not mismatch_ids}
