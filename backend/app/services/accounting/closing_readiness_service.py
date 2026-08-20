from decimal import Decimal

from app.models.accounting.closing import PeriodClosing
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.journal_entry_line import JournalEntryLine
from app.models.treasury.bank_statement_import import BankStatementImport
from app.models.treasury.banking_control import (
    BankingControlException,
    BankStatementClosure,
)
from app.schemas.accounting.closing_readiness import ClosingReadinessResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class ClosingReadinessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def assess(
        self, organization_id: str, fiscal_year_id: str
    ) -> ClosingReadinessResponse:
        fiscal_year = await self.session.scalar(
            select(FiscalYear).where(
                FiscalYear.organization_id == organization_id,
                FiscalYear.id == fiscal_year_id,
            )
        )
        if fiscal_year is None:
            raise ValueError("Fiscal year not found")
        periods = list(
            await self.session.scalars(
                select(FiscalPeriod).where(
                    FiscalPeriod.organization_id == organization_id,
                    FiscalPeriod.fiscal_year_id == fiscal_year_id,
                )
            )
        )
        period_ids = [period.id for period in periods]
        open_period_count = sum(period.status == "OPEN" for period in periods)
        locked_period_count = sum(period.status == "LOCKED" for period in periods)
        draft_count = 0
        if period_ids:
            draft_count = int(
                await self.session.scalar(
                    select(func.count(JournalEntry.id)).where(
                        JournalEntry.organization_id == organization_id,
                        JournalEntry.fiscal_period_id.in_(period_ids),
                        JournalEntry.status == "DRAFT",
                    )
                )
                or 0
            )
        unresolved_exception_count = int(
            await self.session.scalar(
                select(func.count(BankingControlException.bank_transaction_id)).where(
                    BankingControlException.organization_id == organization_id,
                    BankingControlException.status != "RECONCILED",
                )
            )
            or 0
        )
        closure_ids = select(BankStatementClosure.statement_import_id).where(
            BankStatementClosure.organization_id == organization_id
        )
        unclosed_statement_count = int(
            await self.session.scalar(
                select(func.count(BankStatementImport.id)).where(
                    BankStatementImport.organization_id == organization_id,
                    ~BankStatementImport.id.in_(closure_ids),
                )
            )
            or 0
        )
        closed_period_ids = select(PeriodClosing.fiscal_period_id).where(
            PeriodClosing.organization_id == organization_id
        )
        missing_period_closing_count = int(
            await self.session.scalar(
                select(func.count(FiscalPeriod.id)).where(
                    FiscalPeriod.organization_id == organization_id,
                    FiscalPeriod.fiscal_year_id == fiscal_year_id,
                    ~FiscalPeriod.id.in_(closed_period_ids),
                )
            )
            or 0
        )
        debit = Decimal("0.00")
        credit = Decimal("0.00")
        if period_ids:
            totals = await self.session.execute(
                select(
                    func.coalesce(func.sum(JournalEntryLine.debit), 0),
                    func.coalesce(func.sum(JournalEntryLine.credit), 0),
                )
                .join(
                    JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id
                )
                .where(
                    JournalEntry.organization_id == organization_id,
                    JournalEntry.fiscal_period_id.in_(period_ids),
                    JournalEntry.status == "POSTED",
                )
            )
            debit_value, credit_value = totals.one()
            debit = Decimal(debit_value or 0).quantize(Decimal("0.01"))
            credit = Decimal(credit_value or 0).quantize(Decimal("0.01"))
        blockers: list[str] = []
        if fiscal_year.status == "CLOSED":
            blockers.append("FISCAL_YEAR_ALREADY_CLOSED")
        if not periods:
            blockers.append("NO_FISCAL_PERIODS")
        if open_period_count:
            blockers.append("OPEN_FISCAL_PERIODS")
        if locked_period_count:
            blockers.append("LOCKED_FISCAL_PERIODS")
        if draft_count:
            blockers.append("DRAFT_JOURNAL_ENTRIES")
        if unresolved_exception_count:
            blockers.append("UNRESOLVED_BANKING_EXCEPTIONS")
        if unclosed_statement_count:
            blockers.append("UNCLOSED_BANK_STATEMENTS")
        if missing_period_closing_count:
            blockers.append("MISSING_PERIOD_CLOSINGS")
        if debit != credit:
            blockers.append("POSTED_LEDGER_NOT_BALANCED")
        return ClosingReadinessResponse(
            organization_id=organization_id,
            fiscal_year_id=fiscal_year_id,
            fiscal_year_status=fiscal_year.status,
            fiscal_period_count=len(periods),
            open_period_count=open_period_count,
            locked_period_count=locked_period_count,
            draft_journal_entry_count=draft_count,
            unresolved_banking_exception_count=unresolved_exception_count,
            unclosed_statement_count=unclosed_statement_count,
            missing_period_closing_count=missing_period_closing_count,
            total_posted_debit=debit,
            total_posted_credit=credit,
            status="READY" if not blockers else "NOT_READY",
            blockers=blockers,
        )
