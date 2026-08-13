from app.models.invoicing.invoice_line import InvoiceLine
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class InvoiceLineRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_invoice(self, invoice_id: str) -> list[InvoiceLine]:
        result = await self.session.scalars(
            select(InvoiceLine)
            .where(InvoiceLine.invoice_id == invoice_id)
            .order_by(InvoiceLine.sort_order)
        )
        return list(result)
