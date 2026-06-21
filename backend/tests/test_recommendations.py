"""M09 RecommendationAPI tests."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from grid_unlocked.config import settings
from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.hotspots.subscriber import register_hotspot_subscribers
from grid_unlocked.impact.registry import registry
from grid_unlocked.main import app
from grid_unlocked.propagation.subscriber import register_propagation_subscribers

E2E_EVENT = {
    "id": "FKIDREC0001",
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


@pytest.fixture
async def client():
    register_feature_subscribers()
    register_propagation_subscribers()
    register_hotspot_subscribers()
    registry.load()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_complete_action_card(client):
    await client.post("/ingest/astram", json=E2E_EVENT)
    await asyncio.sleep(0.25)

    resp = await client.get("/recommendations/FKIDREC0001?mode=complete")
    assert resp.status_code == 200
    card = resp.json()
    assert card["card_id"].startswith("CARD-")
    assert card["status"] == "complete"
    assert card["impact"]["rci"] > 0
    assert card["propagation"]["cascade_risk"] > 0
    assert len(card["diversions"]) >= 1
    assert card["dispatch"] is not None
    assert card["dispatch"]["provenance"] in {"MILP", "GREEDY_FALLBACK"}
    assert card["evidence"]["top_features"]
    assert card["governance"]["shadow_mode"] is True
    assert card["latency_ms"] < settings.recommendation_complete_sla_ms + 500


@pytest.mark.asyncio
async def test_skeleton_card_faster_than_complete(client):
    await client.post("/ingest/astram", json={**E2E_EVENT, "id": "FKIDREC0002"})
    await asyncio.sleep(0.25)

    skeleton = await client.get("/recommendations/FKIDREC0002?mode=skeleton&refresh=true")
    assert skeleton.status_code == 200
    body = skeleton.json()
    assert body["status"] == "partial"
    assert body["dispatch_pending"] is True
    assert body["dispatch"] is None
    assert body["skeleton_ms"] < settings.recommendation_skeleton_sla_ms + 800


@pytest.mark.asyncio
async def test_shadow_approve_does_not_enqueue_execution(client):
    await client.post("/ingest/astram", json={**E2E_EVENT, "id": "FKIDREC0003"})
    await asyncio.sleep(0.25)

    card = (await client.get("/recommendations/FKIDREC0003?refresh=true")).json()
    approve = await client.post(
        f"/recommendations/{card['card_id']}/approve",
        json={"commander_id": "CMD-001", "override_codes": []},
    )
    assert approve.status_code == 200
    result = approve.json()
    assert result["shadow_mode"] is True
    assert result["execution_enqueued"] is False
    assert "shadow" in result["message"].lower()


@pytest.mark.asyncio
async def test_reject_captures_reason_code(client):
    await client.post("/ingest/astram", json={**E2E_EVENT, "id": "FKIDREC0004"})
    await asyncio.sleep(0.25)

    card = (await client.get("/recommendations/FKIDREC0004?refresh=true")).json()
    reject = await client.post(
        f"/recommendations/{card['card_id']}/reject",
        json={
            "commander_id": "CMD-002",
            "reason_code": "MODEL_DISAGREE",
            "notes": "RCI seems high for this corridor",
        },
    )
    assert reject.status_code == 200
    assert reject.json()["action"] == "reject"
    assert "MODEL_DISAGREE" in reject.json()["message"]


@pytest.mark.asyncio
async def test_queue_ordered_by_rci(client):
    for i, eid in enumerate(["FKIDRECQ01", "FKIDRECQ02"]):
        await client.post(
            "/ingest/astram",
            json={
                **E2E_EVENT,
                "id": eid,
                "latitude": 12.969 + i * 0.02,
                "veh_type": "heavy_vehicle" if i == 0 else "two_wheeler",
                "corridor": "ORR East 1" if i == 0 else "Non-corridor",
            },
        )
    await asyncio.sleep(0.35)

    queue = await client.get("/recommendations/queue")
    assert queue.status_code == 200
    items = queue.json()["items"]
    assert len(items) >= 2
    rcis = [i["rci"] for i in items]
    assert rcis == sorted(rcis, reverse=True)
    for item in items:
        assert 0.0 <= item["p_closure"] <= 1.0


@pytest.mark.asyncio
async def test_refresh_recomputes_card(client):
    await client.post("/ingest/astram", json={**E2E_EVENT, "id": "FKIDREC0005"})
    await asyncio.sleep(0.25)

    first = (await client.get("/recommendations/FKIDREC0005")).json()
    second = (await client.post("/recommendations/FKIDREC0005/refresh")).json()
    assert first["card_id"] != second["card_id"]
    assert second["impact"]["event_id"] == "FKIDREC0005"


@pytest.mark.asyncio
async def test_unknown_event_404(client):
    resp = await client.get("/recommendations/NO-SUCH-EVENT")
    assert resp.status_code == 404
