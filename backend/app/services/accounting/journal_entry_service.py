from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.accounting.journal_entry.validators import JournalEntry as DomainJournalEntry
from app.domain.accounting.journal_entry.validators import JournalEntryValidationError, JournalLine
from app.core.enums.accounting import FiscalPeriodStatus
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.journal_entry import JournalEntry, JournalEntryLine, JournalEntryStatus
from app.repositories.accounting.journal_entry_repository import JournalEntryRepository
from app.schemas.accounting.journal_entry import JournalEntryCreate


class JournalEntryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = JournalEntryRepository(session)

    @staticmethod
    def _request_hash(data: JournalEntryCreate) -> str:
        payload = data.model_dump(mode="json")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def create(self, organization_id: str, data: JournalEntryCreate) -> JournalEntry:
        request_hash = self._request_hash(data)
        existing = await self.repository.get_by_idempotency_key(organization_id, data.idempotency_key)
        if existing:
            if existing.idempotency_hash != request_hash:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different journal entry")
            return existing

        period = await self.session.scalar(select(FiscalPeriod).where(FiscalPeriod.organization_id == organization_id, FiscalPeriod.id == data.fiscal_period_id))
        if period is None:
            raise HTTPException(status_code=404, detail="Fiscal period not found")
        if period.status != FiscalPeriodStatus.OPEN:
            raise HTTPException(status_code=409, detail="Journal entries can only be created in an open fiscal period")
        if not (period.start_date <= data.entry_date <= period.end_date):
            raise HTTPException(status_code=422, detail="Entry date must fall within the fiscal period")

        account_ids = [line.account_id for line in data.lines]
        accounts = list(await self.session.scalars(select(Account).where(Account.organization_id == organization_id, Account.id.in_(account_ids))))
        accounts_by_id = {account.id: account for account in accounts}
        missing = [account_id for account_id in account_ids if account_id not in accounts_by_id]
        if missing:
            raise HTTPException(status_code=404, detail=f"Account not found: {missing[0]}")
        inactive = next((account.id for account in accounts if not account.is_active), None)
        if inactive:
            raise HTTPException(status_code=409, detail=f"Account is inactive: {inactive}")

        try:
            DomainJournalEntry.from_lines([JournalLine(account_id=line.account_id, debit=line.debit, credit=line.credit) for line in data.lines])
        except JournalEntryValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        entry = JournalEntry(
            organization_id=organization_id,
            fiscal_period_id=data.fiscal_period_id,
            entry_date=data.entry_date,
            reference=data.reference.strip() if data.reference else None,
            description=data.description.strip(),
            idempotency_key=data.idempotency_key,
            idempotency_hash=request_hash,
            status=JournalEntryStatus.DRAFT,
        )
        entry.lines = [
            JournalEntryLine(
                line_number=index,
                account_id=line.account_id,
                description=line.description.strip() if line.description else None,
                debit=line.debit,
                credit=line.credit,
            )
            for index, line in enumerate(data.lines, start=1)
        ]
        self.session.add(entry)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.repository.get_by_idempotency_key(organization_id, data.idempotency_key)
            if existing and existing.idempotency_hash == request_hash:
                return existing
            raise HTTPException(status_code=409, detail="Journal entry conflicts with an existing idempotency key") from exc
        await self.session.refresh(entry)
        return entry

    async def get(self, organization_id: str, entry_id: str) -> JournalEntry:
        entry = await self.repository.get_by_id(organization_id, entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Journal entry not found")
        return entry

    async def post(self, organization_id: str, entry_id: str, actor_id: str) -> JournalEntry:
        entry = await self.get(organization_id, entry_id)
        if entry.status == JournalEntryStatus.POSTED:
            return entry
        if entry.status != JournalEntryStatus.DRAFT:
            raise HTTPException(status_code=409, detail="Only draft journal entries can be posted")

        period = await self.session.scalar(select(FiscalPeriod).where(FiscalPeriod.organization_id == organization_id, FiscalPeriod.id == entry.fiscal_period_id))
        if period is None:
            raise HTTPException(status_code=404, detail="Fiscal period not found")
        if period.status != FiscalPeriodStatus.OPEN:
            raise HTTPException(status_code=409, detail="Journal entries cannot be posted to a closed or locked fiscal period")
        if not (period.start_date <= entry.entry_date <= period.end_date):
            raise HTTPException(status_code=422, detail="Entry date must fall within the fiscal period")

        try:
            DomainJournalEntry.from_lines([JournalLine(account_id=line.account_id, debit=Decimal(line.debit), credit=Decimal(line.credit)) for line in entry.lines])
        except JournalEntryValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        entry.status = JournalEntryStatus.POSTED
        entry.posted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        entry.posted_by = actor_id
        await self.session.commit()
        await self.session.refresh(entry)
        return entry
