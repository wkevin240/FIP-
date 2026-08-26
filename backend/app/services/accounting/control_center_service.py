from datetime import date
from decimal import Decimal

from app.core.enums.accounting import JournalEntryStatus
from app.models.accounting.bank_transaction import BankTransaction
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.journal_entry_line import JournalEntryLine
from app.models.treasury.banking_control import BankingControlException
from app.schemas.accounting.control_center import FinancialControlCenterResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class FinancialControlCenterService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def summarize(
        self, organization_id: str, as_of_date: date
    ) -> FinancialControlCenterResponse:
        draft_count = int(
            await self.session.scalar(
                select(func.count(JournalEntry.id)).where(
                    JournalEntry.organization_id == organization_id,
                    JournalEntry.status == JournalEntryStatus.DRAFT,
                )
            )
            or 0
        )
        open_period_count = int(
            await self.session.scalar(
                select(func.count(FiscalPeriod.id)).where(
                    FiscalPeriod.organization_id == organization_id,
                    FiscalPeriod.start_date <= as_of_date,
                    FiscalPeriod.end_date >= as_of_date,
                    FiscalPeriod.status != "CLOSED",
                )
            )
            or 0
        )
        unresolved_exception_count = int(
            await self.session.scalar(
                select(func.count(BankingControlException.id)).where(
                    BankingControlException.organization_id == organization_id,
                    BankingControlException.status.in_(
                        [
                            "NO_MATCH",
                            "AMBIGUOUS",
                            "PENDING",
                            "REJECTED",
                            "INVALID_RULE",
                            "POSTED_UNRECONCILED",
                        ]
                    ),
                )
            )
            or 0
        )
        unreconciled_count = int(
            await self.session.scalar(
                select(func.count(BankTransaction.id)).where(
                    BankTransaction.organization_id == organization_id,
                    BankTransaction.transaction_date <= as_of_date,
                    BankTransaction.reconciled_at.is_(None),
                )
            )
            or 0
        )
        # The detailed ledger line aggregation is independent of entry creation;
        # the control center reports a deterministic balance from POSTED lines only.
        totals = await self.session.execute(
            select(
                func.coalesce(func.sum(JournalEntryLine.debit), 0),
                func.coalesce(func.sum(JournalEntryLine.credit), 0),
            )
            .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
            .where(
                JournalEntryLine.organization_id == organization_id,
                JournalEntry.status == JournalEntryStatus.POSTED,
                JournalEntry.entry_date <= as_of_date,
            )
        )
        debit, credit = totals.one()
        blockers: list[str] = []
        if draft_count:
            blockers.append("DRAFT_JOURNAL_ENTRIES")
        if unresolved_exception_count:
            blockers.append("UNRESOLVED_BANKING_EXCEPTIONS")
        if unreconciled_count:
            blockers.append("UNRECONCILED_BANK_TRANSACTIONS")
        if open_period_count:
            blockers.append("OPEN_CURRENT_PERIOD")
        if Decimal(debit or 0) != Decimal(credit or 0):
            blockers.append("POSTED_LEDGER_OUT_OF_BALANCE")
        return FinancialControlCenterResponse(
            organization_id=organization_id,
            as_of_date=as_of_date,
            status="READY" if not blockers else "NOT_READY",
            posted_debit_total=Decimal(debit or 0),
            posted_credit_total=Decimal(credit or 0),
            draft_entry_count=draft_count,
            open_period_count=open_period_count,
            unresolved_banking_exception_count=unresolved_exception_count,
            unreconciled_bank_transaction_count=unreconciled_count,
            blockers=blockers,
        )
