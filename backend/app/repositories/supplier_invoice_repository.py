from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.supplier_invoice import SupplierInvoice, SupplierInvoiceStatus


class SupplierInvoiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, organization_id: str, invoice_id: str) -> SupplierInvoice | None:
        return await self.session.scalar(
            select(SupplierInvoice).where(
                SupplierInvoice.organization_id == organization_id,
                SupplierInvoice.id == invoice_id,
            )
        )

    async def get_for_update(self, organization_id: str, invoice_id: str) -> SupplierInvoice | None:
        return await self.session.scalar(
            select(SupplierInvoice)
            .where(
                SupplierInvoice.organization_id == organization_id,
                SupplierInvoice.id == invoice_id,
            )
            .with_for_update()
        )

    async def get_by_number(self, organization_id: str, supplier_id: str, invoice_number: str) -> SupplierInvoice | None:
        return await self.session.scalar(
            select(SupplierInvoice).where(
                SupplierInvoice.organization_id == organization_id,
                SupplierInvoice.supplier_id == supplier_id,
                SupplierInvoice.invoice_number == invoice_number,
            )
        )

    async def list(
        self,
        organization_id: str,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
        supplier_id: str | None = None,
    ) -> list[SupplierInvoice]:
        statement = select(SupplierInvoice).where(SupplierInvoice.organization_id == organization_id)
        if status is not None:
            statement = statement.where(SupplierInvoice.status == status)
        if supplier_id is not None:
            statement = statement.where(SupplierInvoice.supplier_id == supplier_id)
        result = await self.session.scalars(
            statement.order_by(SupplierInvoice.invoice_date.desc(), SupplierInvoice.id).offset(skip).limit(limit)
        )
        return list(result.all())

    async def list_approved_for_exposure(self, organization_id: str) -> list[SupplierInvoice]:
        result = await self.session.scalars(
            select(SupplierInvoice)
            .options(selectinload(SupplierInvoice.supplier))
            .where(
                SupplierInvoice.organization_id == organization_id,
                SupplierInvoice.status == SupplierInvoiceStatus.APPROVED,
            )
            .order_by(SupplierInvoice.supplier_id, SupplierInvoice.currency_code, SupplierInvoice.due_date, SupplierInvoice.id)
        )
        return list(result.all())

    def add(self, invoice: SupplierInvoice) -> None:
        self.session.add(invoice)
