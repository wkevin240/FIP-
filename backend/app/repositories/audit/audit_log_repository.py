from __future__ import annotations

import json

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.audit_context import AuditContext
from app.audit.audit_service import AuditRecord, AuditService
from app.models.audit.audit_log import AuditLog
from app.models.organization import Organization


class AuditChainConflictError(RuntimeError):
    """Raised when an append cannot preserve the organization's audit chain."""


class AuditLogRepository:
    """Persist tenant-scoped audit records as a serialized hash chain."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def append(
        self,
        context: AuditContext,
        *,
        entity_type: str,
        entity_id: str,
        payload: dict,
    ) -> AuditRecord:
        organization = await self.db.scalar(
            select(Organization.id)
            .where(Organization.id == context.organization_id)
            .with_for_update()
        )
        if organization is None:
            raise LookupError(f"Organization {context.organization_id} not found")

        latest = await self.db.scalar(
            select(AuditLog)
            .where(AuditLog.organization_id == context.organization_id)
            .order_by(desc(AuditLog.sequence_no))
            .limit(1)
        )
        previous_hash = latest.record_hash if latest is not None else None
        sequence_no = latest.sequence_no + 1 if latest is not None else 1

        record = AuditService.record(
            context,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            previous_hash=previous_hash,
        )
        persisted = AuditLog(
            organization_id=record.organization_id,
            sequence_no=sequence_no,
            actor_id=record.actor_id,
            action=record.action,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            payload_json=AuditService.canonical_payload_json(record.payload),
            occurred_at=record.occurred_at,
            previous_hash=record.previous_hash,
            record_hash=record.record_hash,
            request_id=record.request_id,
        )
        self.db.add(persisted)
        await self.db.flush()
        return record

    async def list_for_organization(self, organization_id: str) -> list[AuditRecord]:
        rows = (
            await self.db.scalars(
                select(AuditLog)
                .where(AuditLog.organization_id == organization_id)
                .order_by(AuditLog.sequence_no)
            )
        ).all()
        return [
            AuditRecord(
                organization_id=row.organization_id,
                actor_id=row.actor_id,
                action=row.action,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                payload=json.loads(row.payload_json),
                occurred_at=row.occurred_at,
                previous_hash=row.previous_hash,
                record_hash=row.record_hash,
                request_id=row.request_id,
            )
            for row in rows
        ]
