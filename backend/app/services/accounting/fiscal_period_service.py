from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.accounting.fiscal_year.rules import FiscalPeriodRules
from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.journal_entry import JournalEntry, JournalEntryStatus
from app.schemas.accounting.fiscal_period import FiscalPeriodCreate
from app.repositories.accounting.fiscal_period_repository import FiscalPeriodRepository
from app.repositories.accounting.fiscal_year_repository import FiscalYearRepository
from app.services.accounting.ledger_service import LedgerService


class FiscalPeriodService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = FiscalPeriodRepository(session)
        self.year_repository = FiscalYearRepository(session)
        self.ledger_service = LedgerService(session)

    async def create_fiscal_period(self, organization_id: str, data: FiscalPeriodCreate) -> FiscalPeriod:
        FiscalPeriodRules.validate_dates(data.start_date, data.end_date)
        fiscal_year = await self.session.scalar(
            select(FiscalYear)
            .where(
                FiscalYear.organization_id == organization_id,
                FiscalYear.id == data.fiscal_year_id,
            )
            .with_for_update()
        )
        if fiscal_year is None:
            raise HTTPException(status_code=404, detail="Fiscal year not found")
        if fiscal_year.status != FiscalYearStatus.OPEN:
            raise HTTPException(status_code=409, detail="Fiscal periods can only be created in an open fiscal year")
        FiscalPeriodRules.validate_within_year(data.start_date, data.end_date, fiscal_year.start_date, fiscal_year.end_date)

        overlap = await self.session.scalar(
            select(FiscalPeriod.id)
            .where(
                FiscalPeriod.organization_id == organization_id,
                FiscalPeriod.fiscal_year_id == data.fiscal_year_id,
                FiscalPeriod.start_date <= data.end_date,
                FiscalPeriod.end_date >= data.start_date,
            )
            .limit(1)
        )
        if overlap is not None:
            raise HTTPException(status_code=409, detail="Fiscal period dates overlap an existing period")

        period = await self.repository.create(organization_id, data)
        await self.session.commit()
        await self.session.refresh(period)
        return period

    async def get_by_id(self, organization_id: str, period_id: str) -> FiscalPeriod:
        period = await self.repository.get_by_id(organization_id, period_id)
        if period is None:
            raise HTTPException(status_code=404, detail="Fiscal period not found")
        return period

    async def get_by_fiscal_year(self, organization_id: str, fiscal_year_id: str) -> list[FiscalPeriod]:
        if await self.year_repository.get_by_id(organization_id, fiscal_year_id) is None:
            raise HTTPException(status_code=404, detail="Fiscal year not found")
        return await self.repository.list_by_fiscal_year(organization_id, fiscal_year_id)

    async def close_period(self, organization_id: str, period_id: str) -> FiscalPeriod:
        period = await self.session.scalar(
            select(FiscalPeriod)
            .where(
                FiscalPeriod.organization_id == organization_id,
                FiscalPeriod.id == period_id,
            )
            .with_for_update()
        )
        if period is None:
            raise HTTPException(status_code=404, detail="Fiscal period not found")
        if period.status != FiscalPeriodStatus.OPEN:
            raise HTTPException(status_code=409, detail="Only an open fiscal period can be closed")

        draft_count = await self.session.scalar(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.organization_id == organization_id,
                JournalEntry.fiscal_period_id == period_id,
                JournalEntry.status == JournalEntryStatus.DRAFT,
            )
        )
        if draft_count:
            raise HTTPException(status_code=409, detail="Fiscal period contains unposted journal entries")

        reconciliation = await self.ledger_service.reconcile_postings(
            organization_id,
            fiscal_period_id=period_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not reconciliation["is_reconciled"]:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Fiscal period ledger is not reconciled: "
                    f"missing={reconciliation['missing_postings']}, "
                    f"orphan={reconciliation['orphan_postings']}, "
                    f"mismatched={reconciliation['mismatched_postings']}"
                ),
            )

        totals = await self.session.execute(
            select(
                func.coalesce(func.sum(LedgerPosting.debit), 0),
                func.coalesce(func.sum(LedgerPosting.credit), 0),
            ).where(
                LedgerPosting.organization_id == organization_id,
                LedgerPosting.fiscal_period_id == period_id,
                LedgerPosting.posting_date >= period.start_date,
                LedgerPosting.posting_date <= period.end_date,
            )
        )
        total_debit, total_credit = totals.one()
        if total_debit != total_credit:
            raise HTTPException(status_code=409, detail="Fiscal period ledger is not balanced")

        period.status = FiscalPeriodStatus.CLOSED
        await self.session.commit()
        await self.session.refresh(period)
        return period
