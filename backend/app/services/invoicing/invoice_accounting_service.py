from decimal import Decimal

from app.core.enums.accounting import FiscalPeriodStatus
from app.core.enums.invoicing import InvoiceStatus
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.invoicing.invoice import Invoice
from app.repositories.accounting.journal_repository import JournalRepository
from app.repositories.invoicing.invoice_accounting_repository import (
    InvoiceAccountingRepository,
)
from app.repositories.invoicing.invoice_repository import InvoiceRepository
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.schemas.invoicing.accounting import InvoiceAccountingProfileCreate
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class InvoiceAccountingService:
    """Posts issued invoices through the protected Accounting service."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.invoices = InvoiceRepository(session)
        self.accounting = InvoiceAccountingRepository(session)
        self.journals = JournalRepository(session)
        self.journal_entries = JournalEntryService(session)
        self.audit = AuditService(session)

    async def get_profile(self, organization_id: str):
        profile = await self.accounting.get_profile(organization_id)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice accounting profile not found",
            )
        return profile

    async def configure_profile(
        self,
        organization_id: str,
        actor_user_id: str,
        data: InvoiceAccountingProfileCreate,
    ):
        existing = await self.accounting.get_profile(organization_id, for_update=True)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invoice accounting profile already exists",
            )
        await self._validate_profile_accounts(organization_id, data)
        try:
            profile = await self.accounting.create_profile(
                organization_id, data.model_dump()
            )
            await self.audit.record(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="INVOICE_ACCOUNTING_PROFILE_CONFIGURED",
                resource_type="InvoiceAccountingProfile",
                resource_id=profile.id,
                new_value={
                    "journal_id": profile.journal_id,
                    "receivable_account_id": profile.receivable_account_id,
                    "revenue_account_id": profile.revenue_account_id,
                    "collected_vat_account_id": profile.collected_vat_account_id,
                    "is_active": profile.is_active,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invoice accounting profile already exists",
            ) from exc
        return await self.get_profile(organization_id)

    async def post_invoice(
        self,
        organization_id: str,
        actor_user_id: str,
        invoice_id: str,
        idempotency_key: str,
    ):
        normalized_key = idempotency_key.strip()
        if not normalized_key:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Idempotency-Key must not be blank",
            )
        invoice = await self.invoices.get_for_update(organization_id, invoice_id)
        if invoice is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
            )
        existing_posting = await self.accounting.get_posting_by_invoice(
            organization_id, invoice.id
        )
        if existing_posting is not None:
            return existing_posting
        key_posting = await self.accounting.get_posting_by_idempotency_key(
            organization_id, normalized_key
        )
        if key_posting is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key is already bound to another invoice posting",
            )
        if invoice.status == InvoiceStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Cancelled invoices cannot be posted",
            )
        if invoice.status != InvoiceStatus.ISSUED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only issued invoices can be posted",
            )
        if Decimal(invoice.total_amount) <= Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only invoices with a positive total can be posted",
            )
        profile = await self.accounting.get_profile(organization_id, for_update=True)
        if profile is None or not profile.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Invoice accounting is not ready: active profile is required",
            )
        await self._validate_stored_profile(organization_id, profile)
        period = await self._period_for_invoice(organization_id, invoice)
        entry = await self.journal_entries._create_entry(
            organization_id,
            self._entry_data(invoice, profile, period.id),
            actor_user_id,
            commit=False,
        )
        posted_entry = await self.journal_entries.post_entry(
            organization_id, entry.id, actor_user_id, commit=False
        )
        try:
            posting = await self.accounting.create_posting(
                organization_id,
                invoice.id,
                posted_entry.id,
                normalized_key,
            )
            await self.audit.record(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="INVOICE_POSTED_TO_ACCOUNTING",
                resource_type="Invoice",
                resource_id=invoice.id,
                previous_value={"status": InvoiceStatus.ISSUED.value},
                new_value={
                    "status": InvoiceStatus.ISSUED.value,
                    "journal_entry_id": posted_entry.id,
                    "posting_id": posting.id,
                    "source_module": posting.source_module,
                    "source_type": posting.source_type,
                    "source_id": posting.source_id,
                },
                transaction_id=posted_entry.id,
                request_id=normalized_key,
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.accounting.get_posting_by_invoice(
                organization_id, invoice.id
            )
            if existing is not None:
                return existing
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invoice accounting posting already exists",
            ) from exc
        return await self.accounting.get_posting_by_invoice(organization_id, invoice.id)

    async def _validate_profile_accounts(
        self, organization_id: str, data: InvoiceAccountingProfileCreate
    ) -> None:
        journal = await self.journals.get_by_id(organization_id, data.journal_id)
        if journal is None or not journal.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Active journal not found",
            )
        await self._validate_accounts(
            organization_id,
            data.receivable_account_id,
            data.revenue_account_id,
            data.collected_vat_account_id,
        )

    async def _validate_stored_profile(self, organization_id: str, profile) -> None:
        journal = await self.journals.get_by_id(organization_id, profile.journal_id)
        if journal is None or not journal.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Invoice accounting is not ready: active journal is required",
            )
        await self._validate_accounts(
            organization_id,
            profile.receivable_account_id,
            profile.revenue_account_id,
            profile.collected_vat_account_id,
        )

    async def _validate_accounts(
        self,
        organization_id: str,
        receivable_account_id: str,
        revenue_account_id: str,
        collected_vat_account_id: str | None,
    ) -> None:
        account_ids = [receivable_account_id, revenue_account_id]
        if collected_vat_account_id is not None:
            account_ids.append(collected_vat_account_id)
        accounts = list(
            await self.session.scalars(
                select(Account).where(
                    Account.organization_id == organization_id,
                    Account.id.in_(account_ids),
                    Account.is_active.is_(True),
                )
            )
        )
        by_id = {account.id: account for account in accounts}
        expected_types = {
            receivable_account_id: "ASSET",
            revenue_account_id: "REVENUE",
        }
        if collected_vat_account_id is not None:
            expected_types[collected_vat_account_id] = "LIABILITY"
        for account_id, expected_type in expected_types.items():
            account = by_id.get(account_id)
            if account is None or account.account_type != expected_type:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        "Invoice accounting profile requires active "
                        f"{expected_type.lower()} accounts from this organization"
                    ),
                )

    async def _period_for_invoice(
        self, organization_id: str, invoice: Invoice
    ) -> FiscalPeriod:
        period = await self.session.scalar(
            select(FiscalPeriod)
            .where(
                FiscalPeriod.organization_id == organization_id,
                FiscalPeriod.start_date <= invoice.invoice_date,
                FiscalPeriod.end_date >= invoice.invoice_date,
            )
            .with_for_update()
        )
        if period is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Invoice accounting is not ready: fiscal period not found",
            )
        if period.status != FiscalPeriodStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Fiscal period is not open",
            )
        return period

    @staticmethod
    def _entry_data(
        invoice: Invoice, profile, fiscal_period_id: str
    ) -> JournalEntryCreate:
        receivable = Decimal(invoice.total_amount)
        revenue = Decimal(invoice.subtotal)
        vat = Decimal(invoice.tax_amount)
        lines = [
            JournalEntryLineCreate(
                account_id=profile.receivable_account_id,
                debit=receivable,
                description=f"Receivable for invoice {invoice.invoice_number}",
            ),
            JournalEntryLineCreate(
                account_id=profile.revenue_account_id,
                credit=revenue,
                description=f"Revenue for invoice {invoice.invoice_number}",
            ),
        ]
        if vat > Decimal("0.00"):
            if profile.collected_vat_account_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Invoice accounting is not ready: collected VAT account is required",
                )
            lines.append(
                JournalEntryLineCreate(
                    account_id=profile.collected_vat_account_id,
                    credit=vat,
                    description=f"Collected VAT for invoice {invoice.invoice_number}",
                )
            )
        return JournalEntryCreate(
            journal_id=profile.journal_id,
            fiscal_period_id=fiscal_period_id,
            entry_number=f"INV-{invoice.id[:20]}",
            entry_date=invoice.invoice_date,
            description=f"Invoice {invoice.invoice_number}",
            reference=invoice.invoice_number,
            lines=lines,
        )
