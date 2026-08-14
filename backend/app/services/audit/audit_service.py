import json
from datetime import datetime
from typing import Any

from app.domain.audit.chain.rules import AuditChainRules, AuditEventPayload
from app.models.audit.audit_event import AuditEvent
from app.repositories.audit.audit_event_repository import AuditEventRepository
from app.schemas.audit.audit_event import AuditIntegrityCheck
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AuditEventRepository(session)

    async def record(
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
    ) -> AuditEvent:
        return await self.repository.append(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            previous_value=previous_value,
            new_value=new_value,
            context=context,
            transaction_id=transaction_id,
            request_id=request_id,
        )

    async def list_events(
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
        return await self.repository.list(
            organization_id,
            offset,
            min(limit, 100),
            action,
            resource_type,
            resource_id,
            actor_user_id,
            transaction_id,
            occurred_from,
            occurred_to,
        )

    async def verify_integrity(self, organization_id: str) -> AuditIntegrityCheck:
        events = list(
            await self.session.scalars(
                select(AuditEvent)
                .where(AuditEvent.organization_id == organization_id)
                .order_by(AuditEvent.sequence_number)
            )
        )
        previous_hash = "0" * 64
        expected_sequence = 1
        for event in events:
            if (
                event.sequence_number != expected_sequence
                or event.previous_hash != previous_hash
            ):
                return AuditIntegrityCheck(
                    organization_id=organization_id,
                    checked_events=expected_sequence - 1,
                    is_valid=False,
                    invalid_sequence_number=event.sequence_number,
                    details="Audit sequence or predecessor hash is inconsistent",
                )
            payload = AuditEventPayload(
                organization_id=event.organization_id,
                sequence_number=event.sequence_number,
                occurred_at=event.occurred_at,
                actor_user_id=event.actor_user_id,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                previous_value=json.loads(event.previous_value)
                if event.previous_value
                else None,
                new_value=json.loads(event.new_value) if event.new_value else None,
                context=json.loads(event.context) if event.context else None,
                transaction_id=event.transaction_id,
                request_id=event.request_id,
                previous_hash=event.previous_hash,
            )
            if AuditChainRules.compute_hash(payload) != event.event_hash:
                return AuditIntegrityCheck(
                    organization_id=organization_id,
                    checked_events=expected_sequence - 1,
                    is_valid=False,
                    invalid_sequence_number=event.sequence_number,
                    details="Audit event hash is inconsistent",
                )
            previous_hash = event.event_hash
            expected_sequence += 1
        return AuditIntegrityCheck(
            organization_id=organization_id,
            checked_events=len(events),
            is_valid=True,
        )
