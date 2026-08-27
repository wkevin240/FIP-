import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.models.organization import Organization
from app.models.procurement import PurchaseInvoice, PurchaseInvoiceLine, Supplier
from app.models.procurement_flow import PurchaseOrder, PurchaseOrderLine
from app.schemas.procurement_flow import GoodsReceiptCreate, GoodsReceiptLineCreate
from app.services.procurement_flow_service import ProcurementFlowService
from fastapi import HTTPException
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


async def _context(session: AsyncSession):
    suffix = uuid4().hex
    organization = Organization(name=f"P2P flow {suffix}")
    session.add(organization)
    await session.flush()
    supplier = Supplier(
        organization_id=organization.id,
        supplier_code=f"SUP-{suffix}",
        legal_name="Isolated supplier",
    )
    session.add(supplier)
    await session.flush()
    order = PurchaseOrder(
        organization_id=organization.id,
        supplier_id=supplier.id,
        order_number=f"PO-{suffix}",
        order_date=date(2026, 8, 22),
        status="ISSUED",
    )
    session.add(order)
    await session.flush()
    line = PurchaseOrderLine(
        organization_id=organization.id,
        order_id=order.id,
        description="Test item",
        quantity=Decimal("10.000"),
        unit_price=Decimal("10.00"),
        sort_order=1,
    )
    session.add(line)
    await session.flush()
    invoice = PurchaseInvoice(
        organization_id=organization.id,
        supplier_id=supplier.id,
        purchase_order_id=order.id,
        invoice_number=f"PI-{suffix}",
        invoice_date=date(2026, 8, 22),
        status="VALIDATED",
        subtotal=Decimal("50.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("50.00"),
        paid_amount=Decimal("0.00"),
    )
    session.add(invoice)
    await session.flush()
    session.add(
        PurchaseInvoiceLine(
            organization_id=organization.id,
            invoice_id=invoice.id,
            expense_account_id="expense-account",
            description="Test item",
            quantity=Decimal("5.000"),
            unit_price=Decimal("10.00"),
            tax_rate=Decimal("0.00"),
            line_subtotal=Decimal("50.00"),
            tax_amount=Decimal("0.00"),
            line_total=Decimal("50.00"),
            sort_order=1,
        )
    )
    await session.commit()
    return organization.id, order.id, line.id, invoice.id


@pytest.mark.asyncio
async def test_three_way_match_uses_received_line_amount(
    postgres_session: AsyncSession,
):
    organization_id, order_id, line_id, invoice_id = await _context(postgres_session)
    service = ProcurementFlowService(postgres_session)
    await service.create_receipt(
        organization_id,
        "receiver",
        GoodsReceiptCreate(
            receipt_number=f"GR-{uuid4().hex}",
            order_id=order_id,
            receipt_date=date(2026, 8, 22),
            lines=[
                GoodsReceiptLineCreate(
                    order_line_id=line_id, received_quantity=Decimal("5.000")
                )
            ],
        ),
    )
    result = await service.three_way_match(organization_id, invoice_id)
    assert result["status"] == "MATCHED"
    assert result["received_amount"] == Decimal("50.00")
    assert result["amount_difference"] == Decimal("0.00")


@pytest.mark.asyncio
async def test_receipt_cannot_exceed_ordered_quantity(postgres_session: AsyncSession):
    organization_id, order_id, line_id, _ = await _context(postgres_session)
    service = ProcurementFlowService(postgres_session)
    data = GoodsReceiptCreate(
        receipt_number=f"GR-{uuid4().hex}",
        order_id=order_id,
        receipt_date=date(2026, 8, 22),
        lines=[
            GoodsReceiptLineCreate(
                order_line_id=line_id, received_quantity=Decimal("8.000")
            )
        ],
    )
    await service.create_receipt(organization_id, "receiver", data)
    with pytest.raises(HTTPException, match="exceeds ordered"):
        await service.create_receipt(
            organization_id,
            "receiver",
            GoodsReceiptCreate(
                receipt_number=f"GR-{uuid4().hex}",
                order_id=order_id,
                receipt_date=date(2026, 8, 22),
                lines=[
                    GoodsReceiptLineCreate(
                        order_line_id=line_id, received_quantity=Decimal("3.000")
                    )
                ],
            ),
        )


@pytest.mark.asyncio
async def test_purchase_order_line_fk_is_tenant_scoped(postgres_session: AsyncSession):
    organization_id, order_id, line_id, _ = await _context(postgres_session)
    other = Organization(name=f"Other {uuid4().hex}")
    postgres_session.add(other)
    await postgres_session.flush()
    from app.models.procurement_flow import GoodsReceipt, GoodsReceiptLine

    receipt = GoodsReceipt(
        organization_id=organization_id,
        order_id=order_id,
        receipt_number=f"GR-{uuid4().hex}",
        receipt_date=date(2026, 8, 22),
        receiver_user_id="receiver",
        status="POSTED",
    )
    postgres_session.add(receipt)
    await postgres_session.flush()
    postgres_session.add(
        GoodsReceiptLine(
            organization_id=other.id,
            receipt_id=receipt.id,
            order_line_id=line_id,
            received_quantity=Decimal("1.000"),
        )
    )
    with pytest.raises(IntegrityError):
        await postgres_session.commit()
    await postgres_session.rollback()
