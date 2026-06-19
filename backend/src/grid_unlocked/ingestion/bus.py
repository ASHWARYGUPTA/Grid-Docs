import asyncio
from collections.abc import Awaitable, Callable

from grid_unlocked.ingestion.schemas import EventClosedMessage, EventNormalizedMessage

EventNormalizedHandler = Callable[[EventNormalizedMessage], Awaitable[None] | None]
EventClosedHandler = Callable[[EventClosedMessage], Awaitable[None] | None]


class InProcessEventBus:
    """MVP event bus — in-process pub/sub until Redis/Kafka in Phase 1.5."""

    def __init__(self) -> None:
        self._normalized_handlers: list[EventNormalizedHandler] = []
        self._closed_handlers: list[EventClosedHandler] = []

    def subscribe_normalized(self, handler: EventNormalizedHandler) -> None:
        self._normalized_handlers.append(handler)

    def subscribe_closed(self, handler: EventClosedHandler) -> None:
        self._closed_handlers.append(handler)

    async def publish_normalized(self, message: EventNormalizedMessage) -> None:
        for handler in self._normalized_handlers:
            result = handler(message)
            if asyncio.iscoroutine(result):
                await result

    async def publish_closed(self, message: EventClosedMessage) -> None:
        for handler in self._closed_handlers:
            result = handler(message)
            if asyncio.iscoroutine(result):
                await result


event_bus = InProcessEventBus()
