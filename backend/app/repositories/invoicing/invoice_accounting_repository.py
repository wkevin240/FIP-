from app.models.invoicing.accounting import (
    InvoiceAccountingPosting,
    InvoiceAccountingProfile,
)
from app.models.invoicing.invoice import Invoice
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class InvoiceAccountingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_profile(
        self, organization_id: str, *, for_update: bool = False
    ) -> InvoiceAccountingProfile | None:
        statement = select(InvoiceAccountingProfile).where(
            InvoiceAccountingProfile.organization_id == organization_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def create_profile(
        self, organization_id: str, data: dict[str, object]
    ) -> InvoiceAccountingProfile:
        profile = InvoiceAccountingProfile(organization_id=organization_id, **data)
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def get_posting_by_invoice(
        self, organization_id: str, invoice_id: str
    ) -> InvoiceAccountingPosting | None:
        return await self.session.scalar(
            select(InvoiceAccountingPosting)
            .options(
                selectinload(InvoiceAccountingPosting.invoice).selectinload(
                    Invoice.lines
                )
            )
            .where(
                InvoiceAccountingPosting.organization_id == organization_id,
                InvoiceAccountingPosting.source_id == invoice_id,
            )
        )

    async def get_posting_by_idempotency_key(
        self, organization_id: str, idempotency_key: str
    ) -> InvoiceAccountingPosting | None:
        return await self.session.scalar(
            select(InvoiceAccountingPosting)
            .options(
                selectinload(InvoiceAccountingPosting.invoice).selectinload(
                    Invoice.lines
                )
            )
            .where(
                InvoiceAccountingPosting.organization_id == organization_id,
                InvoiceAccountingPosting.idempotency_key == idempotency_key,
            )
        )

    async def create_posting(
        self,
        organization_id: str,
        invoice_id: str,
        journal_entry_id: str,
        idempotency_key: str,
    ) -> InvoiceAccountingPosting:
        posting = InvoiceAccountingPosting(
            organization_id=organization_id,
            source_id=invoice_id,
            journal_entry_id=journal_entry_id,
            idempotency_key=idempotency_key,
        )
        self.session.add(posting)
        await self.session.flush()
        return posting
