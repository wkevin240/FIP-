from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import Supplier


class SupplierRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, organization_id: str, supplier_id: str) -> Supplier | None:
        return await self.session.scalar(
            select(Supplier).where(
                Supplier.organization_id == organization_id,
                Supplier.id == supplier_id,
            )
        )

    async def get_for_update(self, organization_id: str, supplier_id: str) -> Supplier | None:
        return await self.session.scalar(
            select(Supplier)
            .where(Supplier.organization_id == organization_id, Supplier.id == supplier_id)
            .with_for_update()
        )

    async def get_by_code(self, organization_id: str, code: str) -> Supplier | None:
        return await self.session.scalar(
            select(Supplier).where(Supplier.organization_id == organization_id, Supplier.code == code)
        )

    async def get_by_tax_id(self, organization_id: str, tax_id: str) -> Supplier | None:
        return await self.session.scalar(
            select(Supplier).where(Supplier.organization_id == organization_id, Supplier.tax_id == tax_id)
        )

    async def list(
        self,
        organization_id: str,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
    ) -> list[Supplier]:
        statement = select(Supplier).where(Supplier.organization_id == organization_id)
        if is_active is not None:
            statement = statement.where(Supplier.is_active == is_active)
        result = await self.session.scalars(
            statement.order_by(Supplier.code, Supplier.id).offset(skip).limit(limit)
        )
        return list(result.all())

    def add(self, supplier: Supplier) -> None:
        self.session.add(supplier)
