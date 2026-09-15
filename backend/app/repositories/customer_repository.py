from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer


class CustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, organization_id: str, customer_id: str) -> Customer | None:
        return await self.session.scalar(
            select(Customer).where(
                Customer.organization_id == organization_id,
                Customer.id == customer_id,
            )
        )

    async def get_for_update(self, organization_id: str, customer_id: str) -> Customer | None:
        """Load a customer while serializing concurrent mutations on its row."""
        return await self.session.scalar(
            select(Customer)
            .where(
                Customer.organization_id == organization_id,
                Customer.id == customer_id,
            )
            .with_for_update()
        )

    async def get_by_code(self, organization_id: str, code: str) -> Customer | None:
        return await self.session.scalar(
            select(Customer).where(
                Customer.organization_id == organization_id,
                Customer.code == code,
            )
        )

    async def get_by_tax_id(self, organization_id: str, tax_id: str) -> Customer | None:
        return await self.session.scalar(
            select(Customer).where(
                Customer.organization_id == organization_id,
                Customer.tax_id == tax_id,
            )
        )

    async def list(
        self,
        organization_id: str,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
    ) -> list[Customer]:
        statement = select(Customer).where(Customer.organization_id == organization_id)
        if is_active is not None:
            statement = statement.where(Customer.is_active == is_active)

        result = await self.session.scalars(
            statement.order_by(Customer.code, Customer.id).offset(skip).limit(limit)
        )
        return list(result.all())

    def add(self, customer: Customer) -> None:
        self.session.add(customer)
