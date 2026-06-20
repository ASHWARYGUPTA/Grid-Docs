"""M15 — CommandDashboard WebSocket fanout tests."""

import time

from starlette.testclient import TestClient

from grid_unlocked.config import settings
from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.governance.service import reset_cache_for_tests
from grid_unlocked.hotspots.subscriber import register_hotspot_subscribers
from grid_unlocked.impact.registry import registry
from grid_unlocked.main import app
from grid_unlocked.propagation.subscriber import register_propagation_subscribers

E2E_EVENT = {
    "id": "FKIDDASH001",
    "event_type": "unplanned",
    "latitude": 12.969,
    "longitude": 77.701,
    "event_cause": "accident",
    "requires_road_closure": True,
    "start_datetime": "2024-03-07T12:00:00+00:00",
    "status": "active",
    "authenticated": "yes",
    "created_date": "2024-03-07T12:05:00+00:00",
    "corridor": "ORR East 1",
    "priority": "High",
    "veh_type": "heavy_vehicle",
}


def _setup_client() -> TestClient:
    register_feature_subscribers()
    register_propagation_subscribers()
    register_hotspot_subscribers()
    registry.load()
    return TestClient(app)


def test_websocket_receives_card_delta_after_approve():
    client = _setup_client()
    with client:
        client.post("/ingest/astram", json=E2E_EVENT)
        time.sleep(0.3)
        card = client.get("/recommendations/FKIDDASH001?refresh=true").json()

        with client.websocket_connect("/ws/dashboard") as ws:
            approve = client.post(
                f"/recommendations/{card['card_id']}/approve",
                json={"commander_id": "CMD-001", "override_codes": []},
            )
            assert approve.status_code == 200
            message = ws.receive_json()
            assert message["type"] == "dashboard.delta"
            assert message["scope"] == "card"
            assert message["event_id"] == "FKIDDASH001"
            assert message["payload"]["status"] == "approved"


def test_websocket_receives_hotspot_delta_on_ingest():
    client = _setup_client()
    with client:
        with client.websocket_connect("/ws/dashboard") as ws:
            client.post("/ingest/astram", json={**E2E_EVENT, "id": "FKIDDASH002"})
            message = ws.receive_json()
            assert message["scope"] == "hotspot"
            assert message["event_id"] == "FKIDDASH002"
            assert message["payload"]["h3_res7"]


def test_multiple_connections_all_receive_same_delta():
    client = _setup_client()
    with client:
        with client.websocket_connect("/ws/dashboard") as ws1, client.websocket_connect(
            "/ws/dashboard"
        ) as ws2:
            client.post("/ingest/astram", json={**E2E_EVENT, "id": "FKIDDASH003"})
            m1 = ws1.receive_json()
            m2 = ws2.receive_json()
            assert m1["event_id"] == m2["event_id"] == "FKIDDASH003"


def test_disconnect_reconnect_does_not_crash_server():
    client = _setup_client()
    with client:
        with client.websocket_connect("/ws/dashboard") as ws:
            pass  # closes immediately on exiting the with-block

        # Server should still be healthy and a new connection should work.
        with client.websocket_connect("/ws/dashboard") as ws2:
            client.post("/ingest/astram", json={**E2E_EVENT, "id": "FKIDDASH004"})
            message = ws2.receive_json()
            assert message["event_id"] == "FKIDDASH004"


def test_card_delta_arrives_within_5s_of_ingest():
    """Spec latency contract: dashboard live update <= 5s (ARCHITECTURE.md §11)."""
    client = _setup_client()
    with client:
        with client.websocket_connect("/ws/dashboard") as ws:
            t0 = time.perf_counter()
            client.post("/ingest/astram", json={**E2E_EVENT, "id": "FKIDDASH005"})
            ws.receive_json()  # hotspot delta, fired on ingest
            card = client.get("/recommendations/FKIDDASH005?refresh=true").json()
            client.post(
                f"/recommendations/{card['card_id']}/approve",
                json={"commander_id": "CMD-001", "override_codes": []},
            )
            message = ws.receive_json()  # card delta, fired on approve
            elapsed = time.perf_counter() - t0
            assert message["scope"] == "card"
            assert elapsed < 5.0


def test_websocket_receives_tier_delta_on_override():
    client = _setup_client()
    with client:
        reset_cache_for_tests()
        with client.websocket_connect("/ws/dashboard") as ws:
            resp = client.post(
                "/governance/override-tier",
                json={"tier": "2", "reason": "test drill", "operator_id": "OP-1"},
            )
            assert resp.status_code == 200
            message = ws.receive_json()
            assert message["scope"] == "tier"
            assert message["payload"]["tier"] == "2"
