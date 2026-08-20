from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums.accounting import FiscalPeriodStatus
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.journal import Journal
from app.models.procurement import (
    ProcurementAccountingProfile,
    PurchaseInvoice,
    PurchaseInvoiceAccountingPosting,
    PurchaseInvoiceLine,
    Supplier,
    SupplierPayment,
    SupplierPaymentAccountingPosting,
)
from app.models.supplier_payment_allocation import SupplierPaymentAllocation
from app.repositories.procurement_repository import ProcurementRepository
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.schemas.procurement import (
    ProcurementAccountingProfileCreate,
    PurchaseInvoiceCreate,
    SupplierCreate,
    SupplierPaymentCreate,
)
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.audit.audit_service import AuditService


class ProcurementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProcurementRepository(session)
        self.entries = JournalEntryService(session)
        self.audit = AuditService(session)

    async def create_supplier(
        self, organization_id: str, actor_user_id: str, data: SupplierCreate
    ):
        supplier = Supplier(organization_id=organization_id, **data.model_dump())
        self.session.add(supplier)
        try:
            await self.session.flush()
            await self.audit.record(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="SUPPLIER_CREATED",
                resource_type="Supplier",
                resource_id=supplier.id,
                new_value={
                    "supplier_code": supplier.supplier_code,
                    "legal_name": supplier.legal_name,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier code already exists",
            ) from exc
        return supplier

    async def configure_profile(
        self,
        organization_id: str,
        actor_user_id: str,
        data: ProcurementAccountingProfileCreate,
    ):
        if await self.repo.profile(organization_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Procurement accounting profile already exists",
            )
        await self._validate_profile(organization_id, data)
        profile = ProcurementAccountingProfile(
            organization_id=organization_id, **data.model_dump()
        )
        self.session.add(profile)
        await self.session.flush()
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="PROCUREMENT_ACCOUNTING_PROFILE_CONFIGURED",
            resource_type="ProcurementAccountingProfile",
            resource_id=profile.id,
            new_value=data.model_dump(),
        )
        await self.session.commit()
        return profile

    async def create_invoice(
        self, organization_id: str, actor_user_id: str, data: PurchaseInvoiceCreate
    ):
        supplier = await self.repo.supplier(organization_id, data.supplier_id)
        if supplier is None or not supplier.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Active supplier not found",
            )
        subtotal = sum((line.line_subtotal for line in data.lines), Decimal("0.00"))
        tax_amount = sum((line.tax_amount for line in data.lines), Decimal("0.00"))
        invoice = PurchaseInvoice(
            organization_id=organization_id,
            supplier_id=data.supplier_id,
            invoice_number=data.invoice_number,
            invoice_date=data.invoice_date,
            due_date=data.due_date,
            currency=data.currency,
            notes=data.notes,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=subtotal + tax_amount,
        )
        self.session.add(invoice)
        await self.session.flush()
        for index, line in enumerate(data.lines, start=1):
            self.session.add(
                PurchaseInvoiceLine(
                    organization_id=organization_id,
                    invoice_id=invoice.id,
                    expense_account_id=line.expense_account_id,
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    tax_rate=line.tax_rate,
                    line_subtotal=line.line_subtotal,
                    tax_amount=line.tax_amount,
                    line_total=line.line_total,
                    sort_order=index,
                )
            )
        await self.session.flush()
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="PURCHASE_INVOICE_CREATED",
            resource_type="PurchaseInvoice",
            resource_id=invoice.id,
            new_value={
                "invoice_number": invoice.invoice_number,
                "total_amount": str(invoice.total_amount),
            },
        )
        await self.session.commit()
        return invoice

    async def validate_invoice(
        self, organization_id: str, actor_user_id: str, invoice_id: str
    ):
        invoice = await self.repo.invoice(organization_id, invoice_id, lock=True)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Purchase invoice not found")
        if invoice.status != "DRAFT":
            raise HTTPException(
                status_code=422, detail="Only draft purchase invoices can be validated"
            )
        if not invoice.lines:
            raise HTTPException(
                status_code=422, detail="Purchase invoice requires lines"
            )
        invoice.status = "VALIDATED"
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="PURCHASE_INVOICE_VALIDATED",
            resource_type="PurchaseInvoice",
            resource_id=invoice.id,
            previous_value={"status": "DRAFT"},
            new_value={"status": "VALIDATED"},
        )
        await self.session.commit()
        return invoice

    async def create_payment(
        self, organization_id: str, actor_user_id: str, data: SupplierPaymentCreate
    ):
        invoice = None
        if data.invoice_id is not None:
            invoice = await self.repo.invoice(
                organization_id, data.invoice_id, lock=True
            )
            if invoice is None:
                raise HTTPException(
                    status_code=404, detail="Purchase invoice not found"
                )
            if invoice.status not in {"VALIDATED", "PARTIALLY_PAID"}:
                raise HTTPException(
                    status_code=422, detail="Purchase invoice is not payable"
                )
            if (
                data.payment_date < invoice.invoice_date
                or data.amount > invoice.outstanding_amount
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Payment exceeds supplier invoice outstanding amount",
                )
        payment = SupplierPayment(organization_id=organization_id, **data.model_dump())
        if invoice is not None:
            invoice.paid_amount = Decimal(invoice.paid_amount) + data.amount
            invoice.status = (
                "PAID"
                if invoice.paid_amount == invoice.total_amount
                else "PARTIALLY_PAID"
            )
        self.session.add(payment)
        await self.session.flush()
        if invoice is not None:
            self.session.add(
                SupplierPaymentAllocation(
                    organization_id=organization_id,
                    payment_id=payment.id,
                    invoice_id=invoice.id,
                    supplier_id=invoice.supplier_id,
                    amount=data.amount,
                    idempotency_key=f"payment-{payment.id}-initial",
                    created_by_user_id=actor_user_id,
                )
            )
            await self.session.flush()
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="SUPPLIER_PAYMENT_CREATED",
            resource_type="SupplierPayment",
            resource_id=payment.id,
            new_value={"invoice_id": data.invoice_id, "amount": str(data.amount)},
        )
        await self.session.commit()
        return payment

    async def post_invoice(
        self,
        organization_id: str,
        actor_user_id: str,
        invoice_id: str,
        idempotency_key: str,
    ):
        key = idempotency_key.strip()
        if not key:
            raise HTTPException(
                status_code=422, detail="Idempotency-Key must not be blank"
            )
        invoice = await self.repo.invoice(organization_id, invoice_id, lock=True)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Purchase invoice not found")
        existing = await self.repo.invoice_posting(organization_id, invoice_id)
        if existing:
            return existing
        if await self.repo.posting_by_key(organization_id, key):
            raise HTTPException(
                status_code=409, detail="Idempotency-Key is already bound"
            )
        if invoice.status not in {"VALIDATED", "PARTIALLY_PAID", "PAID"}:
            raise HTTPException(
                status_code=422, detail="Only validated purchase invoices can be posted"
            )
        profile = await self.repo.profile(organization_id, lock=True)
        if profile is None or not profile.is_active:
            raise HTTPException(
                status_code=422,
                detail="Active procurement accounting profile is required",
            )
        await self._validate_profile(
            organization_id,
            ProcurementAccountingProfileCreate(
                journal_id=profile.journal_id,
                payable_account_id=profile.payable_account_id,
                deductible_vat_account_id=profile.deductible_vat_account_id,
                settlement_account_id=profile.settlement_account_id,
            ),
        )
        period = await self._period(organization_id, invoice.invoice_date)
        lines = []
        for item in invoice.lines:
            lines.append(
                JournalEntryLineCreate(
                    account_id=item.expense_account_id,
                    debit=Decimal(item.line_subtotal),
                    description=item.description,
                )
            )
        if Decimal(invoice.tax_amount) > 0:
            if not profile.deductible_vat_account_id:
                raise HTTPException(
                    status_code=422, detail="Deductible VAT account is required"
                )
            lines.append(
                JournalEntryLineCreate(
                    account_id=profile.deductible_vat_account_id,
                    debit=Decimal(invoice.tax_amount),
                    description=f"Deductible VAT {invoice.invoice_number}",
                )
            )
        lines.append(
            JournalEntryLineCreate(
                account_id=profile.payable_account_id,
                credit=Decimal(invoice.total_amount),
                description=f"Supplier payable {invoice.invoice_number}",
            )
        )
        entry = await self.entries._create_entry(
            organization_id,
            JournalEntryCreate(
                journal_id=profile.journal_id,
                fiscal_period_id=period.id,
                entry_number=f"PUR-{invoice.id[:20]}",
                entry_date=invoice.invoice_date,
                description=f"Supplier invoice {invoice.invoice_number}",
                reference=invoice.invoice_number,
                lines=lines,
            ),
            actor_user_id,
            commit=False,
        )
        posted = await self.entries.post_entry(
            organization_id, entry.id, actor_user_id, commit=False
        )
        posting = PurchaseInvoiceAccountingPosting(
            organization_id=organization_id,
            source_id=invoice.id,
            journal_entry_id=posted.id,
            idempotency_key=key,
        )
        self.session.add(posting)
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="PURCHASE_INVOICE_POSTED_TO_ACCOUNTING",
            resource_type="PurchaseInvoice",
            resource_id=invoice.id,
            new_value={"journal_entry_id": posted.id},
            transaction_id=posted.id,
            request_id=key,
        )
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.repo.invoice_posting(organization_id, invoice_id)
            if existing:
                return existing
            raise HTTPException(
                status_code=409, detail="Purchase invoice posting already exists"
            ) from exc
        return posting

    async def post_payment(
        self,
        organization_id: str,
        actor_user_id: str,
        payment_id: str,
        idempotency_key: str,
    ):
        key = idempotency_key.strip()
        if not key:
            raise HTTPException(
                status_code=422, detail="Idempotency-Key must not be blank"
            )
        payment = await self.repo.payment(organization_id, payment_id, lock=True)
        if payment is None:
            raise HTTPException(status_code=404, detail="Supplier payment not found")
        existing = await self.repo.payment_posting(organization_id, payment_id)
        if existing:
            return existing
        allocated_amount = Decimal(
            await self.session.scalar(
                select(
                    func.coalesce(func.sum(SupplierPaymentAllocation.amount), 0)
                ).where(
                    SupplierPaymentAllocation.organization_id == organization_id,
                    SupplierPaymentAllocation.payment_id == payment.id,
                )
            )
            or 0
        )
        if allocated_amount != Decimal(payment.amount):
            raise HTTPException(
                status_code=422,
                detail="Supplier payment must be fully allocated before posting",
            )
        if await self.repo.posting_by_key(organization_id, key):
            raise HTTPException(
                status_code=409, detail="Idempotency-Key is already bound"
            )
        profile = await self.repo.profile(organization_id, lock=True)
        if profile is None or not profile.is_active:
            raise HTTPException(
                status_code=422,
                detail="Active procurement accounting profile is required",
            )
        period = await self._period(organization_id, payment.payment_date)
        entry = await self.entries._create_entry(
            organization_id,
            JournalEntryCreate(
                journal_id=profile.journal_id,
                fiscal_period_id=period.id,
                entry_number=f"SUP-PAY-{payment.id[:20]}",
                entry_date=payment.payment_date,
                description=f"Supplier payment {payment.external_reference}",
                reference=payment.external_reference,
                lines=[
                    JournalEntryLineCreate(
                        account_id=profile.payable_account_id,
                        debit=Decimal(payment.amount),
                        description="Supplier payable settlement",
                    ),
                    JournalEntryLineCreate(
                        account_id=profile.settlement_account_id,
                        credit=Decimal(payment.amount),
                        description="Supplier bank settlement",
                    ),
                ],
            ),
            actor_user_id,
            commit=False,
        )
        posted = await self.entries.post_entry(
            organization_id, entry.id, actor_user_id, commit=False
        )
        posting = SupplierPaymentAccountingPosting(
            organization_id=organization_id,
            source_id=payment.id,
            journal_entry_id=posted.id,
            idempotency_key=key,
        )
        self.session.add(posting)
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="SUPPLIER_PAYMENT_POSTED_TO_ACCOUNTING",
            resource_type="SupplierPayment",
            resource_id=payment.id,
            new_value={"journal_entry_id": posted.id},
            transaction_id=posted.id,
            request_id=key,
        )
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            existing = await self.repo.payment_posting(organization_id, payment_id)
            if existing:
                return existing
            raise HTTPException(
                status_code=409, detail="Supplier payment posting already exists"
            ) from exc
        return posting

    async def _period(self, organization_id: str, value: date):
        period = await self.session.scalar(
            select(FiscalPeriod)
            .where(
                FiscalPeriod.organization_id == organization_id,
                FiscalPeriod.start_date <= value,
                FiscalPeriod.end_date >= value,
            )
            .with_for_update()
        )
        if period is None or period.status != FiscalPeriodStatus.OPEN:
            raise HTTPException(status_code=422, detail="Fiscal period is not open")
        return period

    async def _validate_profile(
        self, organization_id: str, data: ProcurementAccountingProfileCreate
    ):
        journal = await self.session.scalar(
            select(Journal).where(
                Journal.organization_id == organization_id,
                Journal.id == data.journal_id,
                Journal.is_active.is_(True),
            )
        )
        if journal is None:
            raise HTTPException(status_code=422, detail="Active journal is required")
        account_ids = [data.payable_account_id, data.settlement_account_id]
        expected = {
            data.payable_account_id: "LIABILITY",
            data.settlement_account_id: "ASSET",
        }
        if data.deductible_vat_account_id:
            account_ids.append(data.deductible_vat_account_id)
            expected[data.deductible_vat_account_id] = "ASSET"
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
        for account_id, account_type in expected.items():
            if (
                by_id.get(account_id) is None
                or by_id[account_id].account_type != account_type
            ):
                raise HTTPException(
                    status_code=422,
                    detail=f"Procurement profile requires active {account_type.lower()} accounts from this organization",
                )
