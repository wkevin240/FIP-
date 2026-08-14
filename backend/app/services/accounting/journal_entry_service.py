from datetime import datetime, timezone
from decimal import Decimal

from app.core.config import settings
from app.core.enums.accounting import FiscalPeriodStatus, JournalEntryStatus
from app.domain.accounting.journal_entry.rules import JournalEntryRules
from app.models.accounting.account import Account
from app.models.accounting.journal_entry import JournalEntry
from app.repositories.accounting.fiscal_period_repository import FiscalPeriodRepository
from app.repositories.accounting.journal_entry_repository import JournalEntryRepository
from app.repositories.accounting.journal_repository import JournalRepository
from app.schemas.accounting.journal_entry import (
    JournalEntryCorrectionCreate,
    JournalEntryCreate,
    JournalEntryReversalCreate,
)
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class JournalEntryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.entry_repository = JournalEntryRepository(session)
        self.journal_repository = JournalRepository(session)
        self.period_repository = FiscalPeriodRepository(session)
        self.audit = AuditService(session)

    async def get_entry(
        self, organization_id: str, journal_entry_id: str
    ) -> JournalEntry:
        entry = await self.entry_repository.get_by_id(organization_id, journal_entry_id)
        if entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found"
            )
        return entry

    async def get_all_entries(
        self, organization_id: str, skip: int = 0, limit: int = 100
    ) -> list[JournalEntry]:
        return await self.entry_repository.list(organization_id, skip, min(limit, 100))

    async def create_entry(
        self,
        organization_id: str,
        data: JournalEntryCreate,
        actor_user_id: str | None = None,
    ) -> JournalEntry:
        return await self._create_entry(
            organization_id, data, actor_user_id, commit=True
        )

    async def _create_entry(
        self,
        organization_id: str,
        data: JournalEntryCreate,
        actor_user_id: str | None,
        *,
        commit: bool,
        reversal_of_id: str | None = None,
        reversal_reason: str | None = None,
    ) -> JournalEntry:
        journal = await self.journal_repository.get_by_id(
            organization_id, data.journal_id
        )
        if journal is None or not journal.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Active journal not found",
            )
        period = await self.period_repository.get_by_id(
            organization_id, data.fiscal_period_id, for_update=True
        )
        if period is None or period.status != FiscalPeriodStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Fiscal period is not open",
            )
        try:
            JournalEntryRules.validate_entry_date(
                data.entry_date, period.start_date, period.end_date
            )
            JournalEntryRules.validate_balanced_lines(data.lines)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        if await self.entry_repository.get_by_number(
            organization_id, data.journal_id, data.entry_number
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Entry number already exists in this journal",
            )
        await self._validate_active_accounts(organization_id, data)
        try:
            entry = await self.entry_repository.create(
                organization_id,
                data,
                reversal_of_id=reversal_of_id,
                reversal_reason=reversal_reason,
            )
            await self.audit.record(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="JOURNAL_ENTRY_CREATED",
                resource_type="JournalEntry",
                resource_id=entry.id,
                new_value={
                    "entry_number": entry.entry_number,
                    "entry_date": str(entry.entry_date),
                    "status": entry.status,
                },
                transaction_id=entry.id,
            )
            if commit:
                await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Entry number already exists in this journal",
            ) from exc
        return entry if not commit else await self.get_entry(organization_id, entry.id)

    async def post_entry(
        self,
        organization_id: str,
        journal_entry_id: str,
        actor_user_id: str | None = None,
        *,
        commit: bool = True,
    ) -> JournalEntry:
        entry = await self.get_entry(organization_id, journal_entry_id)
        if entry.status != JournalEntryStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only draft entries can be posted",
            )
        period = await self.period_repository.get_by_id(
            organization_id, entry.fiscal_period_id, for_update=True
        )
        if period is None or period.status != FiscalPeriodStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Fiscal period is not open",
            )
        try:
            JournalEntryRules.validate_entry_date(
                entry.entry_date, period.start_date, period.end_date
            )
            JournalEntryRules.validate_balanced_lines(entry.lines)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        account_ids = {line.account_id for line in entry.lines}
        active_accounts = await self.session.scalars(
            select(Account.id).where(
                Account.organization_id == organization_id,
                Account.id.in_(account_ids),
                Account.is_active.is_(True),
            )
        )
        if len(set(active_accounts)) != len(account_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="All entry accounts must exist and be active",
            )
        await self._authorized_transition("post_journal_entry", entry.id)
        if self.session.bind and self.session.bind.dialect.name == "postgresql":
            await self.session.refresh(entry)
        else:
            entry.status = JournalEntryStatus.POSTED
            entry.posted_at = datetime.now(timezone.utc)
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="JOURNAL_ENTRY_POSTED",
            resource_type="JournalEntry",
            resource_id=entry.id,
            previous_value={"status": JournalEntryStatus.DRAFT.value},
            new_value={"status": JournalEntryStatus.POSTED.value},
            transaction_id=entry.id,
        )
        if commit:
            await self.session.commit()
            return await self.get_entry(organization_id, entry.id)
        return entry

    async def reverse_entry(
        self,
        organization_id: str,
        journal_entry_id: str,
        data: JournalEntryReversalCreate,
        actor_user_id: str | None = None,
        *,
        commit: bool = True,
    ) -> tuple[JournalEntry, JournalEntry]:
        original = await self.get_entry(organization_id, journal_entry_id)
        if original.status != JournalEntryStatus.POSTED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only posted entries can be reversed",
            )
        if await self.session.scalar(
            select(JournalEntry.id).where(
                JournalEntry.organization_id == organization_id,
                JournalEntry.reversal_of_id == original.id,
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A reversal already exists for this journal entry",
            )
        reversal_data = JournalEntryCreate(
            journal_id=original.journal_id,
            fiscal_period_id=data.fiscal_period_id,
            entry_number=data.entry_number,
            entry_date=data.entry_date,
            description=f"Reversal of {original.entry_number}: {data.reason}",
            reference=data.reference or original.reference,
            lines=[
                JournalEntryLineCreate(
                    account_id=line.account_id,
                    debit=Decimal(line.credit),
                    credit=Decimal(line.debit),
                )
                for line in original.lines
            ],
        )
        reversal = await self._create_entry(
            organization_id,
            reversal_data,
            actor_user_id,
            commit=False,
            reversal_of_id=original.id,
            reversal_reason=data.reason,
        )
        await self.post_entry(organization_id, reversal.id, actor_user_id, commit=False)
        await self._authorized_transition(
            "void_journal_entry", original.id, actor_user_id or "system"
        )
        if self.session.bind and self.session.bind.dialect.name == "postgresql":
            await self.session.refresh(original)
        else:
            original.status = JournalEntryStatus.VOIDED
            original.voided_at = datetime.now(timezone.utc)
            original.voided_by_user_id = actor_user_id or "system"
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="JOURNAL_ENTRY_REVERSED",
            resource_type="JournalEntry",
            resource_id=original.id,
            previous_value={"status": JournalEntryStatus.POSTED.value},
            new_value={
                "status": JournalEntryStatus.VOIDED.value,
                "reversal_entry_id": reversal.id,
                "reason": data.reason,
            },
            transaction_id=original.id,
        )
        if commit:
            await self.session.commit()
            return await self.get_entry(
                organization_id, original.id
            ), await self.get_entry(organization_id, reversal.id)
        return original, reversal

    async def correct_entry(
        self,
        organization_id: str,
        journal_entry_id: str,
        data: JournalEntryCorrectionCreate,
        actor_user_id: str | None = None,
    ) -> tuple[JournalEntry, JournalEntry, JournalEntry]:
        original, reversal = await self.reverse_entry(
            organization_id,
            journal_entry_id,
            data.reversal,
            actor_user_id,
            commit=False,
        )
        correction = await self._create_entry(
            organization_id, data.correction, actor_user_id, commit=False
        )
        await self.post_entry(
            organization_id, correction.id, actor_user_id, commit=False
        )
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="JOURNAL_ENTRY_CORRECTED",
            resource_type="JournalEntry",
            resource_id=correction.id,
            previous_value={
                "original_entry_id": original.id,
                "reversal_entry_id": reversal.id,
            },
            new_value={"correction_entry_id": correction.id},
            transaction_id=original.id,
        )
        await self.session.commit()
        return (
            await self.get_entry(organization_id, original.id),
            await self.get_entry(organization_id, reversal.id),
            await self.get_entry(organization_id, correction.id),
        )

    async def _authorized_transition(
        self, function_name: str, *parameters: str
    ) -> None:
        if self.session.bind and self.session.bind.dialect.name == "postgresql":
            if not settings.ACCOUNTING_POSTING_TOKEN:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Accounting posting authorization is not configured",
                )
            await self.session.execute(
                text("SELECT set_config('fip.posting_token', :posting_token, true)"),
                {"posting_token": settings.ACCOUNTING_POSTING_TOKEN},
            )
            placeholders = ", ".join(
                f":value_{index}" for index in range(len(parameters))
            )
            await self.session.execute(
                text(f"SELECT {function_name}({placeholders})"),
                {f"value_{index}": value for index, value in enumerate(parameters)},
            )

    async def _validate_active_accounts(
        self, organization_id: str, data: JournalEntryCreate
    ) -> None:
        account_ids = {line.account_id for line in data.lines}
        active_accounts = await self.session.scalars(
            select(Account.id).where(
                Account.organization_id == organization_id,
                Account.id.in_(account_ids),
                Account.is_active.is_(True),
            )
        )
        if len(set(active_accounts)) != len(account_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="All entry accounts must exist and be active",
            )
