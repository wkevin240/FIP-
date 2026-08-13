from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums.accounting import JournalEntryStatus
from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.vat import VATEntry, VATRate
from app.schemas.accounting.vat import VATRateCreate


class VATRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_rate(self, organization_id: str, data: VATRateCreate) -> VATRate:
        rate = VATRate(**data.model_dump(), organization_id=organization_id)
        self.session.add(rate)
        await self.session.flush()
        return rate

    async def get_rate(self, organization_id: str, rate_id: str) -> VATRate | None:
        return await self.session.scalar(
            select(VATRate).where(
                VATRate.organization_id == organization_id,
                VATRate.id == rate_id,
            )
        )

    async def get_effective_rate(
        self, organization_id: str, rate_id: str, tax_date: date
    ) -> VATRate | None:
        return await self.session.scalar(
            select(VATRate).where(
                VATRate.organization_id == organization_id,
                VATRate.id == rate_id,
                VATRate.is_active.is_(True),
                VATRate.effective_from <= tax_date,
                (VATRate.effective_to.is_(None)) | (VATRate.effective_to >= tax_date),
            )
        )

    async def list_rates(self, organization_id: str) -> list[VATRate]:
        result = await self.session.scalars(
            select(VATRate)
            .where(VATRate.organization_id == organization_id)
            .order_by(VATRate.code, VATRate.effective_from.desc())
        )
        return list(result)

    async def get_entry_by_journal_entry(
        self, organization_id: str, journal_entry_id: str
    ) -> VATEntry | None:
        return await self.session.scalar(
            select(VATEntry).where(
                VATEntry.organization_id == organization_id,
                VATEntry.journal_entry_id == journal_entry_id,
            )
        )

    async def get_posted_journal_entry(
        self, organization_id: str, journal_entry_id: str
    ) -> JournalEntry | None:
        return await self.session.scalar(
            select(JournalEntry).where(
                JournalEntry.organization_id == organization_id,
                JournalEntry.id == journal_entry_id,
                JournalEntry.status == JournalEntryStatus.POSTED,
            )
        )

    async def create_entry(self, entry: VATEntry) -> VATEntry:
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def summary(
        self, organization_id: str, start_date: date, end_date: date
    ) -> dict[str, Decimal]:
        result = await self.session.execute(
            select(
                VATEntry.direction,
                func.coalesce(func.sum(VATEntry.vat_amount), 0).label("total"),
            )
            .where(
                VATEntry.organization_id == organization_id,
                VATEntry.tax_date >= start_date,
                VATEntry.tax_date <= end_date,
            )
            .group_by(VATEntry.direction)
        )
        totals = {"INPUT": Decimal("0.00"), "OUTPUT": Decimal("0.00")}
        for direction, total in result.all():
            totals[direction] = Decimal(total)
        return totals
