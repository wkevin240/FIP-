from decimal import Decimal

from app.core.enums.accounting import FiscalPeriodStatus
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.invoicing.credit_note import CreditNote
from app.models.invoicing.payment import Payment
from app.models.invoicing.payment_allocation import PaymentAllocation
from app.repositories.invoicing.invoice_accounting_repository import (
    InvoiceAccountingRepository,
)
from app.repositories.invoicing.settlement_accounting_repository import (
    SettlementAccountingRepository,
)
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.schemas.invoicing.settlement_accounting import PaymentPostingCreate
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class SettlementAccountingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.profile = InvoiceAccountingRepository(session)
        self.links = SettlementAccountingRepository(session)
        self.entries = JournalEntryService(session)
        self.audit = AuditService(session)

    async def post_credit_note(
        self, organization_id: str, actor_id: str, credit_note_id: str, key: str
    ):
        credit = await self.session.scalar(
            select(CreditNote)
            .where(
                CreditNote.organization_id == organization_id,
                CreditNote.id == credit_note_id,
            )
            .with_for_update()
        )
        if credit is None:
            raise HTTPException(status_code=404, detail="Credit note not found")
        existing = await self.links.credit_posting(organization_id, credit.id)
        if existing:
            return existing
        profile, period = await self._profile_period(
            organization_id, credit.credit_date
        )
        if Decimal(credit.amount) != Decimal(credit.subtotal) + Decimal(
            credit.tax_amount
        ):
            raise HTTPException(
                status_code=422, detail="Credit note HT plus VAT must equal total"
            )
        lines = [
            JournalEntryLineCreate(
                account_id=profile.revenue_account_id, debit=Decimal(credit.subtotal)
            ),
            JournalEntryLineCreate(
                account_id=profile.receivable_account_id, credit=Decimal(credit.amount)
            ),
        ]
        if Decimal(credit.tax_amount) > 0:
            if not profile.collected_vat_account_id:
                raise HTTPException(
                    status_code=422, detail="Collected VAT account is required"
                )
            lines.append(
                JournalEntryLineCreate(
                    account_id=profile.collected_vat_account_id,
                    debit=Decimal(credit.tax_amount),
                )
            )
        entry = await self.entries._create_entry(
            organization_id,
            JournalEntryCreate(
                journal_id=profile.journal_id,
                fiscal_period_id=period.id,
                entry_number=f"CN-{credit.id[:20]}",
                entry_date=credit.credit_date,
                description=f"Credit note {credit.credit_note_number}",
                reference=credit.credit_note_number,
                lines=lines,
            ),
            actor_id,
            commit=False,
        )
        posted = await self.entries.post_entry(
            organization_id, entry.id, actor_id, commit=False
        )
        try:
            await self.links.create_credit_posting(
                organization_id, credit.id, posted.id, key
            )
            await self.audit.record(
                organization_id,
                actor_id,
                "CREDIT_NOTE_POSTED_TO_ACCOUNTING",
                "CreditNote",
                credit.id,
                new_value={"journal_entry_id": posted.id},
                transaction_id=posted.id,
                request_id=key,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.links.credit_posting(organization_id, credit.id)
            if existing:
                return existing
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Credit note accounting posting exists",
            ) from exc
        return await self.links.credit_posting(organization_id, credit.id)

    async def post_payment(
        self,
        organization_id: str,
        actor_id: str,
        payment_id: str,
        key: str,
        data: PaymentPostingCreate,
    ):
        payment = await self.session.scalar(
            select(Payment)
            .where(Payment.organization_id == organization_id, Payment.id == payment_id)
            .with_for_update()
        )
        if payment is None:
            raise HTTPException(status_code=404, detail="Payment not found")
        allocated_amount = Decimal(
            await self.session.scalar(
                select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
                    PaymentAllocation.organization_id == organization_id,
                    PaymentAllocation.payment_id == payment.id,
                )
            )
            or 0
        )
        if allocated_amount <= 0:
            raise HTTPException(
                status_code=422,
                detail="Payment must be allocated before accounting posting",
            )
        existing = await self.links.payment_posting(organization_id, payment.id)
        if existing:
            return existing
        profile, period = await self._profile_period(
            organization_id, payment.payment_date
        )
        account = await self.session.scalar(
            select(Account).where(
                Account.organization_id == organization_id,
                Account.id == data.settlement_account_id,
                Account.is_active.is_(True),
            )
        )
        if account is None or account.id == profile.receivable_account_id:
            raise HTTPException(
                status_code=422, detail="Active distinct settlement account is required"
            )
        entry = await self.entries._create_entry(
            organization_id,
            JournalEntryCreate(
                journal_id=profile.journal_id,
                fiscal_period_id=period.id,
                entry_number=f"PAY-{payment.id[:19]}",
                entry_date=payment.payment_date,
                description=f"Payment {payment.external_reference or payment.id}",
                reference=payment.external_reference,
                lines=[
                    JournalEntryLineCreate(
                        account_id=account.id, debit=Decimal(payment.amount)
                    ),
                    JournalEntryLineCreate(
                        account_id=profile.receivable_account_id,
                        credit=Decimal(payment.amount),
                    ),
                ],
            ),
            actor_id,
            commit=False,
        )
        posted = await self.entries.post_entry(
            organization_id, entry.id, actor_id, commit=False
        )
        try:
            await self.links.create_payment_posting(
                organization_id, payment.id, posted.id, account.id, key
            )
            await self.audit.record(
                organization_id,
                actor_id,
                "PAYMENT_POSTED_TO_ACCOUNTING",
                "Payment",
                payment.id,
                new_value={"journal_entry_id": posted.id},
                transaction_id=posted.id,
                request_id=key,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.links.payment_posting(organization_id, payment.id)
            if existing:
                return existing
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment accounting posting exists",
            ) from exc
        return await self.links.payment_posting(organization_id, payment.id)

    async def _profile_period(self, organization_id: str, event_date):
        profile = await self.profile.get_profile(organization_id, for_update=True)
        if profile is None or not profile.is_active:
            raise HTTPException(
                status_code=422, detail="Active invoice accounting profile is required"
            )
        period = await self.session.scalar(
            select(FiscalPeriod)
            .where(
                FiscalPeriod.organization_id == organization_id,
                FiscalPeriod.start_date <= event_date,
                FiscalPeriod.end_date >= event_date,
            )
            .with_for_update()
        )
        if period is None or period.status != FiscalPeriodStatus.OPEN:
            raise HTTPException(status_code=422, detail="Fiscal period is not open")
        return profile, period
