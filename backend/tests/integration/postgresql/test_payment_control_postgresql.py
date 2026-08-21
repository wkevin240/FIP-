import os
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from app.models.invoicing.payment_allocation import PaymentAllocation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from tests.integration.treasury.test_treasury_accounting_service import _context

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


@pytest.mark.asyncio
async def test_payment_allocation_database_constraints(postgres_session: AsyncSession):
    organization, _, _, _, _, _ = await _context(postgres_session)
    from app.models.invoicing.invoice import Invoice
    from app.models.invoicing.payment import Payment

    invoice = Invoice(
        organization_id=organization.id,
        invoice_number=f"INV-{uuid4().hex}",
        customer_name="Test customer",
        invoice_date=date(2026, 8, 1),
        status="ISSUED",
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
        credited_amount=Decimal("0.00"),
    )
    postgres_session.add(invoice)
    await postgres_session.flush()

    payment = Payment(
        organization_id=organization.id,
        invoice_id=invoice.id,
        payment_date=date(2026, 8, 21),
        amount=Decimal("100.00"),
        method="BANK_TRANSFER",
        external_reference=f"PAY-{uuid4().hex}",
        received_at=datetime(2026, 8, 21, 10, 0, 0, tzinfo=UTC).replace(tzinfo=None),
    )
    postgres_session.add(payment)
    await postgres_session.flush()
    organization_id = organization.id
    payment_id = payment.id
    invoice_id = invoice.id
    allocation = PaymentAllocation(
        organization_id=organization_id,
        payment_id=payment_id,
        invoice_id=invoice_id,
        allocated_amount=Decimal("40.00"),
        idempotency_key=f"ALLOC-{uuid4().hex}",
    )
    postgres_session.add(allocation)
    await postgres_session.commit()

    duplicate = PaymentAllocation(
        organization_id=organization_id,
        payment_id=payment_id,
        invoice_id=invoice_id,
        allocated_amount=Decimal("10.00"),
        idempotency_key=f"ALLOC-{uuid4().hex}",
    )
    postgres_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await postgres_session.commit()
    await postgres_session.rollback()

    negative = PaymentAllocation(
        organization_id=organization_id,
        payment_id=payment_id,
        invoice_id=invoice_id,
        allocated_amount=Decimal("-1.00"),
        idempotency_key=f"ALLOC-{uuid4().hex}",
    )
    postgres_session.add(negative)
    with pytest.raises(IntegrityError):
        await postgres_session.commit()
    await postgres_session.rollback()


@pytest.mark.asyncio
async def test_payment_without_canonical_allocation_is_unapplied(
    postgres_session: AsyncSession,
):
    organization, _, _, _, _, _ = await _context(postgres_session)
    from app.models.invoicing.invoice import Invoice
    from app.models.invoicing.payment import Payment
    from app.services.invoicing.payment_control_service import PaymentControlService

    invoice = Invoice(
        organization_id=organization.id,
        invoice_number=f"INV-{uuid4().hex}",
        customer_name="Regression customer",
        invoice_date=date(2026, 8, 1),
        status="ISSUED",
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
        credited_amount=Decimal("0.00"),
    )
    payment = Payment(
        organization_id=organization.id,
        invoice_id=invoice.id,
        payment_date=date(2026, 8, 21),
        amount=Decimal("100.00"),
        method="BANK_TRANSFER",
        external_reference=f"PAY-{uuid4().hex}",
        received_at=datetime(2026, 8, 21, 10, 0, 0, tzinfo=UTC).replace(tzinfo=None),
    )
    postgres_session.add_all([invoice, payment])
    await postgres_session.commit()

    control = await PaymentControlService(postgres_session).customer_control(
        organization.id, payment.id
    )
    assert control.allocated_amount == Decimal("0.00")
    assert control.unapplied_amount == Decimal("100.00")
    assert control.status == "UNAPPLIED"


@pytest.mark.asyncio
async def test_payment_bank_transaction_comparison_reports_real_difference(
    postgres_session: AsyncSession,
):
    organization, _, bank_profile, _, _, _ = await _context(postgres_session)
    from app.models.accounting.bank_transaction import BankTransaction
    from app.models.invoicing.payment import Payment
    from app.services.invoicing.payment_control_service import PaymentControlService

    reference = f"PAY-{uuid4().hex}"
    payment = Payment(
        organization_id=organization.id,
        invoice_id=None,
        payment_date=date(2026, 8, 21),
        amount=Decimal("100.00"),
        method="BANK_TRANSFER",
        external_reference=reference,
        received_at=datetime(2026, 8, 21, 10, 0, 0, tzinfo=UTC).replace(tzinfo=None),
    )
    bank_transaction = BankTransaction(
        organization_id=organization.id,
        bank_account_id=bank_profile.ledger_account_id,
        transaction_date=date(2026, 8, 21),
        amount=Decimal("97.50"),
        description="Customer settlement",
        reference=reference,
        external_id=f"BANK-{uuid4().hex}",
    )
    postgres_session.add_all([payment, bank_transaction])
    await postgres_session.commit()

    report = await PaymentControlService(postgres_session).reconciliation(
        organization.id, date(2026, 8, 21)
    )
    assert report.status == "INCOMPLETE"
    assert report.payment_without_bank_transaction == 0
    assert report.bank_transaction_without_payment == 0
    assert report.amount_differences == Decimal("2.50")
    assert "PAYMENT_BANK_AMOUNT_DIFFERENCE" in report.blockers
