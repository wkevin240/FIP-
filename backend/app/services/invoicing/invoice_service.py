from datetime import datetime, timezone
from decimal import Decimal

from app.domain.invoicing.invoice.rules import InvoiceLineCalculation, InvoiceRules
from app.models.invoicing.invoice import Invoice
from app.repositories.accounting.vat_repository import VATRepository
from app.repositories.inventory.product_repository import ProductRepository
from app.repositories.invoicing.invoice_repository import InvoiceRepository
from app.schemas.invoicing.invoice import InvoiceCreate, InvoiceUpdate
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class InvoiceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.invoices = InvoiceRepository(session)
        self.products = ProductRepository(session)
        self.vat_rates = VATRepository(session)

    async def get_invoice(self, organization_id: str, invoice_id: str) -> Invoice:
        invoice = await self.invoices.get_by_id(organization_id, invoice_id)
        if invoice is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
            )
        return invoice

    async def list_invoices(
        self,
        organization_id: str,
        status_value: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Invoice]:
        return await self.invoices.list(
            organization_id,
            status_value,
            max(offset, 0),
            min(max(limit, 1), 100),
        )

    async def create_invoice(
        self, organization_id: str, data: InvoiceCreate
    ) -> Invoice:
        try:
            InvoiceRules.validate_dates(data.invoice_date, data.due_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        if await self.invoices.get_by_number(organization_id, data.invoice_number):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invoice number already exists",
            )
        prepared_lines, calculations = await self._prepare_lines(organization_id, data)
        totals = InvoiceRules.aggregate(calculations)
        try:
            invoice = await self.invoices.create(
                organization_id,
                data,
                prepared_lines,
                {
                    "subtotal": totals.subtotal,
                    "tax_amount": totals.tax_amount,
                    "total_amount": totals.total_amount,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invoice number already exists",
            ) from exc
        return await self.get_invoice(organization_id, invoice.id)

    async def update_invoice(
        self, organization_id: str, invoice_id: str, data: InvoiceUpdate
    ) -> Invoice:
        invoice = await self.get_invoice(organization_id, invoice_id)
        try:
            InvoiceRules.validate_issue_transition(invoice.status)
            due_date = (
                data.due_date
                if "due_date" in data.model_fields_set
                else invoice.due_date
            )
            InvoiceRules.validate_dates(invoice.invoice_date, due_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        await self.invoices.update(invoice, data)
        await self.session.commit()
        return await self.get_invoice(organization_id, invoice.id)

    async def issue_invoice(self, organization_id: str, invoice_id: str) -> Invoice:
        invoice = await self.invoices.get_for_update(organization_id, invoice_id)
        if invoice is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
            )
        try:
            InvoiceRules.validate_issue_transition(invoice.status)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        invoice.status = "ISSUED"
        invoice.issued_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.session.commit()
        return await self.get_invoice(organization_id, invoice.id)

    async def _prepare_lines(
        self, organization_id: str, data: InvoiceCreate
    ) -> tuple[list[dict[str, object]], list[InvoiceLineCalculation]]:
        prepared_lines: list[dict[str, object]] = []
        calculations: list[InvoiceLineCalculation] = []
        for sort_order, line in enumerate(data.lines, start=1):
            if line.product_id is not None:
                product = await self.products.get_by_id(
                    organization_id, line.product_id
                )
                if product is None or not product.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="Active product not found",
                    )
            tax_rate = Decimal("0.00")
            if line.vat_rate_id is not None:
                vat_rate = await self.vat_rates.get_effective_rate(
                    organization_id, line.vat_rate_id, data.invoice_date
                )
                if vat_rate is None:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="Active VAT rate not found for invoice date",
                    )
                tax_rate = Decimal(vat_rate.rate)
            try:
                calculation = InvoiceRules.calculate_line(
                    line.quantity, line.unit_price, tax_rate
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
                ) from exc
            calculations.append(calculation)
            prepared_lines.append(
                {
                    "product_id": line.product_id,
                    "vat_rate_id": line.vat_rate_id,
                    "description": line.description,
                    "quantity": line.quantity,
                    "unit_price": line.unit_price,
                    "tax_rate": tax_rate,
                    "line_subtotal": calculation.subtotal,
                    "tax_amount": calculation.tax_amount,
                    "line_total": calculation.total,
                    "sort_order": sort_order,
                }
            )
        return prepared_lines, calculations
