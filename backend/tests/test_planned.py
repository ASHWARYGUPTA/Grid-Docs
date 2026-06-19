import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.main import app
from grid_unlocked.planned.templates import MVP_CAUSES
from grid_unlocked.propagation.subscriber import register_propagation_subscribers

NOW = datetime.now(UTC)
START = (NOW + timedelta(hours=22)).isoformat()
END = (NOW + timedelta(hours=70)).isoformat()

PLANNED_CONSTRUCTION = {
    "id": "FKIDPLAN0001",
    "event_type": "planned",
    "latitude": 12.940,
    "longitude": 77.512,
    "address": "Mysore Road construction zone",
    "event_cause": "construction",
    "requires_road_closure": True,
    "start_datetime": START,
    "end_datetime": END,
    "status": "active",
    "authenticated": "yes",
    "created_date": NOW.isoformat(),
    "corridor": "Mysore Road",
    "priority": "Medium",
}

PLANNED_VIP = {
    **PLANNED_CONSTRUCTION,
    "id": "FKIDPLAN0002",
    "event_cause": "vip_movement",
    "corridor": "Bellary Road 1",
    "address": "VIP movement Bellary Road",
}


@pytest.fixture
async def client():
    register_feature_subscribers()
    register_propagation_subscribers()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_planned_package_construction(client):
    await client.post("/ingest/planned", json=PLANNED_CONSTRUCTION)
    await asyncio.sleep(0.25)

    response = await client.post("/planned/package", json={"event_id": "FKIDPLAN0001"})
    assert response.status_code == 200
    body = response.json()
    assert body["cause"] == "construction"
    assert body["corridor"] == "Mysore Road"
    assert body["staffing_min"] >= 3
    assert body["barricade_count"] >= 6
    assert len(body["checklist"]) >= 3
    assert len(body["analog_events"]) >= 1
    assert len(body["diversion_refs"]) == 3
    assert body["impact_overlay"]["p_closure"] >= 0.36
    assert body["latency_ms"] < 10_000


@pytest.mark.asyncio
async def test_vip_always_stages_barricades(client):
    await client.post("/ingest/planned", json=PLANNED_VIP)
    await asyncio.sleep(0.25)

    response = await client.post("/planned/package", json={"event_id": "FKIDPLAN0002"})
    assert response.status_code == 200
    body = response.json()
    assert body["barricade_staging_required"] is True
    assert body["barricade_count"] >= 12


@pytest.mark.asyncio
async def test_package_cache_skips_regeneration(client):
    await client.post("/ingest/planned", json=PLANNED_CONSTRUCTION)
    await asyncio.sleep(0.25)

    first = await client.post("/planned/package", json={"event_id": "FKIDPLAN0001"})
    second = await client.post("/planned/package", json={"event_id": "FKIDPLAN0001"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert second.json()["latency_ms"] <= first.json()["latency_ms"]


@pytest.mark.asyncio
async def test_all_mvp_templates_exist(client):
    for cause in sorted(MVP_CAUSES):
        response = await client.get(f"/templates/{cause}")
        assert response.status_code == 200
        assert response.json()["cause"] == cause
        assert len(response.json()["checklist"]) >= 3


@pytest.mark.asyncio
async def test_construction_mysore_analogs(client):
    await client.post("/ingest/planned", json=PLANNED_CONSTRUCTION)
    await asyncio.sleep(0.25)
    response = await client.post("/planned/package", json={"event_id": "FKIDPLAN0001"})
    analogs = response.json()["analog_events"]
    assert any(a["cause"] == "construction" for a in analogs)


@pytest.mark.asyncio
async def test_upcoming_timeline(client):
    await client.post("/ingest/planned", json=PLANNED_CONSTRUCTION)
    await asyncio.sleep(0.25)
    response = await client.get("/planned/upcoming?hours=72")
    assert response.status_code == 200
    ids = {p["event_id"] for p in response.json()}
    assert "FKIDPLAN0001" in ids


@pytest.mark.asyncio
async def test_unplanned_event_rejected(client):
    unplanned = {**PLANNED_CONSTRUCTION, "id": "FKIDPLAN0003", "event_type": "unplanned"}
    await client.post("/ingest/astram", json=unplanned)
    response = await client.post("/planned/package", json={"event_id": "FKIDPLAN0003"})
    assert response.status_code == 422
