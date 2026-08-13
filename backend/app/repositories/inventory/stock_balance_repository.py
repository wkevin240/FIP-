from app.models.inventory.stock_balance import StockBalance
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class StockBalanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(
        self, organization_id: str, warehouse_id: str, product_id: str
    ) -> StockBalance | None:
        return await self.session.scalar(
            select(StockBalance).where(
                StockBalance.organization_id == organization_id,
                StockBalance.warehouse_id == warehouse_id,
                StockBalance.product_id == product_id,
            )
        )

    async def get_for_update(
        self, organization_id: str, warehouse_id: str, product_id: str
    ) -> StockBalance | None:
        return await self.session.scalar(
            select(StockBalance)
            .where(
                StockBalance.organization_id == organization_id,
                StockBalance.warehouse_id == warehouse_id,
                StockBalance.product_id == product_id,
            )
            .with_for_update()
        )

    async def list(
        self,
        organization_id: str,
        warehouse_id: str | None,
        product_id: str | None,
        below_reorder_point: bool,
        offset: int,
        limit: int,
    ) -> list[StockBalance]:
        statement = select(StockBalance).where(
            StockBalance.organization_id == organization_id
        )
        if warehouse_id is not None:
            statement = statement.where(StockBalance.warehouse_id == warehouse_id)
        if product_id is not None:
            statement = statement.where(StockBalance.product_id == product_id)
        if below_reorder_point:
            from app.models.inventory.product import Product

            statement = statement.join(Product).where(
                StockBalance.quantity <= Product.reorder_point
            )
        result = await self.session.scalars(
            statement.order_by(StockBalance.warehouse_id, StockBalance.product_id)
            .offset(offset)
            .limit(limit)
        )
        return list(result)

    async def create(
        self,
        organization_id: str,
        warehouse_id: str,
        product_id: str,
    ) -> StockBalance:
        balance = StockBalance(
            organization_id=organization_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
        )
        self.session.add(balance)
        await self.session.flush()
        return balance
