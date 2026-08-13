from app.models.fixed_assets.disposal import FixedAssetAuditEvent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class FixedAssetAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(
        self,
        organization_id: str,
        actor_user_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str,
        asset_id: str | None = None,
        previous_value: str | None = None,
        new_value: str | None = None,
        reason: str | None = None,
        context_ip: str | None = None,
    ) -> FixedAssetAuditEvent:
        event = FixedAssetAuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            asset_id=asset_id,
            previous_value=previous_value,
            new_value=new_value,
            reason=reason,
            context_ip=context_ip,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_for_asset(
        self, organization_id: str, asset_id: str
    ) -> list[FixedAssetAuditEvent]:
        result = await self.session.scalars(
            select(FixedAssetAuditEvent)
            .where(
                FixedAssetAuditEvent.organization_id == organization_id,
                FixedAssetAuditEvent.asset_id == asset_id,
            )
            .order_by(FixedAssetAuditEvent.occurred_at, FixedAssetAuditEvent.id)
        )
        return list(result)
