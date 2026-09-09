from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from .audit_context import AuditContext


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """Tamper-evident representation of one auditable business event."""

    organization_id: str
    actor_id: str
    action: str
    entity_type: str
    entity_id: str
    payload: dict[str, Any]
    occurred_at: datetime
    previous_hash: str | None
    record_hash: str
    request_id: str | None = None


class AuditService:
    """Build deterministic audit records without coupling the domain to storage."""

    @staticmethod
    def _canonicalize(value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: AuditService._canonicalize(value[key]) for key in sorted(value)}
        if isinstance(value, (list, tuple)):
            return [AuditService._canonicalize(item) for item in value]
        return value

    @classmethod
    def _digest(cls, record: dict[str, Any]) -> str:
        canonical = json.dumps(
            cls._canonicalize(record),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @classmethod
    def record(
        cls,
        context: AuditContext,
        *,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
        previous_hash: str | None = None,
    ) -> AuditRecord:
        occurred_at = context.timestamp()
        unsigned = {
            "organization_id": context.organization_id,
            "actor_id": context.actor_id,
            "action": context.action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": payload,
            "occurred_at": occurred_at,
            "previous_hash": previous_hash,
            "request_id": context.request_id,
        }
        return AuditRecord(
            **unsigned,
            record_hash=cls._digest(unsigned),
        )

    @classmethod
    def verify_chain(cls, records: list[AuditRecord]) -> bool:
        """Verify ordering, linkage and content hashes for an organization's chain."""
        previous_hash: str | None = None
        for record in records:
            if record.previous_hash != previous_hash:
                return False
            unsigned = {
                "organization_id": record.organization_id,
                "actor_id": record.actor_id,
                "action": record.action,
                "entity_type": record.entity_type,
                "entity_id": record.entity_id,
                "payload": record.payload,
                "occurred_at": record.occurred_at,
                "previous_hash": record.previous_hash,
                "request_id": record.request_id,
            }
            if cls._digest(unsigned) != record.record_hash:
                return False
            previous_hash = record.record_hash
        return True
