import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from app.core.enums.accounting import FiscalPeriodStatus, JournalEntryStatus
from app.domain.accounting.closing.rules import PeriodClosingRules
from app.domain.accounting.journal_entry.rules import JournalEntryRules
from app.models.accounting.closing import PeriodClosing
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.journal_entry import JournalEntry
from app.repositories.accounting.closing_repository import ClosingRepository
from app.schemas.accounting.closing import (
    PeriodClosingSummaryResponse,
)
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class ClosingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ClosingRepository(session)

    async def preview_closing(
        self, organization_id: str, fiscal_period_id: str
    ) -> PeriodClosingSummaryResponse:
        period = await self._get_period(organization_id, fiscal_period_id)
        return await self._build_summary(organization_id, period)

    async def get_closing(
        self, organization_id: str, fiscal_period_id: str
    ) -> PeriodClosing:
        closing = await self.repository.get_by_period(organization_id, fiscal_period_id)
        if closing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Period closing not found"
            )
        return closing

    async def close_period(
        self, organization_id: str, fiscal_period_id: str, closed_by_user_id: str
    ) -> PeriodClosing:
        try:
            period = await self.session.scalar(
                select(FiscalPeriod)
                .where(
                    FiscalPeriod.organization_id == organization_id,
                    FiscalPeriod.id == fiscal_period_id,
                )
                .with_for_update()
            )
            if period is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Fiscal period not found",
                )
            if period.status != FiscalPeriodStatus.OPEN:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Only open fiscal periods can be closed",
                )
            if await self.repository.get_by_period(organization_id, fiscal_period_id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Fiscal period already has a closing record",
                )

            period.status = FiscalPeriodStatus.LOCKED
            await self.session.flush()

            draft_count = await self.session.scalar(
                select(func.count(JournalEntry.id)).where(
                    JournalEntry.organization_id == organization_id,
                    JournalEntry.fiscal_period_id == fiscal_period_id,
                    JournalEntry.status == JournalEntryStatus.DRAFT,
                )
            )
            if draft_count:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Draft journal entries must be posted or voided before closing",
                )

            summary = await self._build_summary(
                organization_id, period, lock_entries=True
            )
            period.status = FiscalPeriodStatus.CLOSED
            closing = PeriodClosing(
                organization_id=organization_id,
                fiscal_period_id=fiscal_period_id,
                closed_by_user_id=closed_by_user_id,
                closed_at=datetime.now(timezone.utc),
                posted_entry_count=summary.posted_entry_count,
                posted_line_count=summary.posted_line_count,
                total_debit=summary.total_debit,
                total_credit=summary.total_credit,
                control_hash=summary.control_hash,
            )
            await self.repository.create(closing)
            await self.session.commit()
        except HTTPException:
            await self.session.rollback()
            raise
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Fiscal period already has a closing record",
            ) from exc

        await self.session.refresh(closing)
        return closing

    async def _get_period(
        self, organization_id: str, fiscal_period_id: str
    ) -> FiscalPeriod:
        period = await self.session.scalar(
            select(FiscalPeriod).where(
                FiscalPeriod.organization_id == organization_id,
                FiscalPeriod.id == fiscal_period_id,
            )
        )
        if period is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Fiscal period not found"
            )
        return period

    async def _build_summary(
        self,
        organization_id: str,
        period: FiscalPeriod,
        lock_entries: bool = False,
    ) -> PeriodClosingSummaryResponse:
        query = (
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(
                JournalEntry.organization_id == organization_id,
                JournalEntry.fiscal_period_id == period.id,
                JournalEntry.status == JournalEntryStatus.POSTED,
            )
            .order_by(
                JournalEntry.entry_date,
                JournalEntry.journal_id,
                JournalEntry.entry_number,
                JournalEntry.id,
            )
        )
        if lock_entries:
            query = query.with_for_update()
        result = await self.session.scalars(query)
        entries = list(result.unique())

        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")
        posted_line_count = 0
        digest_entries = []
        for entry in entries:
            try:
                JournalEntryRules.validate_balanced_lines(entry.lines)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Posted entry {entry.entry_number} is invalid: {exc}",
                ) from exc

            digest_lines = []
            for line in entry.lines:
                debit = Decimal(line.debit)
                credit = Decimal(line.credit)
                total_debit += debit
                total_credit += credit
                posted_line_count += 1
                digest_lines.append(
                    {
                        "account_id": line.account_id,
                        "credit": format(credit, ".2f"),
                        "debit": format(debit, ".2f"),
                        "id": line.id,
                        "line_number": line.line_number,
                    }
                )
            digest_entries.append(
                {
                    "entry_date": entry.entry_date.isoformat(),
                    "entry_number": entry.entry_number,
                    "id": entry.id,
                    "journal_id": entry.journal_id,
                    "lines": digest_lines,
                }
            )

        try:
            PeriodClosingRules.validate_summary(
                len(entries), posted_line_count, total_debit, total_credit
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc

        control_payload = json.dumps(
            {
                "entries": digest_entries,
                "fiscal_period_id": period.id,
                "organization_id": organization_id,
                "total_credit": format(total_credit, ".2f"),
                "total_debit": format(total_debit, ".2f"),
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        control_hash = hashlib.sha256(control_payload.encode("utf-8")).hexdigest()
        return PeriodClosingSummaryResponse(
            fiscal_period_id=period.id,
            posted_entry_count=len(entries),
            posted_line_count=posted_line_count,
            total_debit=total_debit,
            total_credit=total_credit,
            control_hash=control_hash,
        )
