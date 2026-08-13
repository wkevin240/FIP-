from app.models.fixed_assets.depreciation import (
    DepreciationPlan,
    DepreciationScheduleLine,
)
from app.models.fixed_assets.disposal import FixedAssetDisposal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class DepreciationPlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_asset(
        self, organization_id: str, asset_id: str
    ) -> list[DepreciationPlan]:
        result = await self.session.scalars(
            select(DepreciationPlan)
            .options(selectinload(DepreciationPlan.schedule_lines))
            .where(
                DepreciationPlan.organization_id == organization_id,
                DepreciationPlan.asset_id == asset_id,
            )
            .order_by(DepreciationPlan.component_id, DepreciationPlan.version_number)
        )
        return list(result)

    async def create(self, plan: DepreciationPlan) -> DepreciationPlan:
        self.session.add(plan)
        await self.session.flush()
        return plan


class DepreciationScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, organization_id: str, schedule_line_id: str, for_update: bool = False
    ) -> DepreciationScheduleLine | None:
        statement = (
            select(DepreciationScheduleLine)
            .options(selectinload(DepreciationScheduleLine.plan))
            .where(
                DepreciationScheduleLine.organization_id == organization_id,
                DepreciationScheduleLine.id == schedule_line_id,
            )
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def list_for_plan(
        self, organization_id: str, plan_id: str
    ) -> list[DepreciationScheduleLine]:
        result = await self.session.scalars(
            select(DepreciationScheduleLine)
            .where(
                DepreciationScheduleLine.organization_id == organization_id,
                DepreciationScheduleLine.plan_id == plan_id,
            )
            .order_by(DepreciationScheduleLine.sequence_number)
        )
        return list(result)

    async def list_due(
        self, organization_id: str, asset_id: str, through_date
    ) -> list[DepreciationScheduleLine]:
        result = await self.session.scalars(
            select(DepreciationScheduleLine)
            .join(DepreciationPlan)
            .options(selectinload(DepreciationScheduleLine.plan))
            .where(
                DepreciationScheduleLine.organization_id == organization_id,
                DepreciationPlan.asset_id == asset_id,
                DepreciationScheduleLine.status == "PLANNED",
                DepreciationScheduleLine.scheduled_date <= through_date,
            )
            .order_by(DepreciationScheduleLine.scheduled_date)
        )
        return list(result)


class FixedAssetDisposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_asset(
        self, organization_id: str, asset_id: str
    ) -> FixedAssetDisposal | None:
        return await self.session.scalar(
            select(FixedAssetDisposal).where(
                FixedAssetDisposal.organization_id == organization_id,
                FixedAssetDisposal.asset_id == asset_id,
            )
        )

    async def create(self, disposal: FixedAssetDisposal) -> FixedAssetDisposal:
        self.session.add(disposal)
        await self.session.flush()
        return disposal
