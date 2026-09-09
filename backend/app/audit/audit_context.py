from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class AuditContext:
    """Immutable actor/request context attached to auditable operations."""

    organization_id: str
    actor_id: str
    action: str
    request_id: str | None = None
    occurred_at: datetime | None = None

    def timestamp(self) -> datetime:
        value = self.occurred_at or datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
