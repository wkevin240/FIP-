from decimal import Decimal

from app.core.enums.accounting import FiscalPeriodStatus
from app.models.accounting.account import Account
from app.models.accounting.bank_transaction import BankTransaction
from app.models.accounting.fiscal_period import FiscalPeriod
from app.repositories.accounting.journal_repository import JournalRepository
from app.repositories.treasury.bank_transaction_repository import (
    TreasuryBankTransactionRepository,
)
from app.repositories.treasury.treasury_accounting_repository import (
    TreasuryAccountingRepository,
)
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.schemas.treasury.accounting import (
    TreasuryAccountingProfileCreate,
    TreasuryTransactionPostingCreate,
)
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class TreasuryAccountingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.accounting = TreasuryAccountingRepository(session)
        self.transactions = TreasuryBankTransactionRepository(session)
        self.journals = JournalRepository(session)
        self.entries = JournalEntryService(session)
        self.audit = AuditService(session)

    async def get_profile(self, organization_id: str):
        profile = await self.accounting.get_profile(organization_id)
        if profile is None:
            raise HTTPException(
                status_code=404, detail="Treasury accounting profile not found"
            )
        return profile

    async def configure_profile(
        self,
        organization_id: str,
        actor_user_id: str,
        data: TreasuryAccountingProfileCreate,
    ):
        if await self.accounting.get_profile(organization_id, for_update=True):
            raise HTTPException(
                status_code=409, detail="Treasury accounting profile already exists"
            )
        await self._validate_journal(organization_id, data.journal_id)
        try:
            profile = await self.accounting.create_profile(
                organization_id, data.journal_id
            )
            await self.audit.record(
                organization_id,
                actor_user_id,
                "TREASURY_ACCOUNTING_PROFILE_CONFIGURED",
                "TreasuryAccountingProfile",
                profile.id,
                new_value={"journal_id": data.journal_id},
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=409, detail="Treasury accounting profile already exists"
            ) from exc
        return await self.get_profile(organization_id)

    async def post_transaction(
        self,
        organization_id: str,
        actor_user_id: str,
        transaction_id: str,
        data: TreasuryTransactionPostingCreate,
    ):
        transaction = await self.transactions.get_by_id(organization_id, transaction_id)
        if transaction is None:
            raise HTTPException(status_code=404, detail="Bank transaction not found")
        existing = await self.accounting.get_posting(organization_id, transaction.id)
        if existing is not None:
            return existing
        profile = await self.accounting.get_profile(organization_id, for_update=True)
        if profile is None:
            raise HTTPException(
                status_code=422,
                detail="Treasury accounting is not ready: profile is required",
            )
        await self._validate_journal(organization_id, profile.journal_id)
        bank, counterpart = await self._validate_accounts(
            organization_id, transaction, data.counterpart_account_id
        )
        period = await self._period(organization_id, transaction)
        amount = Decimal(transaction.amount)
        debit, credit = (
            (bank.id, counterpart.id) if amount > 0 else (counterpart.id, bank.id)
        )
        entry = await self.entries._create_entry(
            organization_id,
            JournalEntryCreate(
                journal_id=profile.journal_id,
                fiscal_period_id=period.id,
                entry_number=f"BNK-{transaction.id[:20]}",
                entry_date=transaction.transaction_date,
                description=transaction.description,
                reference=transaction.reference,
                lines=[
                    JournalEntryLineCreate(account_id=debit, debit=abs(amount)),
                    JournalEntryLineCreate(account_id=credit, credit=abs(amount)),
                ],
            ),
            actor_user_id,
            commit=False,
        )
        posted = await self.entries.post_entry(
            organization_id, entry.id, actor_user_id, commit=False
        )
        try:
            await self.accounting.create_posting(
                organization_id, transaction.id, posted.id, counterpart.id
            )
            await self.audit.record(
                organization_id,
                actor_user_id,
                "TREASURY_TRANSACTION_POSTED_TO_ACCOUNTING",
                "BankTransaction",
                transaction.id,
                new_value={
                    "journal_entry_id": posted.id,
                    "counterpart_account_id": counterpart.id,
                    "amount": str(amount),
                },
                transaction_id=posted.id,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.accounting.get_posting(
                organization_id, transaction.id
            )
            if existing is not None:
                return existing
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Treasury accounting posting already exists",
            ) from exc
        return await self.accounting.get_posting(organization_id, transaction.id)

    async def _validate_journal(self, organization_id: str, journal_id: str) -> None:
        journal = await self.journals.get_by_id(organization_id, journal_id)
        if journal is None or not journal.is_active:
            raise HTTPException(status_code=422, detail="Active journal not found")

    async def _validate_accounts(
        self, organization_id: str, transaction: BankTransaction, counterpart_id: str
    ):
        accounts = list(
            await self.session.scalars(
                select(Account).where(
                    Account.organization_id == organization_id,
                    Account.id.in_([transaction.bank_account_id, counterpart_id]),
                    Account.is_active.is_(True),
                )
            )
        )
        by_id = {account.id: account for account in accounts}
        bank = by_id.get(transaction.bank_account_id)
        counterpart = by_id.get(counterpart_id)
        if bank is None or bank.account_type != "ASSET":
            raise HTTPException(
                status_code=422, detail="Active treasury bank asset account not found"
            )
        if counterpart is None or counterpart.id == bank.id:
            raise HTTPException(
                status_code=422,
                detail="Active distinct counterpart account is required",
            )
        return bank, counterpart

    async def _period(
        self, organization_id: str, transaction: BankTransaction
    ) -> FiscalPeriod:
        period = await self.session.scalar(
            select(FiscalPeriod)
            .where(
                FiscalPeriod.organization_id == organization_id,
                FiscalPeriod.start_date <= transaction.transaction_date,
                FiscalPeriod.end_date >= transaction.transaction_date,
            )
            .with_for_update()
        )
        if period is None or period.status != FiscalPeriodStatus.OPEN:
            raise HTTPException(status_code=422, detail="Fiscal period is not open")
        return period
