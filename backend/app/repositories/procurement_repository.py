from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.procurement import (
    ProcurementAccountingProfile,
    PurchaseInvoice,
    PurchaseInvoiceAccountingPosting,
    Supplier,
    SupplierPayment,
    SupplierPaymentAccountingPosting,
)


class ProcurementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def supplier(
        self, organization_id: str, supplier_id: str, *, lock: bool = False
    ):
        query = select(Supplier).where(
            Supplier.organization_id == organization_id, Supplier.id == supplier_id
        )
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def invoice(
        self, organization_id: str, invoice_id: str, *, lock: bool = False
    ):
        query = (
            select(PurchaseInvoice)
            .options(selectinload(PurchaseInvoice.lines))
            .where(
                PurchaseInvoice.organization_id == organization_id,
                PurchaseInvoice.id == invoice_id,
            )
        )
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def payment(
        self, organization_id: str, payment_id: str, *, lock: bool = False
    ):
        query = select(SupplierPayment).where(
            SupplierPayment.organization_id == organization_id,
            SupplierPayment.id == payment_id,
        )
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def profile(self, organization_id: str, *, lock: bool = False):
        query = select(ProcurementAccountingProfile).where(
            ProcurementAccountingProfile.organization_id == organization_id
        )
        if lock:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def invoice_posting(self, organization_id: str, invoice_id: str):
        return await self.session.scalar(
            select(PurchaseInvoiceAccountingPosting).where(
                PurchaseInvoiceAccountingPosting.organization_id == organization_id,
                PurchaseInvoiceAccountingPosting.source_id == invoice_id,
            )
        )

    async def payment_posting(self, organization_id: str, payment_id: str):
        return await self.session.scalar(
            select(SupplierPaymentAccountingPosting).where(
                SupplierPaymentAccountingPosting.organization_id == organization_id,
                SupplierPaymentAccountingPosting.source_id == payment_id,
            )
        )

    async def posting_by_key(self, organization_id: str, key: str):
        invoice = await self.session.scalar(
            select(PurchaseInvoiceAccountingPosting).where(
                PurchaseInvoiceAccountingPosting.organization_id == organization_id,
                PurchaseInvoiceAccountingPosting.idempotency_key == key,
            )
        )
        if invoice is not None:
            return invoice
        return await self.session.scalar(
            select(SupplierPaymentAccountingPosting).where(
                SupplierPaymentAccountingPosting.organization_id == organization_id,
                SupplierPaymentAccountingPosting.idempotency_key == key,
            )
        )
