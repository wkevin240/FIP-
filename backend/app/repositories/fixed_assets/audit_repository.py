import json

from app.models.fixed_assets.disposal import FixedAssetAuditEvent
from app.repositories.audit.audit_event_repository import AuditEventRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class FixedAssetAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.transversal_audit = AuditEventRepository(session)

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
        await self.transversal_audit.append(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            previous_value=json.loads(previous_value) if previous_value else None,
            new_value=json.loads(new_value) if new_value else None,
            context={
                key: value
                for key, value in {
                    "asset_id": asset_id,
                    "reason": reason,
                    "context_ip": context_ip,
                }.items()
                if value is not None
            }
            or None,
            transaction_id=asset_id or resource_id,
        )
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
