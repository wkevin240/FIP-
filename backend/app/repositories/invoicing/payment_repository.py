from datetime import datetime

from app.models.invoicing.payment import Payment
from app.schemas.invoicing.payment import PaymentCreate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_external_reference(
        self, organization_id: str, external_reference: str
    ) -> Payment | None:
        return await self.session.scalar(
            select(Payment).where(
                Payment.organization_id == organization_id,
                Payment.external_reference == external_reference,
            )
        )

    async def create(
        self, organization_id: str, data: PaymentCreate, received_at: datetime
    ) -> Payment:
        payment = Payment(
            **data.model_dump(),
            organization_id=organization_id,
            received_at=received_at,
        )
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def list_by_invoice(
        self, organization_id: str, invoice_id: str
    ) -> list[Payment]:
        result = await self.session.scalars(
            select(Payment)
            .where(
                Payment.organization_id == organization_id,
                Payment.invoice_id == invoice_id,
            )
            .order_by(Payment.payment_date.desc(), Payment.created_at.desc())
        )
        return list(result)
