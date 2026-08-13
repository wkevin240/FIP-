from app.models.inventory.product import Product
from app.repositories.inventory.product_repository import ProductRepository
from app.schemas.inventory.product import ProductCreate, ProductUpdate
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class ProductService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ProductRepository(session)

    async def get_product(self, organization_id: str, product_id: str) -> Product:
        product = await self.repository.get_by_id(organization_id, product_id)
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )
        return product

    async def list_products(
        self,
        organization_id: str,
        offset: int = 0,
        limit: int = 100,
        active_only: bool = False,
    ) -> list[Product]:
        return await self.repository.list(
            organization_id, max(offset, 0), min(max(limit, 1), 100), active_only
        )

    async def create_product(
        self, organization_id: str, data: ProductCreate
    ) -> Product:
        if await self.repository.get_by_sku(organization_id, data.sku):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Product SKU already exists",
            )
        try:
            product = await self.repository.create(organization_id, data)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Product SKU already exists",
            ) from exc
        await self.session.refresh(product)
        return product

    async def update_product(
        self, organization_id: str, product_id: str, data: ProductUpdate
    ) -> Product:
        product = await self.get_product(organization_id, product_id)
        await self.repository.update(product, data)
        await self.session.commit()
        await self.session.refresh(product)
        return product
