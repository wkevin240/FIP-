from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DomainEvent:
    name: str
    organization_id: str
    entity_id: str
    payload: dict[str, Any]


Handler = Callable[[DomainEvent], None]


class EventBus:
    """Small in-process event bus used to decouple domain actions from side effects."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    def publish(self, event: DomainEvent) -> None:
        for handler in tuple(self._handlers.get(event.name, ())):
            handler(event)
