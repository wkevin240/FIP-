from app.models.inventory.warehouse import Warehouse
from app.schemas.inventory.warehouse import WarehouseCreate, WarehouseUpdate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class WarehouseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, organization_id: str, warehouse_id: str
    ) -> Warehouse | None:
        return await self.session.scalar(
            select(Warehouse).where(
                Warehouse.organization_id == organization_id,
                Warehouse.id == warehouse_id,
            )
        )

    async def get_by_code(self, organization_id: str, code: str) -> Warehouse | None:
        return await self.session.scalar(
            select(Warehouse).where(
                Warehouse.organization_id == organization_id,
                Warehouse.code == code,
            )
        )

    async def list(
        self,
        organization_id: str,
        offset: int,
        limit: int,
        active_only: bool,
    ) -> list[Warehouse]:
        statement = (
            select(Warehouse)
            .where(Warehouse.organization_id == organization_id)
            .order_by(Warehouse.code)
            .offset(offset)
            .limit(limit)
        )
        if active_only:
            statement = statement.where(Warehouse.is_active.is_(True))
        result = await self.session.scalars(statement)
        return list(result)

    async def create(self, organization_id: str, data: WarehouseCreate) -> Warehouse:
        warehouse = Warehouse(**data.model_dump(), organization_id=organization_id)
        self.session.add(warehouse)
        await self.session.flush()
        return warehouse

    async def update(self, warehouse: Warehouse, data: WarehouseUpdate) -> Warehouse:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(warehouse, field, value)
        await self.session.flush()
        return warehouse
