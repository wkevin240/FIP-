from datetime import date
from decimal import Decimal

import pytest
from app.core.enums.accounting import FiscalPeriodStatus
from app.core.enums.invoicing import PaymentMethod
from app.models.accounting.account import Account
from app.models.accounting.journal_entry import JournalEntry
from app.models.audit.audit_event import AuditEvent
from app.models.invoicing.accounting import InvoiceAccountingProfile
from app.models.invoicing.settlement_accounting import (
    CreditNoteAccountingPosting,
    PaymentAccountingPosting,
)
from app.schemas.invoicing.credit_note import CreditNoteCreate
from app.schemas.invoicing.payment import PaymentCreate
from app.schemas.invoicing.settlement_accounting import PaymentPostingCreate
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.accounting.reporting_service import ReportingService
from app.services.invoicing.credit_note_service import CreditNoteService
from app.services.invoicing.payment_service import PaymentService
from app.services.invoicing.settlement_accounting_service import (
    SettlementAccountingService,
)
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.integration.invoicing.test_invoice_accounting_service import (
    _create_accounting_context,
    _create_issued_invoice,
)


async def _create_settlement_account(
    session: AsyncSession, organization_id: str, code: str
) -> Account:
    account = Account(
        organization_id=organization_id,
        code=code,
        name=f"Settlement account {code}",
        account_type="ASSET",
        level=1,
        path=f"/{code}/",
    )
    session.add(account)
    await session.commit()
    return account


@pytest.mark.asyncio
async def test_credit_note_posts_balanced_decimal_entry_idempotently(
    db_session: AsyncSession,
) -> None:
    organization, vat_rate, _ = await _create_accounting_context(db_session)
    invoice = await _create_issued_invoice(db_session, organization, vat_rate.id)
    credit = await CreditNoteService(db_session).create_credit_note(
        organization.id,
        CreditNoteCreate(
            invoice_id=invoice.id,
            credit_note_number="CN-SETTLEMENT-001",
            credit_date=date(2026, 2, 20),
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("18.00"),
            amount=Decimal("118.00"),
            reason="Validated commercial credit",
        ),
    )
    service = SettlementAccountingService(db_session)
    first = await service.post_credit_note(
        organization.id, "settlement-tester", credit.id, "credit-post-001"
    )
    again = await service.post_credit_note(
        organization.id, "settlement-tester", credit.id, "credit-post-002"
    )

    assert first.id == again.id
    entry = await JournalEntryService(db_session).get_entry(
        organization.id, first.journal_entry_id
    )
    assert entry is not None and entry.status.value == "POSTED"
    assert sum(
        (Decimal(line.debit) for line in entry.lines), Decimal("0.00")
    ) == Decimal("118.00")
    assert sum(
        (Decimal(line.credit) for line in entry.lines), Decimal("0.00")
    ) == Decimal("118.00")
    assert (
        await db_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization.id,
                AuditEvent.action == "CREDIT_NOTE_POSTED_TO_ACCOUNTING",
                AuditEvent.resource_id == credit.id,
            )
        )
        == 1
    )


@pytest.mark.asyncio
async def test_partial_payment_posts_to_real_settlement_account_idempotently(
    db_session: AsyncSession,
) -> None:
    organization, vat_rate, _ = await _create_accounting_context(db_session)
    invoice = await _create_issued_invoice(db_session, organization, vat_rate.id)
    settlement_account = await _create_settlement_account(
        db_session, organization.id, "512SETTLEMENT"
    )
    payment = await PaymentService(db_session).create_payment(
        organization.id,
        PaymentCreate(
            invoice_id=invoice.id,
            payment_date=date(2026, 2, 20),
            amount=Decimal("50.00"),
            method=PaymentMethod.BANK_TRANSFER,
            external_reference="PAY-SETTLEMENT-001",
        ),
    )
    service = SettlementAccountingService(db_session)
    first = await service.post_payment(
        organization.id,
        "settlement-tester",
        payment.id,
        "payment-post-001",
        PaymentPostingCreate(settlement_account_id=settlement_account.id),
    )
    again = await service.post_payment(
        organization.id,
        "settlement-tester",
        payment.id,
        "payment-post-002",
        PaymentPostingCreate(settlement_account_id=settlement_account.id),
    )

    assert first.id == again.id
    entry = await JournalEntryService(db_session).get_entry(
        organization.id, first.journal_entry_id
    )
    assert entry is not None
    assert sum(
        (Decimal(line.debit) for line in entry.lines), Decimal("0.00")
    ) == Decimal("50.00")
    assert sum(
        (Decimal(line.credit) for line in entry.lines), Decimal("0.00")
    ) == Decimal("50.00")
    assert (
        await db_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization.id,
                AuditEvent.action == "PAYMENT_POSTED_TO_ACCOUNTING",
                AuditEvent.resource_id == payment.id,
            )
        )
        == 1
    )


@pytest.mark.asyncio
async def test_credit_note_partial_excess_closed_period_missing_profile_and_tenant_scope(
    db_session: AsyncSession,
) -> None:
    organization, vat_rate, _ = await _create_accounting_context(db_session)
    invoice = await _create_issued_invoice(db_session, organization, vat_rate.id)
    credit_service = CreditNoteService(db_session)
    settlement_service = SettlementAccountingService(db_session)
    partial_credit = await credit_service.create_credit_note(
        organization.id,
        CreditNoteCreate(
            invoice_id=invoice.id,
            credit_note_number="CN-PARTIAL-001",
            credit_date=date(2026, 2, 20),
            subtotal=Decimal("50.00"),
            tax_amount=Decimal("9.00"),
            amount=Decimal("59.00"),
            reason="Partial credit",
        ),
    )
    partial_credit_id = partial_credit.id
    partial_credit_subtotal = Decimal(partial_credit.subtotal)
    partial_credit_tax_amount = Decimal(partial_credit.tax_amount)
    partial_credit_amount = Decimal(partial_credit.amount)
    partial_posting = await settlement_service.post_credit_note(
        organization.id,
        "settlement-tester",
        partial_credit.id,
        "credit-partial-post-001",
    )
    assert partial_posting.source_id == partial_credit_id
    assert partial_credit_subtotal + partial_credit_tax_amount == partial_credit_amount

    with pytest.raises(HTTPException, match="exceeds invoice outstanding") as excessive:
        await credit_service.create_credit_note(
            organization.id,
            CreditNoteCreate(
                invoice_id=invoice.id,
                credit_note_number="CN-EXCESS-001",
                credit_date=date(2026, 2, 20),
                subtotal=Decimal("50.01"),
                tax_amount=Decimal("9.00"),
                amount=Decimal("59.01"),
                reason="Excess credit must be rejected",
            ),
        )
    assert excessive.value.status_code == 422

    other_organization, _, _ = await _create_accounting_context(db_session)
    with pytest.raises(HTTPException, match="Credit note not found") as cross_tenant:
        await SettlementAccountingService(db_session).post_credit_note(
            other_organization.id,
            "settlement-tester",
            partial_credit_id,
            "credit-cross-tenant-001",
        )
    assert cross_tenant.value.status_code == 404

    closed_organization, closed_vat_rate, _ = await _create_accounting_context(
        db_session, fiscal_period_status=FiscalPeriodStatus.CLOSED
    )
    closed_invoice = await _create_issued_invoice(
        db_session, closed_organization, closed_vat_rate.id
    )
    closed_credit = await credit_service.create_credit_note(
        closed_organization.id,
        CreditNoteCreate(
            invoice_id=closed_invoice.id,
            credit_note_number="CN-CLOSED-001",
            credit_date=date(2026, 2, 20),
            subtotal=Decimal("10.00"),
            tax_amount=Decimal("1.80"),
            amount=Decimal("11.80"),
            reason="Closed period control",
        ),
    )
    with pytest.raises(HTTPException, match="Fiscal period is not open") as closed:
        await SettlementAccountingService(db_session).post_credit_note(
            closed_organization.id,
            "settlement-tester",
            closed_credit.id,
            "credit-closed-period-001",
        )
    assert closed.value.status_code == 422
    assert (
        await db_session.scalar(
            select(func.count(CreditNoteAccountingPosting.id)).where(
                CreditNoteAccountingPosting.organization_id == closed_organization.id
            )
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.organization_id == closed_organization.id
            )
        )
        == 0
    )

    missing_organization, missing_vat_rate, _ = await _create_accounting_context(
        db_session
    )
    missing_invoice = await _create_issued_invoice(
        db_session, missing_organization, missing_vat_rate.id
    )
    missing_credit = await credit_service.create_credit_note(
        missing_organization.id,
        CreditNoteCreate(
            invoice_id=missing_invoice.id,
            credit_note_number="CN-NO-PROFILE-001",
            credit_date=date(2026, 2, 20),
            subtotal=Decimal("10.00"),
            tax_amount=Decimal("1.80"),
            amount=Decimal("11.80"),
            reason="Profile is intentionally disabled",
        ),
    )
    profile = await db_session.scalar(
        select(InvoiceAccountingProfile).where(
            InvoiceAccountingProfile.organization_id == missing_organization.id
        )
    )
    assert profile is not None
    profile.is_active = False
    await db_session.commit()
    with pytest.raises(
        HTTPException, match="Active invoice accounting profile"
    ) as absent:
        await SettlementAccountingService(db_session).post_credit_note(
            missing_organization.id,
            "settlement-tester",
            missing_credit.id,
            "credit-missing-profile-001",
        )
    assert absent.value.status_code == 422
    assert (
        await db_session.scalar(
            select(func.count(CreditNoteAccountingPosting.id)).where(
                CreditNoteAccountingPosting.organization_id == missing_organization.id
            )
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.organization_id == missing_organization.id
            )
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == missing_organization.id,
                AuditEvent.action == "CREDIT_NOTE_POSTED_TO_ACCOUNTING",
            )
        )
        == 0
    )


@pytest.mark.asyncio
async def test_total_multiple_payments_and_missing_profile_rollback(
    db_session: AsyncSession,
) -> None:
    organization, vat_rate, _ = await _create_accounting_context(db_session)
    settlement_account = await _create_settlement_account(
        db_session, organization.id, "512PAYMENTS"
    )
    payment_service = PaymentService(db_session)
    settlement_service = SettlementAccountingService(db_session)

    fully_paid_invoice = await _create_issued_invoice(
        db_session, organization, vat_rate.id
    )
    full_payment = await payment_service.create_payment(
        organization.id,
        PaymentCreate(
            invoice_id=fully_paid_invoice.id,
            payment_date=date(2026, 2, 20),
            amount=Decimal("118.00"),
            method=PaymentMethod.BANK_TRANSFER,
            external_reference="PAY-TOTAL-001",
        ),
    )
    full_posting = await settlement_service.post_payment(
        organization.id,
        "settlement-tester",
        full_payment.id,
        "payment-total-post-001",
        PaymentPostingCreate(settlement_account_id=settlement_account.id),
    )

    multi_paid_invoice = await _create_issued_invoice(
        db_session, organization, vat_rate.id
    )
    first_payment = await payment_service.create_payment(
        organization.id,
        PaymentCreate(
            invoice_id=multi_paid_invoice.id,
            payment_date=date(2026, 2, 20),
            amount=Decimal("50.00"),
            method=PaymentMethod.BANK_TRANSFER,
            external_reference="PAY-MULTI-001",
        ),
    )
    second_payment = await payment_service.create_payment(
        organization.id,
        PaymentCreate(
            invoice_id=multi_paid_invoice.id,
            payment_date=date(2026, 2, 20),
            amount=Decimal("68.00"),
            method=PaymentMethod.BANK_TRANSFER,
            external_reference="PAY-MULTI-002",
        ),
    )
    first_posting = await settlement_service.post_payment(
        organization.id,
        "settlement-tester",
        first_payment.id,
        "payment-multi-post-001",
        PaymentPostingCreate(settlement_account_id=settlement_account.id),
    )
    second_posting = await settlement_service.post_payment(
        organization.id,
        "settlement-tester",
        second_payment.id,
        "payment-multi-post-002",
        PaymentPostingCreate(settlement_account_id=settlement_account.id),
    )
    assert len({full_posting.id, first_posting.id, second_posting.id}) == 3
    assert (
        await db_session.scalar(
            select(func.count(PaymentAccountingPosting.id)).where(
                PaymentAccountingPosting.organization_id == organization.id,
                PaymentAccountingPosting.source_id.in_(
                    [full_payment.id, first_payment.id, second_payment.id]
                ),
            )
        )
        == 3
    )

    blocked_invoice = await _create_issued_invoice(
        db_session, organization, vat_rate.id
    )
    blocked_payment = await payment_service.create_payment(
        organization.id,
        PaymentCreate(
            invoice_id=blocked_invoice.id,
            payment_date=date(2026, 2, 20),
            amount=Decimal("1.00"),
            method=PaymentMethod.BANK_TRANSFER,
            external_reference="PAY-NO-PROFILE-001",
        ),
    )
    profile = await db_session.scalar(
        select(InvoiceAccountingProfile).where(
            InvoiceAccountingProfile.organization_id == organization.id
        )
    )
    assert profile is not None
    profile.is_active = False
    await db_session.commit()
    with pytest.raises(
        HTTPException, match="Active invoice accounting profile"
    ) as absent:
        await settlement_service.post_payment(
            organization.id,
            "settlement-tester",
            blocked_payment.id,
            "payment-missing-profile-001",
            PaymentPostingCreate(settlement_account_id=settlement_account.id),
        )
    assert absent.value.status_code == 422
    assert (
        await db_session.scalar(
            select(func.count(PaymentAccountingPosting.id)).where(
                PaymentAccountingPosting.organization_id == organization.id,
                PaymentAccountingPosting.source_id == blocked_payment.id,
            )
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization.id,
                AuditEvent.action == "PAYMENT_POSTED_TO_ACCOUNTING",
                AuditEvent.resource_id == blocked_payment.id,
            )
        )
        == 0
    )


@pytest.mark.asyncio
async def test_reconciles_invoice_credit_payment_and_accounting_in_decimal(
    db_session: AsyncSession,
) -> None:
    organization, vat_rate, invoice_accounting = await _create_accounting_context(
        db_session
    )
    settlement_account = await _create_settlement_account(
        db_session, organization.id, "512RECONCILIATION"
    )
    invoice = await _create_issued_invoice(db_session, organization, vat_rate.id)
    invoice_posting = await invoice_accounting.post_invoice(
        organization.id, "settlement-tester", invoice.id, "invoice-reconcile-001"
    )
    credit = await CreditNoteService(db_session).create_credit_note(
        organization.id,
        CreditNoteCreate(
            invoice_id=invoice.id,
            credit_note_number="CN-RECONCILIATION-001",
            credit_date=date(2026, 2, 20),
            subtotal=Decimal("50.00"),
            tax_amount=Decimal("9.00"),
            amount=Decimal("59.00"),
            reason="Reconciliation credit",
        ),
    )
    credit_posting = await SettlementAccountingService(db_session).post_credit_note(
        organization.id,
        "settlement-tester",
        credit.id,
        "credit-reconcile-001",
    )
    payment = await PaymentService(db_session).create_payment(
        organization.id,
        PaymentCreate(
            invoice_id=invoice.id,
            payment_date=date(2026, 2, 20),
            amount=Decimal("59.00"),
            method=PaymentMethod.BANK_TRANSFER,
            external_reference="PAY-RECONCILIATION-001",
        ),
    )
    payment_posting = await SettlementAccountingService(db_session).post_payment(
        organization.id,
        "settlement-tester",
        payment.id,
        "payment-reconcile-001",
        PaymentPostingCreate(settlement_account_id=settlement_account.id),
    )
    assert Decimal(credit.subtotal) + Decimal(credit.tax_amount) == Decimal(
        credit.amount
    )

    entry_ids = [
        invoice_posting.journal_entry_id,
        credit_posting.journal_entry_id,
        payment_posting.journal_entry_id,
    ]
    entries = [
        await JournalEntryService(db_session).get_entry(organization.id, entry_id)
        for entry_id in entry_ids
    ]
    assert all(
        entry is not None and entry.status.value == "POSTED" for entry in entries
    )
    debit_total = sum(
        (Decimal(line.debit) for entry in entries for line in entry.lines),
        Decimal("0.00"),
    )
    credit_total = sum(
        (Decimal(line.credit) for entry in entries for line in entry.lines),
        Decimal("0.00"),
    )
    assert debit_total == credit_total == Decimal("236.00")
    credit_entry = entries[1]
    payment_entry = entries[2]
    assert sum(
        (Decimal(line.debit) for line in credit_entry.lines), Decimal("0.00")
    ) == Decimal("59.00")
    assert sum(
        (Decimal(line.credit) for line in credit_entry.lines), Decimal("0.00")
    ) == Decimal("59.00")
    assert sum(
        (Decimal(line.debit) for line in payment_entry.lines), Decimal("0.00")
    ) == Decimal("59.00")
    assert sum(
        (Decimal(line.credit) for line in payment_entry.lines), Decimal("0.00")
    ) == Decimal("59.00")
    assert (
        await db_session.scalar(
            select(func.count(CreditNoteAccountingPosting.id)).where(
                CreditNoteAccountingPosting.organization_id == organization.id,
                CreditNoteAccountingPosting.source_id == credit.id,
                CreditNoteAccountingPosting.journal_entry_id
                == credit_posting.journal_entry_id,
            )
        )
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count(PaymentAccountingPosting.id)).where(
                PaymentAccountingPosting.organization_id == organization.id,
                PaymentAccountingPosting.source_id == payment.id,
                PaymentAccountingPosting.journal_entry_id
                == payment_posting.journal_entry_id,
            )
        )
        == 1
    )
    trial_balance = await ReportingService(db_session).trial_balance(
        organization.id, date(2026, 2, 20), date(2026, 2, 1)
    )
    assert trial_balance.is_balanced is True
    assert trial_balance.total_debit == Decimal("236.00")
    assert trial_balance.total_credit == Decimal("236.00")
