from __future__ import annotations

from app.models.invoicing.invoice import Invoice
from app.models.invoicing.invoice_line import InvoiceLine
from app.schemas.invoicing.invoice import InvoiceCreate, InvoiceUpdate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class InvoiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _with_lines() -> select:
        return select(Invoice).options(selectinload(Invoice.lines))

    async def get_by_id(self, organization_id: str, invoice_id: str) -> Invoice | None:
        return await self.session.scalar(
            self._with_lines().where(
                Invoice.organization_id == organization_id,
                Invoice.id == invoice_id,
            )
        )

    async def get_for_update(
        self, organization_id: str, invoice_id: str
    ) -> Invoice | None:
        return await self.session.scalar(
            select(Invoice)
            .where(
                Invoice.organization_id == organization_id,
                Invoice.id == invoice_id,
            )
            .with_for_update()
        )

    async def get_by_number(
        self, organization_id: str, invoice_number: str
    ) -> Invoice | None:
        return await self.session.scalar(
            select(Invoice).where(
                Invoice.organization_id == organization_id,
                Invoice.invoice_number == invoice_number,
            )
        )

    async def list(
        self,
        organization_id: str,
        status_value: str | None,
        offset: int,
        limit: int,
    ) -> list[Invoice]:
        statement = self._with_lines().where(Invoice.organization_id == organization_id)
        if status_value is not None:
            statement = statement.where(Invoice.status == status_value)
        result = await self.session.scalars(
            statement.order_by(
                Invoice.invoice_date.desc(), Invoice.invoice_number.desc()
            )
            .offset(offset)
            .limit(limit)
        )
        return list(result.unique())

    async def create(
        self,
        organization_id: str,
        data: InvoiceCreate,
        prepared_lines: list[dict[str, object]],
        totals: dict[str, object],
    ) -> Invoice:
        invoice = Invoice(
            **data.model_dump(exclude={"lines"}),
            **totals,
            organization_id=organization_id,
        )
        self.session.add(invoice)
        await self.session.flush()
        self.session.add_all(
            [InvoiceLine(invoice_id=invoice.id, **line) for line in prepared_lines]
        )
        await self.session.flush()
        return invoice

    async def update(self, invoice: Invoice, data: InvoiceUpdate) -> Invoice:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(invoice, field, value)
        await self.session.flush()
        return invoice
