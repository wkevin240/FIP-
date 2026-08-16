from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.core.enums.invoicing import InvoiceStatus
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.journal import Journal
from app.models.accounting.journal_entry import JournalEntry
from app.models.accounting.vat import VATRate
from app.models.audit.audit_event import AuditEvent
from app.models.invoicing.accounting import InvoiceAccountingPosting
from app.models.organization import Organization
from app.schemas.invoicing.accounting import InvoiceAccountingProfileCreate
from app.schemas.invoicing.invoice import InvoiceCreate, InvoiceLineCreate
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.accounting.reporting_service import ReportingService
from app.services.invoicing.invoice_accounting_service import InvoiceAccountingService
from app.services.invoicing.invoice_service import InvoiceService
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_accounting_context(
    session: AsyncSession,
    *,
    vat_account: bool = True,
    fiscal_period_status: FiscalPeriodStatus = FiscalPeriodStatus.OPEN,
) -> tuple[Organization, VATRate, InvoiceAccountingService]:
    suffix = uuid4().hex[:12]
    organization = Organization(name=f"Invoice accounting organization {suffix}")
    session.add(organization)
    await session.flush()
    fiscal_year = FiscalYear(
        organization_id=organization.id,
        name=f"FY invoice {suffix}",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status=FiscalYearStatus.OPEN,
    )
    session.add(fiscal_year)
    await session.flush()
    fiscal_period = FiscalPeriod(
        organization_id=organization.id,
        fiscal_year_id=fiscal_year.id,
        name=f"Period invoice {suffix}",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status=fiscal_period_status,
    )
    journal = Journal(
        organization_id=organization.id,
        code=f"VE{suffix[:8]}",
        name="Invoice sales journal",
        journal_type="SALES",
        is_active=True,
    )
    receivable = Account(
        organization_id=organization.id,
        code=f"411{suffix[:8]}",
        name="Trade receivables",
        account_type="ASSET",
        level=1,
        path=f"/411{suffix[:8]}/",
    )
    revenue = Account(
        organization_id=organization.id,
        code=f"701{suffix[:8]}",
        name="Sales revenue",
        account_type="REVENUE",
        level=1,
        path=f"/701{suffix[:8]}/",
    )
    collected_vat = Account(
        organization_id=organization.id,
        code=f"443{suffix[:8]}",
        name="Collected VAT",
        account_type="LIABILITY",
        level=1,
        path=f"/443{suffix[:8]}/",
    )
    vat_rate = VATRate(
        organization_id=organization.id,
        code=f"VAT{suffix[:8]}",
        name="Invoice VAT",
        rate=Decimal("18.00"),
        effective_from=date(2020, 1, 1),
        is_active=True,
    )
    session.add_all(
        [
            fiscal_period,
            journal,
            receivable,
            revenue,
            collected_vat,
            vat_rate,
        ]
    )
    await session.commit()
    service = InvoiceAccountingService(session)
    await service.configure_profile(
        organization.id,
        "invoice-accounting-tester",
        InvoiceAccountingProfileCreate(
            journal_id=journal.id,
            receivable_account_id=receivable.id,
            revenue_account_id=revenue.id,
            collected_vat_account_id=collected_vat.id if vat_account else None,
        ),
    )
    return organization, vat_rate, service


async def _create_issued_invoice(
    session: AsyncSession,
    organization: Organization,
    vat_rate_id: str | None,
    *,
    amount: Decimal = Decimal("100.00"),
):
    suffix = uuid4().hex[:12]
    invoice = await InvoiceService(session).create_invoice(
        organization.id,
        InvoiceCreate(
            invoice_number=f"INV-{suffix}",
            customer_name="Invoice accounting test customer",
            invoice_date=date(2026, 2, 15),
            due_date=date(2026, 3, 15),
            lines=[
                InvoiceLineCreate(
                    description="Accounting integration service",
                    quantity=Decimal("1.000"),
                    unit_price=amount,
                    vat_rate_id=vat_rate_id,
                )
            ],
        ),
    )
    return await InvoiceService(session).issue_invoice(organization.id, invoice.id)


@pytest.mark.asyncio
async def test_posts_invoice_with_vat_as_balanced_decimal_entry_and_reporting_impact(
    db_session: AsyncSession,
) -> None:
    organization, vat_rate, service = await _create_accounting_context(db_session)
    invoice = await _create_issued_invoice(db_session, organization, vat_rate.id)

    posting = await service.post_invoice(
        organization.id,
        "invoice-accounting-tester",
        invoice.id,
        "invoice-post-vat-001",
    )

    assert posting is not None
    assert posting.source_module == "INVOICING"
    assert posting.source_type == "INVOICE"
    assert posting.source_id == invoice.id
    entry = await JournalEntryService(db_session).get_entry(
        organization.id, posting.journal_entry_id
    )
    assert entry.status.value == "POSTED"
    assert sum(
        (Decimal(line.debit) for line in entry.lines), Decimal("0.00")
    ) == Decimal("118.00")
    assert sum(
        (Decimal(line.credit) for line in entry.lines), Decimal("0.00")
    ) == Decimal("118.00")
    assert sorted(Decimal(line.credit) for line in entry.lines if line.credit) == [
        Decimal("18.00"),
        Decimal("100.00"),
    ]
    trial_balance = await ReportingService(db_session).trial_balance(
        organization.id, date(2026, 2, 15), date(2026, 2, 1)
    )
    assert trial_balance.is_balanced is True
    assert trial_balance.total_debit == Decimal("118.00")
    assert trial_balance.total_credit == Decimal("118.00")
    income_statement = await ReportingService(db_session).income_statement(
        organization.id, date(2026, 2, 1), date(2026, 2, 15)
    )
    assert income_statement.total_revenue == Decimal("100.00")
    actions = set(
        await db_session.scalars(
            select(AuditEvent.action).where(
                AuditEvent.organization_id == organization.id,
                AuditEvent.resource_id.in_([invoice.id, posting.journal_entry_id]),
            )
        )
    )
    assert "INVOICE_POSTED_TO_ACCOUNTING" in actions
    assert "JOURNAL_ENTRY_POSTED" in actions


@pytest.mark.asyncio
async def test_invoice_posting_is_idempotent_by_source_and_rejects_key_reuse(
    db_session: AsyncSession,
) -> None:
    organization, vat_rate, service = await _create_accounting_context(db_session)
    invoice = await _create_issued_invoice(db_session, organization, vat_rate.id)

    first = await service.post_invoice(
        organization.id, "actor", invoice.id, "invoice-idempotency-001"
    )
    repeated = await service.post_invoice(
        organization.id, "actor", invoice.id, "invoice-idempotency-different"
    )
    assert repeated is not None
    assert repeated.id == first.id
    assert repeated.journal_entry_id == first.journal_entry_id
    assert (
        await db_session.scalar(
            select(func.count(InvoiceAccountingPosting.id)).where(
                InvoiceAccountingPosting.organization_id == organization.id,
                InvoiceAccountingPosting.source_id == invoice.id,
            )
        )
        == 1
    )

    other_invoice = await _create_issued_invoice(db_session, organization, vat_rate.id)
    with pytest.raises(HTTPException, match="Idempotency-Key") as conflict:
        await service.post_invoice(
            organization.id, "actor", other_invoice.id, "invoice-idempotency-001"
        )
    assert conflict.value.status_code == 409


@pytest.mark.asyncio
async def test_posting_rejects_closed_period_and_leaves_no_accounting_trace(
    db_session: AsyncSession,
) -> None:
    organization, vat_rate, service = await _create_accounting_context(
        db_session, fiscal_period_status=FiscalPeriodStatus.CLOSED
    )
    invoice = await _create_issued_invoice(db_session, organization, vat_rate.id)

    with pytest.raises(HTTPException, match="Fiscal period is not open") as blocked:
        await service.post_invoice(
            organization.id, "actor", invoice.id, "invoice-closed-period"
        )
    assert blocked.value.status_code == 422
    assert (
        await db_session.scalar(
            select(func.count(InvoiceAccountingPosting.id)).where(
                InvoiceAccountingPosting.organization_id == organization.id
            )
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.organization_id == organization.id
            )
        )
        == 0
    )


@pytest.mark.asyncio
async def test_posting_with_vat_requires_configured_collected_vat_account_and_rolls_back(
    db_session: AsyncSession,
) -> None:
    organization, vat_rate, service = await _create_accounting_context(
        db_session, vat_account=False
    )
    invoice = await _create_issued_invoice(db_session, organization, vat_rate.id)

    with pytest.raises(HTTPException, match="collected VAT account") as not_ready:
        await service.post_invoice(
            organization.id, "actor", invoice.id, "invoice-vat-not-ready"
        )
    assert not_ready.value.status_code == 422
    assert (
        await db_session.scalar(
            select(func.count(InvoiceAccountingPosting.id)).where(
                InvoiceAccountingPosting.organization_id == organization.id
            )
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.organization_id == organization.id
            )
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization.id,
                AuditEvent.action == "INVOICE_POSTED_TO_ACCOUNTING",
            )
        )
        == 0
    )


@pytest.mark.asyncio
async def test_posting_rejects_cancelled_invoice_and_is_tenant_scoped(
    db_session: AsyncSession,
) -> None:
    organization, vat_rate, service = await _create_accounting_context(db_session)
    invoice = await _create_issued_invoice(db_session, organization, vat_rate.id)
    invoice.status = InvoiceStatus.CANCELLED
    await db_session.commit()

    with pytest.raises(HTTPException, match="Cancelled") as cancelled:
        await service.post_invoice(
            organization.id, "actor", invoice.id, "invoice-cancelled"
        )
    assert cancelled.value.status_code == 422

    other_organization, _, other_service = await _create_accounting_context(db_session)
    with pytest.raises(HTTPException, match="Invoice not found") as cross_tenant:
        await other_service.post_invoice(
            other_organization.id, "actor", invoice.id, "invoice-cross-tenant"
        )
    assert cross_tenant.value.status_code == 404
