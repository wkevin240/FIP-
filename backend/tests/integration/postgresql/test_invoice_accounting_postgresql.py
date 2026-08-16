import asyncio
import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.accounting.journal import Journal
from app.models.accounting.vat import VATRate
from app.models.audit.audit_event import AuditEvent
from app.models.invoicing.accounting import InvoiceAccountingPosting
from app.models.organization import Organization
from app.schemas.invoicing.accounting import InvoiceAccountingProfileCreate
from app.schemas.invoicing.invoice import InvoiceCreate, InvoiceLineCreate
from app.services.invoicing.invoice_accounting_service import InvoiceAccountingService
from app.services.invoicing.invoice_service import InvoiceService
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

POSTGRES_TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_DATABASE_URL,
    reason="PostgreSQL integration database is not configured",
)


@pytest.fixture
async def postgres_session():
    engine = create_async_engine(POSTGRES_TEST_DATABASE_URL, echo=False)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


async def _create_invoice_context(session: AsyncSession) -> tuple[str, str, str]:
    suffix = uuid4().hex[:12]
    organization = Organization(name=f"Invoice PostgreSQL organization {suffix}")
    session.add(organization)
    await session.flush()
    fiscal_year = FiscalYear(
        organization_id=organization.id,
        name=f"FY invoice PostgreSQL {suffix}",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status=FiscalYearStatus.OPEN,
    )
    session.add(fiscal_year)
    await session.flush()
    fiscal_period = FiscalPeriod(
        organization_id=organization.id,
        fiscal_year_id=fiscal_year.id,
        name=f"Period invoice PostgreSQL {suffix}",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status=FiscalPeriodStatus.OPEN,
    )
    journal = Journal(
        organization_id=organization.id,
        code=f"VE{suffix[:8]}",
        name="Invoice PostgreSQL journal",
        journal_type="SALES",
        is_active=True,
    )
    receivable = Account(
        organization_id=organization.id,
        code=f"411{suffix[:8]}",
        name="Invoice PostgreSQL receivable",
        account_type="ASSET",
        level=1,
        path=f"/411{suffix[:8]}/",
    )
    revenue = Account(
        organization_id=organization.id,
        code=f"701{suffix[:8]}",
        name="Invoice PostgreSQL revenue",
        account_type="REVENUE",
        level=1,
        path=f"/701{suffix[:8]}/",
    )
    vat_account = Account(
        organization_id=organization.id,
        code=f"443{suffix[:8]}",
        name="Invoice PostgreSQL VAT",
        account_type="LIABILITY",
        level=1,
        path=f"/443{suffix[:8]}/",
    )
    vat_rate = VATRate(
        organization_id=organization.id,
        code=f"VAT{suffix[:8]}",
        name="Invoice PostgreSQL VAT",
        rate=Decimal("18.00"),
        effective_from=date(2020, 1, 1),
        is_active=True,
    )
    session.add_all(
        [fiscal_period, journal, receivable, revenue, vat_account, vat_rate]
    )
    await session.commit()
    accounting = InvoiceAccountingService(session)
    await accounting.configure_profile(
        organization.id,
        "postgres-invoice-tester",
        InvoiceAccountingProfileCreate(
            journal_id=journal.id,
            receivable_account_id=receivable.id,
            revenue_account_id=revenue.id,
            collected_vat_account_id=vat_account.id,
        ),
    )
    invoice = await InvoiceService(session).create_invoice(
        organization.id,
        InvoiceCreate(
            invoice_number=f"INV-PG-{suffix}",
            customer_name="PostgreSQL invoice customer",
            invoice_date=date(2026, 2, 15),
            due_date=date(2026, 3, 15),
            lines=[
                InvoiceLineCreate(
                    description="PostgreSQL accounting integration",
                    quantity=Decimal("1.000"),
                    unit_price=Decimal("100.00"),
                    vat_rate_id=vat_rate.id,
                )
            ],
        ),
    )
    issued = await InvoiceService(session).issue_invoice(organization.id, invoice.id)
    return organization.id, issued.id, journal.id


@pytest.mark.asyncio
async def test_postgresql_enforces_single_source_link_and_tenant_foreign_keys(
    postgres_session: AsyncSession,
) -> None:
    organization_id, invoice_id, _ = await _create_invoice_context(postgres_session)
    posting = await InvoiceAccountingService(postgres_session).post_invoice(
        organization_id, "postgres-invoice-tester", invoice_id, "postgres-source-001"
    )
    assert posting is not None
    journal_entry_id = posting.journal_entry_id

    with pytest.raises(IntegrityError):
        await postgres_session.execute(
            text(
                """
                INSERT INTO public.invoice_accounting_postings (
                    id, created_at, updated_at, organization_id, source_module,
                    source_type, source_id, journal_entry_id, idempotency_key, status
                ) VALUES (
                    :id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :organization_id,
                    'INVOICING', 'INVOICE', :source_id, :journal_entry_id,
                    'postgres-source-duplicate', 'POSTED'
                )
                """
            ),
            {
                "id": uuid4().hex,
                "organization_id": organization_id,
                "source_id": invoice_id,
                "journal_entry_id": journal_entry_id,
            },
        )
        await postgres_session.commit()
    await postgres_session.rollback()

    other_organization_id, _, _ = await _create_invoice_context(postgres_session)
    with pytest.raises(IntegrityError):
        await postgres_session.execute(
            text(
                """
                INSERT INTO public.invoice_accounting_postings (
                    id, created_at, updated_at, organization_id, source_module,
                    source_type, source_id, journal_entry_id, idempotency_key, status
                ) VALUES (
                    :id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :organization_id,
                    'INVOICING', 'INVOICE', :source_id, :journal_entry_id,
                    'postgres-cross-tenant', 'POSTED'
                )
                """
            ),
            {
                "id": uuid4().hex,
                "organization_id": other_organization_id,
                "source_id": invoice_id,
                "journal_entry_id": journal_entry_id,
            },
        )
        await postgres_session.commit()
    await postgres_session.rollback()


@pytest.mark.asyncio
async def test_postgresql_concurrent_invoice_posting_is_serialized_and_audited_once(
    postgres_session: AsyncSession,
) -> None:
    organization_id, invoice_id, _ = await _create_invoice_context(postgres_session)
    engine = create_async_engine(POSTGRES_TEST_DATABASE_URL, echo=False)

    async def post_once(key: str) -> str:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            posting = await InvoiceAccountingService(session).post_invoice(
                organization_id, "postgres-concurrent-tester", invoice_id, key
            )
            assert posting is not None
            return posting.id

    try:
        first_id, second_id = await asyncio.gather(
            post_once("postgres-concurrent-001"),
            post_once("postgres-concurrent-002"),
        )
    finally:
        await engine.dispose()

    assert first_id == second_id
    assert (
        await postgres_session.scalar(
            select(func.count(InvoiceAccountingPosting.id)).where(
                InvoiceAccountingPosting.organization_id == organization_id,
                InvoiceAccountingPosting.source_id == invoice_id,
            )
        )
        == 1
    )
    assert (
        await postgres_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.action == "INVOICE_POSTED_TO_ACCOUNTING",
                AuditEvent.resource_id == invoice_id,
            )
        )
        == 1
    )
