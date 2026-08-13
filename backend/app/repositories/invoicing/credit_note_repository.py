from datetime import datetime

from app.models.invoicing.credit_note import CreditNote
from app.schemas.invoicing.credit_note import CreditNoteCreate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class CreditNoteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_number(
        self, organization_id: str, credit_note_number: str
    ) -> CreditNote | None:
        return await self.session.scalar(
            select(CreditNote).where(
                CreditNote.organization_id == organization_id,
                CreditNote.credit_note_number == credit_note_number,
            )
        )

    async def create(
        self, organization_id: str, data: CreditNoteCreate, issued_at: datetime
    ) -> CreditNote:
        credit_note = CreditNote(
            **data.model_dump(), organization_id=organization_id, issued_at=issued_at
        )
        self.session.add(credit_note)
        await self.session.flush()
        return credit_note

    async def list_by_invoice(
        self, organization_id: str, invoice_id: str
    ) -> list[CreditNote]:
        result = await self.session.scalars(
            select(CreditNote)
            .where(
                CreditNote.organization_id == organization_id,
                CreditNote.invoice_id == invoice_id,
            )
            .order_by(CreditNote.credit_date.desc(), CreditNote.created_at.desc())
        )
        return list(result)
