"""M15 — in-process WebSocket fanout, mirrors ingestion/bus.py::InProcessEventBus."""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

from grid_unlocked.dashboard.schemas import DashboardDelta

logger = logging.getLogger(__name__)


class DashboardBus:
    """MVP fanout — in-process pub/sub until Redis/Kafka in Phase 1.5."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    def register(self, websocket: WebSocket) -> None:
        self._connections.append(websocket)

    def unregister(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def publish(self, delta: DashboardDelta) -> None:
        if not self._connections:
            return
        payload = delta.model_dump(mode="json")
        results = await asyncio.gather(
            *(ws.send_json(payload) for ws in list(self._connections)),
            return_exceptions=True,
        )
        for ws, result in zip(list(self._connections), results, strict=True):
            if isinstance(result, Exception):
                logger.info("Dashboard client send failed, dropping connection: %s", result)
                self.unregister(ws)


dashboard_bus = DashboardBus()
