from app.models.fixed_assets.asset import FixedAsset, FixedAssetComponent
from app.schemas.fixed_assets.asset import (
    FixedAssetComponentCreate,
    FixedAssetCreate,
    FixedAssetUpdate,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class FixedAssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _detail(self, statement):
        return statement.options(
            selectinload(FixedAsset.components),
            selectinload(FixedAsset.plans),
            selectinload(FixedAsset.disposals),
        )

    async def get_by_id(
        self, organization_id: str, asset_id: str, for_update: bool = False
    ) -> FixedAsset | None:
        statement = select(FixedAsset).where(
            FixedAsset.organization_id == organization_id, FixedAsset.id == asset_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(self._detail(statement))

    async def get_by_code(
        self, organization_id: str, asset_code: str
    ) -> FixedAsset | None:
        return await self.session.scalar(
            self._detail(
                select(FixedAsset).where(
                    FixedAsset.organization_id == organization_id,
                    FixedAsset.asset_code == asset_code,
                )
            )
        )

    async def list(
        self, organization_id: str, status_value: str | None, offset: int, limit: int
    ) -> list[FixedAsset]:
        statement = select(FixedAsset).where(
            FixedAsset.organization_id == organization_id
        )
        if status_value is not None:
            statement = statement.where(FixedAsset.status == status_value)
        result = await self.session.scalars(
            self._detail(
                statement.order_by(FixedAsset.asset_code).offset(offset).limit(limit)
            )
        )
        return list(result)

    async def create(self, organization_id: str, data: FixedAssetCreate) -> FixedAsset:
        asset = FixedAsset(organization_id=organization_id, **data.model_dump())
        self.session.add(asset)
        await self.session.flush()
        return asset

    async def update(self, asset: FixedAsset, data: FixedAssetUpdate) -> None:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(asset, field, value)


class FixedAssetComponentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, organization_id: str, component_id: str, for_update: bool = False
    ) -> FixedAssetComponent | None:
        statement = select(FixedAssetComponent).where(
            FixedAssetComponent.organization_id == organization_id,
            FixedAssetComponent.id == component_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def total_cost_for_asset(self, organization_id: str, asset_id: str) -> object:
        return await self.session.scalar(
            select(
                func.coalesce(func.sum(FixedAssetComponent.acquisition_cost), 0)
            ).where(
                FixedAssetComponent.organization_id == organization_id,
                FixedAssetComponent.asset_id == asset_id,
                FixedAssetComponent.status != "RETIRED",
            )
        )

    async def create(
        self,
        organization_id: str,
        asset_id: str,
        data: FixedAssetComponentCreate,
    ) -> FixedAssetComponent:
        component = FixedAssetComponent(
            organization_id=organization_id, asset_id=asset_id, **data.model_dump()
        )
        self.session.add(component)
        await self.session.flush()
        return component

    async def list_for_asset(
        self, organization_id: str, asset_id: str
    ) -> list[FixedAssetComponent]:
        result = await self.session.scalars(
            select(FixedAssetComponent)
            .where(
                FixedAssetComponent.organization_id == organization_id,
                FixedAssetComponent.asset_id == asset_id,
            )
            .order_by(FixedAssetComponent.component_code)
        )
        return list(result)
