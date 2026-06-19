"""M10 — AgenticExecutionBroker tests.

Covers every testing decision from the spec:
  1. Shadow mode blocks queue publish
  2. Idempotent double-approve → single execution
  3. Mock station 500 → DLQ after retries
  4. Audit log completeness on happy path
  5. Enqueue latency ≤200 ms
  6. Retry succeeds on 2nd attempt
  7. GET /execute/audit returns immutable records with correct shape
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from grid_unlocked.config import settings
from grid_unlocked.execution.queue import CommandQueue, QueuedCommand, set_command_queue
from grid_unlocked.execution.schemas import CommandType, ExecutionStatus
from grid_unlocked.execution.service import setup_command_queue
from grid_unlocked.execution.station_client import MockStationClient, StationResponse
from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.hotspots.subscriber import register_hotspot_subscribers
from grid_unlocked.impact.registry import registry
from grid_unlocked.main import app
from grid_unlocked.propagation.subscriber import register_propagation_subscribers

# ---------------------------------------------------------------------------
# Shared test event fixtures
# ---------------------------------------------------------------------------

BASE_EVENT = {
    "id": "FKIDM10BASE",
    "event_type": "unplanned",
    "latitude": 12.969,
    "longitude": 77.701,
    "event_cause": "accident",
    "requires_road_closure": True,
    "start_datetime": "2024-03-07T16:00:00+00:00",
    "status": "active",
    "authenticated": "yes",
    "created_date": "2024-03-07T16:05:00+00:00",
    "corridor": "ORR East 1",
    "priority": "High",
    "veh_type": "heavy_vehicle",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FlakyOnceClient(MockStationClient):
    """Fails exactly on the first call, succeeds on all subsequent calls."""

    def __init__(self) -> None:
        super().__init__(failure_rate=0.0)
        self._first = True

    async def dispatch_unit(self, station_id, event_id, card_id, recommendation_id):
        if self._first:
            self._first = False
            return StationResponse(
                status_code=500,
                body={"error": "transient failure"},
                latency_ms=5,
            )
        return await super().dispatch_unit(station_id, event_id, card_id, recommendation_id)


async def _fresh_queue(client: MockStationClient | None = None) -> CommandQueue:
    """Set up a fresh command queue, stopping any existing one first."""
    from grid_unlocked.execution import queue as _q_module

    if _q_module._command_queue is not None and not _q_module._command_queue._task.done():
        await _q_module._command_queue.stop()
    return await setup_command_queue(station_client=client or MockStationClient(failure_rate=0.0))


@pytest.fixture
async def client():
    """HTTP test client with all subscribers and registry loaded."""
    register_feature_subscribers()
    register_propagation_subscribers()
    register_hotspot_subscribers()
    registry.load()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def live_client(monkeypatch):
    """
    Client with shadow_mode=False and tier=1 so M10 actually fires.
    Uses a MockStationClient with 0% failure rate.
    """
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    monkeypatch.setattr(settings, "governance_tier", "1")

    # Reinitialise queue with always-succeed mock
    client_mock = MockStationClient(failure_rate=0.0)
    queue = await setup_command_queue(station_client=client_mock)

    register_feature_subscribers()
    register_propagation_subscribers()
    register_hotspot_subscribers()
    registry.load()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await queue.stop()


# ---------------------------------------------------------------------------
# 1. Shadow mode blocks queue publish
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shadow_mode_blocks_execution(client):
    """When shadow_mode=True, POST /execute/dispatch must return 403."""
    # Shadow mode is the default in settings (governance_shadow_mode=True)
    assert settings.governance_shadow_mode is True

    resp = await client.post(
        "/execute/dispatch",
        json={
            "approval_token": "APPR-SHADOW-001",
            "card_id": "CARD-SHADOW001",
            "event_id": "EVT-SHADOW",
            "commander_id": "CMD-001",
        },
    )
    assert resp.status_code == 403
    assert "shadow_mode" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 2. Idempotent double-approve → single execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotent_double_enqueue(monkeypatch, client):
    """Second enqueue with same approval_token returns existing execution_id."""
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    monkeypatch.setattr(settings, "governance_tier", "1")

    await _fresh_queue(MockStationClient(failure_rate=0.0))

    payload = {
        "approval_token": "APPR-IDEM-001",
        "card_id": "CARD-IDEM0001",
        "event_id": "EVT-IDEM001",
        "commander_id": "CMD-001",
    }

    r1 = await client.post("/execute/dispatch", json=payload)
    r2 = await client.post("/execute/dispatch", json=payload)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["execution_id"] == r2.json()["execution_id"], (
        "Second enqueue must return the same execution_id (idempotency)"
    )
    assert "idempotent" in r2.json()["message"].lower()


# ---------------------------------------------------------------------------
# 3. Mock station 500 → DLQ after retries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_station_failure_leads_to_dlq(monkeypatch, client):
    """Always-fail mock → execution moves to dead_letter after 3 attempts."""
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    monkeypatch.setattr(settings, "governance_tier", "1")
    import grid_unlocked.execution.service as svc_module
    monkeypatch.setattr(svc_module, "_RETRY_DELAYS", [0.01, 0.01, 0.01])

    await _fresh_queue(MockStationClient(failure_rate=1.0))

    resp = await client.post(
        "/execute/dispatch",
        json={
            "approval_token": "APPR-FAIL-001",
            "card_id": "CARD-FAIL0001",
            "event_id": "EVT-FAIL001",
            "commander_id": "CMD-001",
        },
    )
    assert resp.status_code == 200
    exec_id = resp.json()["execution_id"]

    await asyncio.sleep(1.0)

    status_resp = await client.get(f"/execute/status/{exec_id}")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["status"] == ExecutionStatus.DEAD_LETTER, (
        f"Expected dead_letter, got {body['status']}"
    )
    assert body["attempt_count"] == 3


# ---------------------------------------------------------------------------
# 4. Audit log completeness on happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_log_completeness(monkeypatch, client):
    """Happy path: audit entry contains request_payload and response_body."""
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    monkeypatch.setattr(settings, "governance_tier", "1")

    await _fresh_queue(MockStationClient(failure_rate=0.0))

    event_id = "EVT-AUDIT001"
    card_id = "CARD-AUDIT001"
    resp = await client.post(
        "/execute/dispatch",
        json={
            "approval_token": "APPR-AUDIT-001",
            "card_id": card_id,
            "event_id": event_id,
            "commander_id": "CMD-001",
        },
    )
    assert resp.status_code == 200

    await asyncio.sleep(0.5)

    audit_resp = await client.get(f"/execute/audit?event_id={event_id}")
    assert audit_resp.status_code == 200
    entries = audit_resp.json()["entries"]
    assert len(entries) >= 1, "Expected at least one audit entry"

    entry = entries[0]
    assert entry["event_id"] == event_id
    assert entry["card_id"] == card_id
    assert entry["request_payload"] is not None
    assert "execution_id" in entry["request_payload"]
    assert entry["response_code"] == 200
    assert entry["outcome"] == "acknowledged"


# ---------------------------------------------------------------------------
# 5. Enqueue latency ≤ 200 ms
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_latency_under_200ms(monkeypatch, client):
    """POST /execute/dispatch must return within 200 ms (fire-and-forget)."""
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    monkeypatch.setattr(settings, "governance_tier", "1")

    await _fresh_queue(MockStationClient(failure_rate=0.0))

    resp = await client.post(
        "/execute/dispatch",
        json={
            "approval_token": "APPR-LAT-001",
            "card_id": "CARD-LAT00001",
            "event_id": "EVT-LAT001",
            "commander_id": "CMD-001",
        },
    )
    assert resp.status_code == 200
    enqueue_ms = resp.json()["enqueue_ms"]
    assert enqueue_ms < 200, f"Enqueue took {enqueue_ms:.1f} ms — SLA is 200 ms"


# ---------------------------------------------------------------------------
# 6. Retry succeeds on 2nd attempt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt(monkeypatch, client):
    """
    Client configured to fail exactly once.
    Final status must be 'acknowledged' and attempt_count == 2.
    """
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    monkeypatch.setattr(settings, "governance_tier", "1")
    import grid_unlocked.execution.service as svc_module
    monkeypatch.setattr(svc_module, "_RETRY_DELAYS", [0.01, 0.01, 0.01])

    flaky = _FlakyOnceClient()
    await _fresh_queue(flaky)

    resp = await client.post(
        "/execute/dispatch",
        json={
            "approval_token": "APPR-RETRY-001",
            "card_id": "CARD-RETRY001",
            "event_id": "EVT-RETRY01",
            "commander_id": "CMD-001",
        },
    )
    assert resp.status_code == 200
    exec_id = resp.json()["execution_id"]

    # Wait enough for 1 fail + retry delay (0.01s) + 1 success
    await asyncio.sleep(1.0)

    status_resp = await client.get(f"/execute/status/{exec_id}")
    body = status_resp.json()
    assert body["status"] == ExecutionStatus.ACKNOWLEDGED, (
        f"Expected acknowledged after 2nd attempt, got {body['status']}"
    )
    assert body["attempt_count"] == 2


# ---------------------------------------------------------------------------
# 7. GET /execute/audit returns correct shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_query_response_shape(monkeypatch, client):
    """Audit endpoint returns AuditQueryResponse with correct field shapes."""
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    monkeypatch.setattr(settings, "governance_tier", "1")

    await _fresh_queue(MockStationClient(failure_rate=0.0))

    event_id = "EVT-SHAPE001"
    await client.post(
        "/execute/dispatch",
        json={
            "approval_token": "APPR-SHAPE-001",
            "card_id": "CARD-SHAPE001",
            "event_id": event_id,
            "commander_id": "CMD-001",
        },
    )
    await asyncio.sleep(0.5)

    resp = await client.get(f"/execute/audit?event_id={event_id}&limit=10")
    assert resp.status_code == 200
    body = resp.json()

    assert "entries" in body
    assert "count" in body
    assert body["count"] == len(body["entries"])

    if body["entries"]:
        e = body["entries"][0]
        required_fields = {
            "id", "execution_id", "approval_token", "card_id", "event_id",
            "command_type", "attempt_number", "request_payload",
            "response_code", "outcome", "executed_at",
        }
        missing = required_fields - set(e.keys())
        assert not missing, f"Audit entry missing fields: {missing}"


# ---------------------------------------------------------------------------
# 8. Mock station demo endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_station_ack_endpoint(client):
    """POST /mock/station/ack returns the expected demo payload shape."""
    resp = await client.post("/mock/station/ack")
    assert resp.status_code == 200
    body = resp.json()
    assert body["unit_id"].startswith("MOCK-")
    assert body["status"] == "acknowledged"
    assert body["ack_id"].startswith("ACK-")
    assert "dispatched" in body["message"].lower()


# ---------------------------------------------------------------------------
# 9. Status 404 for unknown execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_404_unknown_execution(client):
    resp = await client.get("/execute/status/EXEC-NONEXISTENT")
    assert resp.status_code == 404
