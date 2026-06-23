"""Stream A — DashboardDelta(scope=incident) fan-out on event_bus normalized.

Unit-level: we attach a fake WebSocket-like consumer directly to
`dashboard_bus`, register the incident subscriber, then publish an
EventNormalizedMessage. This deliberately avoids the TestClient +
lifespan + in-memory SQLite combination, which fails in the existing
test_dashboard.py suite too (pre-existing, unrelated to this stream).
"""

import asyncio
from datetime import UTC, datetime

import pytest

from grid_unlocked.dashboard.bus import dashboard_bus
from grid_unlocked.dashboard.incident_subscriber import register_incident_subscribers
from grid_unlocked.dashboard.schemas import DeltaScope
from grid_unlocked.ingestion.bus import event_bus
from grid_unlocked.ingestion.schemas import (
    EventNormalizedMessage,
    IngestSource,
    NormalizedEvent,
)


class _FakeWebSocket:
    """Stand-in for a real WebSocket — captures payloads sent by dashboard_bus."""

    def __init__(self) -> None:
        self.received: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.received.append(payload)


def _normalized(event_id: str) -> EventNormalizedMessage:
    event = NormalizedEvent(
        event_id=event_id,
        source=IngestSource.ASTRAM,
        event_type="unplanned",
        is_planned=False,
        event_cause="accident",
        status="active",
        authenticated=True,
        latitude=12.969,
        longitude=77.701,
        corridor="ORR East 1",
        junction="Marathahalli",
        priority="High",
        requires_road_closure=True,
        start_datetime=datetime(2024, 3, 7, 12, 0, tzinfo=UTC),
    )
    return EventNormalizedMessage(event=event)


@pytest.mark.asyncio
async def test_incident_subscriber_publishes_to_dashboard_bus():
    register_incident_subscribers()
    ws = _FakeWebSocket()
    dashboard_bus.register(ws)
    try:
        await event_bus.publish_normalized(_normalized("INC-UNIT-1"))
        incidents = [m for m in ws.received if m.get("scope") == DeltaScope.INCIDENT.value]
        assert incidents, f"no incident scope in {ws.received!r}"
        msg = incidents[0]
        assert msg["type"] == "dashboard.delta"
        assert msg["event_id"] == "INC-UNIT-1"
        payload = msg["payload"]
        assert payload["corridor"] == "ORR East 1"
        assert payload["junction"] == "Marathahalli"
        assert payload["event_type"] == "unplanned"
        assert payload["cause"] == "accident"
        assert payload["lat"] == 12.969
        assert payload["lng"] == 77.701
        assert payload["status"] == "active"
    finally:
        dashboard_bus.unregister(ws)


@pytest.mark.asyncio
async def test_incident_subscriber_does_not_break_ingest_when_fanout_fails():
    """A broken WebSocket must not raise out of the subscriber — the
    `publish` path swallows per-connection errors and the subscriber
    additionally wraps in try/except + log."""

    class _BrokenWebSocket(_FakeWebSocket):
        async def send_json(self, payload: dict) -> None:
            raise RuntimeError("simulated client failure")

    register_incident_subscribers()
    broken = _BrokenWebSocket()
    good = _FakeWebSocket()
    dashboard_bus.register(broken)
    dashboard_bus.register(good)
    try:
        await event_bus.publish_normalized(_normalized("INC-UNIT-2"))
        assert any(m.get("scope") == DeltaScope.INCIDENT.value for m in good.received)
    finally:
        dashboard_bus.unregister(broken)
        dashboard_bus.unregister(good)


@pytest.mark.asyncio
async def test_incident_subscriber_idempotent():
    """Calling register twice must not double-fire the subscriber."""
    register_incident_subscribers()
    register_incident_subscribers()
    ws = _FakeWebSocket()
    dashboard_bus.register(ws)
    try:
        await event_bus.publish_normalized(_normalized("INC-UNIT-3"))
        # Allow one event-loop tick for any extra coroutines to drain.
        await asyncio.sleep(0)
        incidents = [m for m in ws.received if m.get("scope") == DeltaScope.INCIDENT.value]
        assert len(incidents) == 1
    finally:
        dashboard_bus.unregister(ws)
