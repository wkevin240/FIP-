from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditEventResponse(BaseModel):
    id: str
    organization_id: str
    sequence_number: int
    occurred_at: datetime
    actor_user_id: str | None
    action: str
    resource_type: str
    resource_id: str
    previous_value: str | None
    new_value: str | None
    context: str | None
    transaction_id: str | None
    request_id: str | None
    previous_hash: str
    event_hash: str

    model_config = ConfigDict(from_attributes=True)


class AuditEventPage(BaseModel):
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    items: list[AuditEventResponse]


class AuditEventFilter(BaseModel):
    action: str | None = Field(default=None, max_length=96)
    resource_type: str | None = Field(default=None, max_length=96)
    resource_id: str | None = None
    actor_user_id: str | None = None
    transaction_id: str | None = Field(default=None, max_length=96)
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None


class AuditIntegrityCheck(BaseModel):
    organization_id: str
    checked_events: int
    is_valid: bool
    invalid_sequence_number: int | None = None
    details: str | None = None


class AuditEventContext(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
