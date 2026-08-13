from app.models.inventory.warehouse import Warehouse
from app.repositories.inventory.warehouse_repository import WarehouseRepository
from app.schemas.inventory.warehouse import WarehouseCreate, WarehouseUpdate
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class WarehouseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = WarehouseRepository(session)

    async def get_warehouse(self, organization_id: str, warehouse_id: str) -> Warehouse:
        warehouse = await self.repository.get_by_id(organization_id, warehouse_id)
        if warehouse is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found"
            )
        return warehouse

    async def list_warehouses(
        self,
        organization_id: str,
        offset: int = 0,
        limit: int = 100,
        active_only: bool = False,
    ) -> list[Warehouse]:
        return await self.repository.list(
            organization_id, max(offset, 0), min(max(limit, 1), 100), active_only
        )

    async def create_warehouse(
        self, organization_id: str, data: WarehouseCreate
    ) -> Warehouse:
        if await self.repository.get_by_code(organization_id, data.code):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Warehouse code already exists",
            )
        try:
            warehouse = await self.repository.create(organization_id, data)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Warehouse code already exists",
            ) from exc
        await self.session.refresh(warehouse)
        return warehouse

    async def update_warehouse(
        self, organization_id: str, warehouse_id: str, data: WarehouseUpdate
    ) -> Warehouse:
        warehouse = await self.get_warehouse(organization_id, warehouse_id)
        await self.repository.update(warehouse, data)
        await self.session.commit()
        await self.session.refresh(warehouse)
        return warehouse
