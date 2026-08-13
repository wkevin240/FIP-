from app.models.inventory.product import Product
from app.schemas.inventory.product import ProductCreate, ProductUpdate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, organization_id: str, product_id: str) -> Product | None:
        return await self.session.scalar(
            select(Product).where(
                Product.organization_id == organization_id,
                Product.id == product_id,
            )
        )

    async def get_by_sku(self, organization_id: str, sku: str) -> Product | None:
        return await self.session.scalar(
            select(Product).where(
                Product.organization_id == organization_id,
                Product.sku == sku,
            )
        )

    async def list(
        self,
        organization_id: str,
        offset: int,
        limit: int,
        active_only: bool,
    ) -> list[Product]:
        statement = (
            select(Product)
            .where(Product.organization_id == organization_id)
            .order_by(Product.sku)
            .offset(offset)
            .limit(limit)
        )
        if active_only:
            statement = statement.where(Product.is_active.is_(True))
        result = await self.session.scalars(statement)
        return list(result)

    async def create(self, organization_id: str, data: ProductCreate) -> Product:
        product = Product(**data.model_dump(), organization_id=organization_id)
        self.session.add(product)
        await self.session.flush()
        return product

    async def update(self, product: Product, data: ProductUpdate) -> Product:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(product, field, value)
        await self.session.flush()
        return product
