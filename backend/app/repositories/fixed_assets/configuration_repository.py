from app.models.fixed_assets.asset_category import (
    FixedAssetAccountingProfile,
    FixedAssetCategory,
)
from app.schemas.fixed_assets.configuration import (
    FixedAssetAccountingProfileCreate,
    FixedAssetCategoryCreate,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class FixedAssetAccountingProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, organization_id: str, profile_id: str
    ) -> FixedAssetAccountingProfile | None:
        return await self.session.scalar(
            select(FixedAssetAccountingProfile).where(
                FixedAssetAccountingProfile.organization_id == organization_id,
                FixedAssetAccountingProfile.id == profile_id,
            )
        )

    async def get_by_code(
        self, organization_id: str, profile_code: str
    ) -> FixedAssetAccountingProfile | None:
        return await self.session.scalar(
            select(FixedAssetAccountingProfile).where(
                FixedAssetAccountingProfile.organization_id == organization_id,
                FixedAssetAccountingProfile.profile_code == profile_code,
            )
        )

    async def create(
        self, organization_id: str, data: FixedAssetAccountingProfileCreate
    ) -> FixedAssetAccountingProfile:
        profile = FixedAssetAccountingProfile(
            organization_id=organization_id, **data.model_dump()
        )
        self.session.add(profile)
        await self.session.flush()
        return profile


class FixedAssetCategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, organization_id: str, category_id: str
    ) -> FixedAssetCategory | None:
        return await self.session.scalar(
            select(FixedAssetCategory).where(
                FixedAssetCategory.organization_id == organization_id,
                FixedAssetCategory.id == category_id,
            )
        )

    async def get_by_code(
        self, organization_id: str, code: str
    ) -> FixedAssetCategory | None:
        return await self.session.scalar(
            select(FixedAssetCategory).where(
                FixedAssetCategory.organization_id == organization_id,
                FixedAssetCategory.code == code,
            )
        )

    async def list(
        self, organization_id: str, active_only: bool
    ) -> list[FixedAssetCategory]:
        statement = select(FixedAssetCategory).where(
            FixedAssetCategory.organization_id == organization_id
        )
        if active_only:
            statement = statement.where(FixedAssetCategory.is_active.is_(True))
        result = await self.session.scalars(statement.order_by(FixedAssetCategory.code))
        return list(result)

    async def create(
        self, organization_id: str, data: FixedAssetCategoryCreate
    ) -> FixedAssetCategory:
        category = FixedAssetCategory(
            organization_id=organization_id, **data.model_dump()
        )
        self.session.add(category)
        await self.session.flush()
        return category
