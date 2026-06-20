"""M11 — VMSRouter tests.

Covers every testing decision from the spec:
  1. Shadow mode blocks VMS push
  2. Idempotent double-push → same delivery set, no duplicate fanout
  3. Mock board 503 → DLQ after retries
  4. Delivery list completeness on happy path (one row per corridor board)
  5. Fanout latency ≤ 500 ms (enqueue, not wait for board ACK)
  6. Retry succeeds on 2nd attempt
  7. Manual retry after DLQ succeeds
  8. Board text template constraints (≤120 chars, ≤3 lines, includes alt route)
  9. Mock /mock/vms/receive demo endpoint
  10. 404 for unknown delivery
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from grid_unlocked.config import settings
from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.hotspots.subscriber import register_hotspot_subscribers
from grid_unlocked.impact.registry import registry
from grid_unlocked.main import app
from grid_unlocked.propagation.subscriber import register_propagation_subscribers
from grid_unlocked.vms.mock_webhook import MockWebhookClient, WebhookResponse
from grid_unlocked.vms.schemas import VmsDeliveryStatus
from grid_unlocked.vms import service as vms_service_module

SAMPLE_ROUTE = {
    "rank": 1,
    "junction_id": "JN-001",
    "description": "Use Bannerghata Road via Sony World Junction",
    "route_summary": "Hosur Road to Bannerghata Road",
    "path": ["Hosur Road", "Sony World Jn", "Bannerghata Road"],
    "eta_delta_min": 6.0,
    "capacity_class": "medium",
    "gridlock_cycle_detected": False,
    "edge_disjoint": True,
}


class _FlakyOnceClient(MockWebhookClient):
    """Fails exactly once per board, succeeds on all subsequent calls."""

    def __init__(self) -> None:
        super().__init__(failure_rate=0.0)
        self._failed_once: set[str] = set()

    async def post_to_board(self, board_id, board_name, endpoint, board_text, push_id, event_id):
        if board_id not in self._failed_once:
            self._failed_once.add(board_id)
            return WebhookResponse(status_code=503, body={"error": "transient"}, latency_ms=5)
        return await super().post_to_board(board_id, board_name, endpoint, board_text, push_id, event_id)


def _set_client(client: MockWebhookClient | None = None) -> None:
    vms_service_module.set_webhook_client(client or MockWebhookClient(failure_rate=0.0))


@pytest.fixture
async def client():
    """HTTP test client with all subscribers and registry loaded."""
    register_feature_subscribers()
    register_propagation_subscribers()
    register_hotspot_subscribers()
    registry.load()
    _set_client(MockWebhookClient(failure_rate=0.0))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# 1. Shadow mode blocks VMS push
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shadow_mode_blocks_vms_push(client):
    assert settings.governance_shadow_mode is True

    resp = await client.post(
        "/vms/push",
        json={
            "push_id": "PUSH-SHADOW-001",
            "event_id": "EVT-SHADOW",
            "card_id": "CARD-SHADOW001",
            "corridor": "Koramangala",
            "routes": [SAMPLE_ROUTE],
            "commander_id": "CMD-001",
        },
    )
    assert resp.status_code == 403
    assert "shadow_mode" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 2. Idempotent double-push → same delivery set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotent_double_push(monkeypatch, client):
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    _set_client(MockWebhookClient(failure_rate=0.0))

    payload = {
        "push_id": "PUSH-IDEM-001",
        "event_id": "EVT-IDEM001",
        "card_id": "CARD-IDEM0001",
        "corridor": "Koramangala",
        "routes": [SAMPLE_ROUTE],
        "commander_id": "CMD-001",
    }

    r1 = await client.post("/vms/push", json=payload)
    r2 = await client.post("/vms/push", json=payload)

    assert r1.status_code == 200
    assert r2.status_code == 200
    ids1 = {d["delivery_id"] for d in r1.json()["deliveries"]}
    ids2 = {d["delivery_id"] for d in r2.json()["deliveries"]}
    assert ids1 == ids2, "Second push must not create new delivery rows (idempotency)"
    assert "idempotent" in r2.json()["message"].lower()


# ---------------------------------------------------------------------------
# 3. Mock board 503 → DLQ after retries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_board_failure_leads_to_dlq(monkeypatch, client):
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    monkeypatch.setattr(vms_service_module, "_RETRY_DELAYS", [0.01, 0.01, 0.01])
    _set_client(MockWebhookClient(failure_rate=1.0))

    resp = await client.post(
        "/vms/push",
        json={
            "push_id": "PUSH-FAIL-001",
            "event_id": "EVT-FAIL001",
            "card_id": "CARD-FAIL0001",
            "corridor": "Koramangala",
            "routes": [SAMPLE_ROUTE],
            "commander_id": "CMD-001",
        },
    )
    assert resp.status_code == 200
    delivery_id = resp.json()["deliveries"][0]["delivery_id"]

    await asyncio.sleep(1.0)

    status_resp = await client.get(f"/vms/status/{delivery_id}")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["status"] == VmsDeliveryStatus.DEAD_LETTER
    assert body["retry_count"] == 3


# ---------------------------------------------------------------------------
# 4. Delivery list completeness — one row per corridor board
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_push_targets_all_corridor_boards(monkeypatch, client):
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    _set_client(MockWebhookClient(failure_rate=0.0))

    resp = await client.post(
        "/vms/push",
        json={
            "push_id": "PUSH-MULTI-001",
            "event_id": "EVT-MULTI001",
            "card_id": "CARD-MULTI001",
            "corridor": "Koramangala",
            "routes": [SAMPLE_ROUTE],
            "commander_id": "CMD-001",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["board_count"] == 3, "Koramangala maps to VMS-KOR-1, VMS-KOR-2, VMS-HSR-1"
    assert len(body["deliveries"]) == 3
    board_ids = {d["board_id"] for d in body["deliveries"]}
    assert board_ids == {"VMS-KOR-1", "VMS-KOR-2", "VMS-HSR-1"}

    await asyncio.sleep(0.5)
    for d in body["deliveries"]:
        status_resp = await client.get(f"/vms/status/{d['delivery_id']}")
        assert status_resp.json()["status"] == VmsDeliveryStatus.DELIVERED


# ---------------------------------------------------------------------------
# 5. Fanout latency ≤ 500 ms
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fanout_latency_under_500ms(monkeypatch, client):
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    _set_client(MockWebhookClient(failure_rate=0.0))

    resp = await client.post(
        "/vms/push",
        json={
            "push_id": "PUSH-LAT-001",
            "event_id": "EVT-LAT001",
            "card_id": "CARD-LAT00001",
            "corridor": "Whitefield",
            "routes": [SAMPLE_ROUTE],
            "commander_id": "CMD-001",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["fanout_ms"] < 500, "Fanout enqueue must be fire-and-forget, not wait for board ACK"


# ---------------------------------------------------------------------------
# 6. Retry succeeds on 2nd attempt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt(monkeypatch, client):
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    monkeypatch.setattr(vms_service_module, "_RETRY_DELAYS", [0.01, 0.01, 0.01])
    _set_client(_FlakyOnceClient())

    resp = await client.post(
        "/vms/push",
        json={
            "push_id": "PUSH-RETRY-001",
            "event_id": "EVT-RETRY01",
            "card_id": "CARD-RETRY001",
            "corridor": "Sarjapur",
            "routes": [SAMPLE_ROUTE],
            "commander_id": "CMD-001",
        },
    )
    assert resp.status_code == 200
    deliveries = resp.json()["deliveries"]

    await asyncio.sleep(1.0)

    for d in deliveries:
        status_resp = await client.get(f"/vms/status/{d['delivery_id']}")
        body = status_resp.json()
        assert body["status"] == VmsDeliveryStatus.DELIVERED
        assert body["retry_count"] == 2


# ---------------------------------------------------------------------------
# 7. Manual retry after DLQ succeeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manual_retry_after_dead_letter_succeeds(monkeypatch, client):
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    monkeypatch.setattr(vms_service_module, "_RETRY_DELAYS", [0.01, 0.01, 0.01])
    _set_client(MockWebhookClient(failure_rate=1.0))

    resp = await client.post(
        "/vms/push",
        json={
            "push_id": "PUSH-DLQR-001",
            "event_id": "EVT-DLQR001",
            "card_id": "CARD-DLQR0001",
            "corridor": "HSR",
            "routes": [SAMPLE_ROUTE],
            "commander_id": "CMD-001",
        },
    )
    delivery_id = resp.json()["deliveries"][0]["delivery_id"]
    await asyncio.sleep(1.0)

    dlq_status = (await client.get(f"/vms/status/{delivery_id}")).json()
    assert dlq_status["status"] == VmsDeliveryStatus.DEAD_LETTER

    _set_client(MockWebhookClient(failure_rate=0.0))
    retry_resp = await client.post(f"/vms/retry/{delivery_id}")
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == VmsDeliveryStatus.PENDING

    await asyncio.sleep(0.5)
    final_status = (await client.get(f"/vms/status/{delivery_id}")).json()
    assert final_status["status"] == VmsDeliveryStatus.DELIVERED


@pytest.mark.asyncio
async def test_manual_retry_rejects_non_dlq_delivery(monkeypatch, client):
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    _set_client(MockWebhookClient(failure_rate=0.0))

    resp = await client.post(
        "/vms/push",
        json={
            "push_id": "PUSH-409-001",
            "event_id": "EVT-409001",
            "card_id": "CARD-4090001",
            "corridor": "Banashankari",
            "routes": [SAMPLE_ROUTE],
            "commander_id": "CMD-001",
        },
    )
    delivery_id = resp.json()["deliveries"][0]["delivery_id"]
    await asyncio.sleep(0.3)

    retry_resp = await client.post(f"/vms/retry/{delivery_id}")
    assert retry_resp.status_code == 409


# ---------------------------------------------------------------------------
# 8. Board text template constraints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_board_text_template_constraints(monkeypatch, client):
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    _set_client(MockWebhookClient(failure_rate=0.0))

    resp = await client.post(
        "/vms/push",
        json={
            "push_id": "PUSH-TEXT-001",
            "event_id": "EVT-TEXT001",
            "card_id": "CARD-TEXT0001",
            "corridor": "Whitefield",
            "routes": [SAMPLE_ROUTE],
            "commander_id": "CMD-001",
        },
    )
    assert resp.status_code == 200
    for d in resp.json()["deliveries"]:
        text = d["board_text"]
        lines = text.split("\n")
        assert len(lines) <= 3, f"Board text must be ≤3 lines, got {len(lines)}"
        inline = " | ".join(lines)
        assert len(inline) <= 120, f"Board text must be ≤120 chars, got {len(inline)}"
        assert "DIVERSION" in text.upper()


@pytest.mark.asyncio
async def test_no_routes_falls_back_to_generic_alert(monkeypatch, client):
    """When routes=[] (e.g. M08 found no scenarios), push must still succeed
    with a generic board message instead of erroring."""
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    _set_client(MockWebhookClient(failure_rate=0.0))

    resp = await client.post(
        "/vms/push",
        json={
            "push_id": "PUSH-NOROUTE-001",
            "event_id": "EVT-NOROUTE001",
            "card_id": "CARD-NOROUTE01",
            "corridor": "BTM",
            "routes": [],
            "commander_id": "CMD-001",
        },
    )
    assert resp.status_code == 200
    for d in resp.json()["deliveries"]:
        assert "DIVERSION ALERT" in d["board_text"]


# ---------------------------------------------------------------------------
# 9. Mock demo endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_vms_receive_endpoint(client):
    resp = await client.post(
        "/mock/vms/receive",
        json={"board_id": "VMS-KOR-1", "board_text": "DIVERSION ALERT"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["board_id"] == "VMS-KOR-1"
    assert body["ack_id"].startswith("VMSACK-")
    assert body["status"] == "displayed"


# ---------------------------------------------------------------------------
# 10. Status 404 for unknown delivery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_404_unknown_delivery(client):
    resp = await client.get("/vms/status/VDEL-NONEXISTENT")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unmapped_corridor_falls_back_to_default_boards(monkeypatch, client):
    """Unknown corridor must use the default board fallback, not 422."""
    monkeypatch.setattr(settings, "governance_shadow_mode", False)
    _set_client(MockWebhookClient(failure_rate=0.0))

    resp = await client.post(
        "/vms/push",
        json={
            "push_id": "PUSH-UNMAPPED-001",
            "event_id": "EVT-UNMAPPED001",
            "card_id": "CARD-UNMAPPED1",
            "corridor": "Some Unknown Corridor",
            "routes": [SAMPLE_ROUTE],
            "commander_id": "CMD-001",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["board_count"] >= 1
