from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer_invoice import CustomerInvoice, CustomerInvoiceStatus


class CustomerInvoiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, organization_id: str, invoice_id: str) -> CustomerInvoice | None:
        return await self.session.scalar(
            select(CustomerInvoice).where(
                CustomerInvoice.organization_id == organization_id,
                CustomerInvoice.id == invoice_id,
            )
        )

    async def get_for_update(self, organization_id: str, invoice_id: str) -> CustomerInvoice | None:
        return await self.session.scalar(
            select(CustomerInvoice)
            .where(
                CustomerInvoice.organization_id == organization_id,
                CustomerInvoice.id == invoice_id,
            )
            .with_for_update()
        )

    async def list(
        self,
        organization_id: str,
        *,
        skip: int,
        limit: int,
        customer_id: str | None = None,
        status: CustomerInvoiceStatus | None = None,
        due_before: date | None = None,
    ) -> list[CustomerInvoice]:
        statement = select(CustomerInvoice).where(CustomerInvoice.organization_id == organization_id)
        if customer_id is not None:
            statement = statement.where(CustomerInvoice.customer_id == customer_id)
        if status is not None:
            statement = statement.where(CustomerInvoice.status == status)
        if due_before is not None:
            statement = statement.where(CustomerInvoice.due_date <= due_before)
        result = await self.session.scalars(
            statement.order_by(CustomerInvoice.invoice_date.desc(), CustomerInvoice.invoice_number, CustomerInvoice.id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.all())

    def add(self, invoice: CustomerInvoice) -> None:
        self.session.add(invoice)

