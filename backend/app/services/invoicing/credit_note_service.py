from datetime import datetime, timezone
from decimal import Decimal

from app.core.enums.invoicing import InvoiceStatus
from app.domain.invoicing.invoice.rules import InvoiceRules
from app.models.invoicing.credit_note import CreditNote
from app.repositories.invoicing.credit_note_repository import CreditNoteRepository
from app.repositories.invoicing.invoice_repository import InvoiceRepository
from app.schemas.invoicing.credit_note import CreditNoteCreate
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class CreditNoteService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.credit_notes = CreditNoteRepository(session)
        self.invoices = InvoiceRepository(session)

    async def create_credit_note(
        self, organization_id: str, data: CreditNoteCreate
    ) -> CreditNote:
        if await self.credit_notes.get_by_number(
            organization_id, data.credit_note_number
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Credit note number already exists",
            )
        try:
            invoice = await self.invoices.get_for_update(
                organization_id, data.invoice_id
            )
            if invoice is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
                )
            if invoice.status not in {
                InvoiceStatus.ISSUED,
                InvoiceStatus.PARTIALLY_PAID,
            }:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Only issued invoices with an outstanding amount can be credited",
                )
            if data.credit_date < invoice.invoice_date:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Credit note date must not precede invoice date",
                )
            try:
                status_value, paid_amount, credited_amount = InvoiceRules.apply_credit(
                    Decimal(invoice.total_amount),
                    Decimal(invoice.paid_amount),
                    Decimal(invoice.credited_amount),
                    data.amount,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
                ) from exc
            invoice.status = status_value
            invoice.paid_amount = paid_amount
            invoice.credited_amount = credited_amount
            credit_note = await self.credit_notes.create(
                organization_id,
                data,
                datetime.now(timezone.utc).replace(tzinfo=None),
            )
            await self.session.commit()
        except HTTPException:
            await self.session.rollback()
            raise
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Credit note number already exists",
            ) from exc
        await self.session.refresh(credit_note)
        return credit_note

    async def list_credit_notes(
        self, organization_id: str, invoice_id: str
    ) -> list[CreditNote]:
        return await self.credit_notes.list_by_invoice(organization_id, invoice_id)
