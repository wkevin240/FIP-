from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.audit_context import AuditContext
from app.domain.accounting.journal_entry.validators import JournalEntry as DomainJournalEntry
from app.domain.accounting.journal_entry.validators import JournalEntryValidationError, JournalLine
from app.core.enums.accounting import FiscalPeriodStatus
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.journal_entry import JournalEntry, JournalEntryLine, JournalEntryStatus
from app.models.accounting.ledger_posting import LedgerPosting
from app.repositories.accounting.journal_entry_repository import JournalEntryRepository
from app.repositories.audit.audit_log_repository import AuditLogRepository
from app.schemas.accounting.journal_entry import JournalEntryCreate, JournalEntryReverse


class JournalEntryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = JournalEntryRepository(session)
        self.audit_repository = AuditLogRepository(session)

    @staticmethod
    def _request_hash(data: JournalEntryCreate | JournalEntryReverse) -> str:
        payload = data.model_dump(mode="json")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _audit_payload(entry: JournalEntry) -> dict:
        return {
            "journal_entry_id": entry.id,
            "fiscal_period_id": entry.fiscal_period_id,
            "entry_date": entry.entry_date.isoformat(),
            "status": entry.status.value,
            "idempotency_key": entry.idempotency_key,
            "lines": [
                {
                    "line_id": line.id,
                    "line_number": line.line_number,
                    "account_id": line.account_id,
                    "debit": str(line.debit),
                    "credit": str(line.credit),
                }
                for line in entry.lines
            ],
        }

    @staticmethod
    def _fiscal_period_lock(organization_id: str, period_id: str):
        return (
            select(FiscalPeriod)
            .where(
                FiscalPeriod.organization_id == organization_id,
                FiscalPeriod.id == period_id,
            )
            .with_for_update()
        )

    @staticmethod
    def _journal_entry_lock(organization_id: str, entry_id: str):
        return (
            select(JournalEntry)
            .where(JournalEntry.organization_id == organization_id, JournalEntry.id == entry_id)
            .with_for_update()
        )

    async def _load_with_lines(self, organization_id: str, entry_id: str) -> JournalEntry:
        entry = await self.session.scalar(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(JournalEntry.organization_id == organization_id, JournalEntry.id == entry_id)
        )
        if entry is None:
            raise HTTPException(status_code=404, detail="Journal entry not found")
        return entry

    async def create(self, organization_id: str, actor_id: str, data: JournalEntryCreate) -> JournalEntry:
        request_hash = self._request_hash(data)
        existing = await self.repository.get_by_idempotency_key(organization_id, data.idempotency_key)
        if existing:
            if existing.idempotency_hash != request_hash:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different journal entry")
            return await self._load_with_lines(organization_id, existing.id)

        period = await self.session.scalar(self._fiscal_period_lock(organization_id, data.fiscal_period_id))
        if period is None:
            raise HTTPException(status_code=404, detail="Fiscal period not found")
        if period.status != FiscalPeriodStatus.OPEN:
            raise HTTPException(status_code=409, detail="Journal entries can only be created in an open fiscal period")
        if not (period.start_date <= data.entry_date <= period.end_date):
            raise HTTPException(status_code=422, detail="Entry date must fall within the fiscal period")

        account_ids = [line.account_id for line in data.lines]
        accounts = list(
            await self.session.scalars(
                select(Account).where(
                    Account.organization_id == organization_id,
                    Account.id.in_(account_ids),
                )
            )
        )
        accounts_by_id = {account.id: account for account in accounts}
        missing = [account_id for account_id in account_ids if account_id not in accounts_by_id]
        if missing:
            raise HTTPException(status_code=404, detail=f"Account not found: {missing[0]}")
        inactive = next((account.id for account in accounts if not account.is_active), None)
        if inactive:
            raise HTTPException(status_code=409, detail=f"Account is inactive: {inactive}")

        try:
            DomainJournalEntry.from_lines(
                [JournalLine(account_id=line.account_id, debit=line.debit, credit=line.credit) for line in data.lines]
            )
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
            created_by=actor_id,
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
            await self.session.flush()
            await self.audit_repository.append(
                AuditContext(organization_id=organization_id, actor_id=actor_id, action="JOURNAL_ENTRY_CREATED"),
                entity_type="journal_entry",
                entity_id=entry.id,
                payload=self._audit_payload(entry),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.repository.get_by_idempotency_key(organization_id, data.idempotency_key)
            if existing and existing.idempotency_hash == request_hash:
                return await self._load_with_lines(organization_id, existing.id)
            raise HTTPException(status_code=409, detail="Journal entry conflicts with an existing idempotency key") from exc
        except Exception:
            await self.session.rollback()
            raise
        return await self._load_with_lines(organization_id, entry.id)

    async def get(self, organization_id: str, entry_id: str) -> JournalEntry:
        return await self._load_with_lines(organization_id, entry_id)

    async def _post_locked(self, entry: JournalEntry, organization_id: str, actor_id: str) -> JournalEntry:
        """Post a locked draft without committing; callers own the transaction."""
        if entry.status == JournalEntryStatus.POSTED:
            ledger_exists = await self.session.scalar(
                select(LedgerPosting.id)
                .where(LedgerPosting.organization_id == organization_id, LedgerPosting.journal_entry_id == entry.id)
                .limit(1)
            )
            if ledger_exists is None:
                raise HTTPException(status_code=409, detail="Posted journal entry has no ledger postings")
            return entry
        if entry.status != JournalEntryStatus.DRAFT:
            raise HTTPException(status_code=409, detail="Only draft journal entries can be posted")
        if entry.created_by is not None and entry.created_by == actor_id:
            raise HTTPException(status_code=403, detail="Journal entry creator cannot post the same journal entry")

        period = await self.session.scalar(self._fiscal_period_lock(organization_id, entry.fiscal_period_id))
        if period is None:
            raise HTTPException(status_code=404, detail="Fiscal period not found")
        if period.status != FiscalPeriodStatus.OPEN:
            raise HTTPException(status_code=409, detail="Journal entries cannot be posted to a closed or locked fiscal period")
        if not (period.start_date <= entry.entry_date <= period.end_date):
            raise HTTPException(status_code=422, detail="Entry date must fall within the fiscal period")

        try:
            DomainJournalEntry.from_lines(
                [
                    JournalLine(account_id=line.account_id, debit=Decimal(line.debit), credit=Decimal(line.credit))
                    for line in entry.lines
                ]
            )
        except JournalEntryValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        existing = await self.session.scalar(
            select(LedgerPosting.id)
            .where(LedgerPosting.organization_id == organization_id, LedgerPosting.journal_entry_id == entry.id)
            .limit(1)
        )
        if existing:
            raise HTTPException(status_code=409, detail="Journal entry already has ledger postings")

        for line in entry.lines:
            self.session.add(
                LedgerPosting(
                    organization_id=entry.organization_id,
                    fiscal_period_id=entry.fiscal_period_id,
                    journal_entry_id=entry.id,
                    journal_entry_line_id=line.id,
                    account_id=line.account_id,
                    posting_date=entry.entry_date,
                    line_number=line.line_number,
                    description=line.description,
                    debit=line.debit,
                    credit=line.credit,
                )
            )
        entry.status = JournalEntryStatus.POSTED
        entry.posted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        entry.posted_by = actor_id
        await self.session.flush()
        return entry

    async def post(self, organization_id: str, entry_id: str, actor_id: str) -> JournalEntry:
        entry_period = await self.session.scalar(
            select(JournalEntry.fiscal_period_id)
            .where(JournalEntry.organization_id == organization_id, JournalEntry.id == entry_id)
        )
        if entry_period is None:
            raise HTTPException(status_code=404, detail="Journal entry not found")
        period = await self.session.scalar(self._fiscal_period_lock(organization_id, entry_period))
        if period is None:
            raise HTTPException(status_code=404, detail="Fiscal period not found")

        entry = await self.session.scalar(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(JournalEntry.organization_id == organization_id, JournalEntry.id == entry_id)
            .with_for_update()
        )
        if entry is None:
            raise HTTPException(status_code=404, detail="Journal entry not found")
        try:
            await self._post_locked(entry, organization_id, actor_id)
            await self.audit_repository.append(
                AuditContext(organization_id=organization_id, actor_id=actor_id, action="JOURNAL_ENTRY_POSTED"),
                entity_type="journal_entry",
                entity_id=entry.id,
                payload=self._audit_payload(entry),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="Journal entry could not be posted safely") from exc
        except Exception:
            await self.session.rollback()
            raise
        return await self._load_with_lines(organization_id, entry.id)

    async def reverse(self, organization_id: str, entry_id: str, actor_id: str, data: JournalEntryReverse) -> JournalEntry:
        original_period = await self.session.scalar(
            select(JournalEntry.fiscal_period_id)
            .where(JournalEntry.organization_id == organization_id, JournalEntry.id == entry_id)
        )
        if original_period is None:
            raise HTTPException(status_code=404, detail="Journal entry not found")
        period = await self.session.scalar(self._fiscal_period_lock(organization_id, original_period))
        if period is None:
            raise HTTPException(status_code=404, detail="Fiscal period not found")

        original = await self.session.scalar(
            select(JournalEntry)
            .options(selectinload(JournalEntry.lines))
            .where(JournalEntry.organization_id == organization_id, JournalEntry.id == entry_id)
            .with_for_update()
        )
        if original is None:
            raise HTTPException(status_code=404, detail="Journal entry not found")
        if original.status != JournalEntryStatus.POSTED:
            raise HTTPException(status_code=409, detail="Only a posted journal entry can be reversed")
        if original.created_by is not None and original.created_by == actor_id:
            raise HTTPException(status_code=403, detail="Journal entry creator cannot reverse the same journal entry")

        request_hash = self._request_hash(data)
        existing = await self.repository.get_by_idempotency_key(organization_id, data.idempotency_key)
        if existing:
            if existing.idempotency_hash != request_hash:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different journal entry")
            return await self._load_with_lines(organization_id, existing.id)

        already_reversed = await self.session.scalar(
            select(JournalEntry.id).where(
                JournalEntry.organization_id == organization_id,
                JournalEntry.reversal_of_id == original.id,
            )
        )
        if already_reversed:
            raise HTTPException(status_code=409, detail="Journal entry has already been reversed")

        if period.status != FiscalPeriodStatus.OPEN:
            raise HTTPException(status_code=409, detail="A reversal requires an open fiscal period")

        reversal_date = data.entry_date or original.entry_date
        if not (period.start_date <= reversal_date <= period.end_date):
            raise HTTPException(status_code=422, detail="Reversal date must fall within the fiscal period")

        reversal = JournalEntry(
            organization_id=organization_id,
            fiscal_period_id=original.fiscal_period_id,
            entry_date=reversal_date,
            reference=data.reference or original.reference,
            description=data.description or f"Reversal of journal entry {original.id}",
            status=JournalEntryStatus.DRAFT,
            idempotency_key=data.idempotency_key,
            idempotency_hash=request_hash,
            created_by=actor_id,
            reversal_of_id=original.id,
        )
        reversal.lines = [
            JournalEntryLine(
                line_number=index,
                account_id=line.account_id,
                description=line.description,
                debit=line.credit,
                credit=line.debit,
            )
            for index, line in enumerate(original.lines, start=1)
        ]
        self.session.add(reversal)
        try:
            await self.session.flush()
            await self._post_locked(reversal, organization_id, actor_id)
            original.status = JournalEntryStatus.REVERSED
            await self.session.flush()
            await self.audit_repository.append(
                AuditContext(organization_id=organization_id, actor_id=actor_id, action="JOURNAL_ENTRY_REVERSED"),
                entity_type="journal_entry",
                entity_id=reversal.id,
                payload={"original_journal_entry_id": original.id, "reversal": self._audit_payload(reversal)},
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="Journal entry reversal conflicts with an existing reversal or idempotency key") from exc
        except Exception:
            await self.session.rollback()
            raise

        return await self._load_with_lines(organization_id, reversal.id)
