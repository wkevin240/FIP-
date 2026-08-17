from app.models.invoicing.settlement_accounting import (
    CreditNoteAccountingPosting,
    PaymentAccountingPosting,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class SettlementAccountingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def credit_posting(self, organization_id: str, source_id: str):
        return await self.session.scalar(
            select(CreditNoteAccountingPosting).where(
                CreditNoteAccountingPosting.organization_id == organization_id,
                CreditNoteAccountingPosting.source_id == source_id,
            )
        )

    async def payment_posting(self, organization_id: str, source_id: str):
        return await self.session.scalar(
            select(PaymentAccountingPosting).where(
                PaymentAccountingPosting.organization_id == organization_id,
                PaymentAccountingPosting.source_id == source_id,
            )
        )

    async def create_credit_posting(
        self, organization_id: str, source_id: str, entry_id: str, key: str
    ):
        value = CreditNoteAccountingPosting(
            organization_id=organization_id,
            source_id=source_id,
            journal_entry_id=entry_id,
            idempotency_key=key,
        )
        self.session.add(value)
        await self.session.flush()
        return value

    async def create_payment_posting(
        self,
        organization_id: str,
        source_id: str,
        entry_id: str,
        settlement_account_id: str,
        key: str,
    ):
        value = PaymentAccountingPosting(
            organization_id=organization_id,
            source_id=source_id,
            journal_entry_id=entry_id,
            settlement_account_id=settlement_account_id,
            idempotency_key=key,
        )
        self.session.add(value)
        await self.session.flush()
        return value
