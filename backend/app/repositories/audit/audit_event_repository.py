from datetime import datetime, timezone
from typing import Any

from app.domain.audit.chain.rules import AuditChainRules, AuditEventPayload
from app.models.audit.audit_event import AuditEvent, AuditSequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class AuditEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(
        self,
        organization_id: str,
        actor_user_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str,
        previous_value: dict[str, Any] | None = None,
        new_value: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        transaction_id: str | None = None,
        request_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> AuditEvent:
        sequence = await self._get_or_create_sequence(organization_id)
        occurred_at = occurred_at or datetime.now(timezone.utc).replace(tzinfo=None)
        AuditChainRules.validate_append(
            action, resource_type, resource_id, sequence.last_hash
        )
        sequence_number = sequence.last_sequence + 1
        payload = AuditEventPayload(
            organization_id=organization_id,
            sequence_number=sequence_number,
            occurred_at=occurred_at,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            previous_value=previous_value,
            new_value=new_value,
            context=context,
            transaction_id=transaction_id,
            request_id=request_id,
            previous_hash=sequence.last_hash,
        )
        event_hash = AuditChainRules.compute_hash(payload)
        event = AuditEvent(
            organization_id=organization_id,
            sequence_number=sequence_number,
            occurred_at=occurred_at,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            previous_value=AuditChainRules.canonical_json(previous_value),
            new_value=AuditChainRules.canonical_json(new_value),
            context=AuditChainRules.canonical_json(context),
            transaction_id=transaction_id,
            request_id=request_id,
            previous_hash=sequence.last_hash,
            event_hash=event_hash,
        )
        self.session.add(event)
        sequence.last_sequence = sequence_number
        sequence.last_hash = event_hash
        await self.session.flush()
        return event

    async def list(
        self,
        organization_id: str,
        offset: int,
        limit: int,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        actor_user_id: str | None = None,
        transaction_id: str | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> list[AuditEvent]:
        statement = select(AuditEvent).where(
            AuditEvent.organization_id == organization_id
        )
        if action:
            statement = statement.where(AuditEvent.action == action)
        if resource_type:
            statement = statement.where(AuditEvent.resource_type == resource_type)
        if resource_id:
            statement = statement.where(AuditEvent.resource_id == resource_id)
        if actor_user_id:
            statement = statement.where(AuditEvent.actor_user_id == actor_user_id)
        if transaction_id:
            statement = statement.where(AuditEvent.transaction_id == transaction_id)
        if occurred_from:
            statement = statement.where(AuditEvent.occurred_at >= occurred_from)
        if occurred_to:
            statement = statement.where(AuditEvent.occurred_at <= occurred_to)
        result = await self.session.scalars(
            statement.order_by(AuditEvent.sequence_number.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result)

    async def get_by_id(self, organization_id: str, event_id: str) -> AuditEvent | None:
        return await self.session.scalar(
            select(AuditEvent).where(
                AuditEvent.organization_id == organization_id, AuditEvent.id == event_id
            )
        )

    async def _get_or_create_sequence(self, organization_id: str) -> AuditSequence:
        sequence = await self.session.scalar(
            select(AuditSequence)
            .where(AuditSequence.organization_id == organization_id)
            .with_for_update()
        )
        if sequence is None:
            sequence = AuditSequence(organization_id=organization_id)
            self.session.add(sequence)
            await self.session.flush()
        return sequence
