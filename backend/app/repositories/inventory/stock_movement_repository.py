from datetime import date
from decimal import Decimal

from app.core.enums.inventory import StockMovementType
from app.models.inventory.stock_movement import StockMovement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class StockMovementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        organization_id: str,
        warehouse_id: str,
        product_id: str,
        movement_type: StockMovementType,
        movement_date: date,
        quantity: Decimal,
        unit_cost: Decimal,
        total_value: Decimal,
        transfer_id: str | None,
        reference: str | None,
        note: str | None,
    ) -> StockMovement:
        movement = StockMovement(
            organization_id=organization_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            movement_type=movement_type,
            movement_date=movement_date,
            quantity=quantity,
            unit_cost=unit_cost,
            total_value=total_value,
            transfer_id=transfer_id,
            reference=reference,
            note=note,
        )
        self.session.add(movement)
        await self.session.flush()
        return movement

    async def list(
        self,
        organization_id: str,
        warehouse_id: str | None,
        product_id: str | None,
        start_date: date | None,
        end_date: date | None,
        offset: int,
        limit: int,
    ) -> list[StockMovement]:
        statement = select(StockMovement).where(
            StockMovement.organization_id == organization_id
        )
        if warehouse_id is not None:
            statement = statement.where(StockMovement.warehouse_id == warehouse_id)
        if product_id is not None:
            statement = statement.where(StockMovement.product_id == product_id)
        if start_date is not None:
            statement = statement.where(StockMovement.movement_date >= start_date)
        if end_date is not None:
            statement = statement.where(StockMovement.movement_date <= end_date)
        result = await self.session.scalars(
            statement.order_by(
                StockMovement.movement_date.desc(), StockMovement.created_at.desc()
            )
            .offset(offset)
            .limit(limit)
        )
        return list(result)
