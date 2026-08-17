from datetime import date
from decimal import Decimal

import pytest
from app.core.enums.invoicing import InvoiceStatus, PaymentMethod
from app.models.accounting.vat import VATRate
from app.models.organization import Organization
from app.schemas.invoicing.credit_note import CreditNoteCreate
from app.schemas.invoicing.invoice import InvoiceCreate, InvoiceLineCreate
from app.schemas.invoicing.payment import PaymentCreate
from app.services.invoicing.credit_note_service import CreditNoteService
from app.services.invoicing.invoice_service import InvoiceService
from app.services.invoicing.payment_service import PaymentService
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_organization_with_vat_rate(
    session: AsyncSession,
) -> tuple[Organization, VATRate]:
    organization = Organization(name="Invoicing test organization")
    session.add(organization)
    await session.commit()
    vat_rate = VATRate(
        organization_id=organization.id,
        code="VAT18",
        name="Standard VAT",
        rate=Decimal("18.00"),
        effective_from=date(2020, 1, 1),
        is_active=True,
    )
    session.add(vat_rate)
    await session.commit()
    return organization, vat_rate


def _invoice_data(invoice_number: str, vat_rate_id: str | None = None) -> InvoiceCreate:
    return InvoiceCreate(
        invoice_number=invoice_number,
        customer_name="Acme Client",
        invoice_date=date(2026, 2, 1),
        due_date=date(2026, 2, 28),
        lines=[
            InvoiceLineCreate(
                description="Professional service",
                quantity=Decimal("1.000"),
                unit_price=Decimal("100.00"),
                vat_rate_id=vat_rate_id,
            )
        ],
    )


@pytest.mark.asyncio
async def test_invoice_issue_payment_and_credit_preserve_amounts(
    db_session: AsyncSession,
) -> None:
    organization, vat_rate = await _create_organization_with_vat_rate(db_session)
    invoice_service = InvoiceService(db_session)
    payment_service = PaymentService(db_session)
    credit_service = CreditNoteService(db_session)

    draft = await invoice_service.create_invoice(
        organization.id, _invoice_data("inv-001", vat_rate.id)
    )
    assert draft.status == InvoiceStatus.DRAFT
    assert draft.subtotal == Decimal("100.00")
    assert draft.tax_amount == Decimal("18.00")
    assert draft.total_amount == Decimal("118.00")
    assert draft.lines[0].tax_rate == Decimal("18.00")

    issued = await invoice_service.issue_invoice(organization.id, draft.id)
    assert issued.status == InvoiceStatus.ISSUED

    payment = await payment_service.create_payment(
        organization.id,
        PaymentCreate(
            invoice_id=draft.id,
            payment_date=date(2026, 2, 2),
            amount=Decimal("50.00"),
            method=PaymentMethod.BANK_TRANSFER,
            external_reference="BANK-001",
        ),
    )
    partially_paid = await invoice_service.get_invoice(organization.id, draft.id)
    assert partially_paid.status == InvoiceStatus.PARTIALLY_PAID
    assert partially_paid.outstanding_amount == Decimal("68.00")

    credit_note = await credit_service.create_credit_note(
        organization.id,
        CreditNoteCreate(
            invoice_id=draft.id,
            credit_note_number="cn-001",
            credit_date=date(2026, 2, 3),
            subtotal=Decimal("57.63"),
            tax_amount=Decimal("10.37"),
            amount=Decimal("68.00"),
            reason="Commercial discount",
        ),
    )
    settled = await invoice_service.get_invoice(organization.id, draft.id)

    assert payment.amount == Decimal("50.00")
    assert credit_note.amount == Decimal("68.00")
    assert settled.status == InvoiceStatus.PAID
    assert settled.paid_amount == Decimal("50.00")
    assert settled.credited_amount == Decimal("68.00")
    assert settled.outstanding_amount == Decimal("0.00")


@pytest.mark.asyncio
async def test_rejects_payment_before_issue_and_settlement_above_outstanding(
    db_session: AsyncSession,
) -> None:
    organization, _ = await _create_organization_with_vat_rate(db_session)
    invoice_service = InvoiceService(db_session)
    payment_service = PaymentService(db_session)
    draft = await invoice_service.create_invoice(
        organization.id, _invoice_data("INV-002")
    )
    draft_id = draft.id

    with pytest.raises(HTTPException, match="Only issued") as unissued_payment:
        await payment_service.create_payment(
            organization.id,
            PaymentCreate(
                invoice_id=draft_id,
                payment_date=date(2026, 2, 2),
                amount=Decimal("10.00"),
                method=PaymentMethod.CASH,
            ),
        )
    assert unissued_payment.value.status_code == 422
    await db_session.refresh(organization, attribute_names=["id"])

    issued = await invoice_service.issue_invoice(organization.id, draft_id)
    with pytest.raises(HTTPException, match="exceeds") as excessive_payment:
        await payment_service.create_payment(
            organization.id,
            PaymentCreate(
                invoice_id=issued.id,
                payment_date=date(2026, 2, 2),
                amount=Decimal("100.01"),
                method=PaymentMethod.CASH,
            ),
        )
    assert excessive_payment.value.status_code == 422


@pytest.mark.asyncio
async def test_invoice_and_payment_external_numbers_are_unique_per_organization(
    db_session: AsyncSession,
) -> None:
    organization, _ = await _create_organization_with_vat_rate(db_session)
    invoice_service = InvoiceService(db_session)
    payment_service = PaymentService(db_session)
    first = await invoice_service.create_invoice(
        organization.id, _invoice_data("INV-003")
    )

    with pytest.raises(
        HTTPException, match="Invoice number already exists"
    ) as duplicate:
        await invoice_service.create_invoice(organization.id, _invoice_data("inv-003"))
    assert duplicate.value.status_code == 409

    issued = await invoice_service.issue_invoice(organization.id, first.id)
    await payment_service.create_payment(
        organization.id,
        PaymentCreate(
            invoice_id=issued.id,
            payment_date=date(2026, 2, 2),
            amount=Decimal("10.00"),
            method=PaymentMethod.MOBILE_MONEY,
            external_reference="MOMO-001",
        ),
    )
    with pytest.raises(
        HTTPException, match="external reference"
    ) as duplicate_reference:
        await payment_service.create_payment(
            organization.id,
            PaymentCreate(
                invoice_id=issued.id,
                payment_date=date(2026, 2, 3),
                amount=Decimal("10.00"),
                method=PaymentMethod.MOBILE_MONEY,
                external_reference="MOMO-001",
            ),
        )
    assert duplicate_reference.value.status_code == 409
