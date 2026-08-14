import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AuditEventPayload:
    organization_id: str
    sequence_number: int
    occurred_at: datetime
    actor_user_id: str | None
    action: str
    resource_type: str
    resource_id: str
    previous_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    context: dict[str, Any] | None
    transaction_id: str | None
    request_id: str | None
    previous_hash: str


class AuditChainRules:
    @staticmethod
    def canonical_json(value: dict[str, Any] | None) -> str | None:
        if value is None:
            return None
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    @classmethod
    def compute_hash(cls, payload: AuditEventPayload) -> str:
        canonical = {
            "organization_id": payload.organization_id,
            "sequence_number": payload.sequence_number,
            "occurred_at": payload.occurred_at.isoformat(timespec="microseconds"),
            "actor_user_id": payload.actor_user_id,
            "action": payload.action,
            "resource_type": payload.resource_type,
            "resource_id": payload.resource_id,
            "previous_value": payload.previous_value,
            "new_value": payload.new_value,
            "context": payload.context,
            "transaction_id": payload.transaction_id,
            "request_id": payload.request_id,
            "previous_hash": payload.previous_hash,
        }
        serialized = json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), default=str
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def validate_append(
        action: str, resource_type: str, resource_id: str, previous_hash: str
    ) -> None:
        if not action or not resource_type or not resource_id:
            raise ValueError("Audit action, resource type and resource id are required")
        if len(previous_hash) != 64:
            raise ValueError("Audit previous hash must be a SHA-256 hex digest")
