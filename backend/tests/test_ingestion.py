import pytest
from httpx import ASGITransport, AsyncClient

from grid_unlocked.db.session import SessionLocal, init_db
from grid_unlocked.main import app


@pytest.fixture
async def client():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


SAMPLE_ASTRAM = {
    "id": "FKIDTEST0001",
    "event_type": "unplanned",
    "latitude": 13.0400041,
    "longitude": 77.5180991,
    "address": "Tumkur Road, Bengaluru",
    "event_cause": "vehicle_breakdown",
    "requires_road_closure": False,
    "start_datetime": "2024-03-07T17:01:48.111+00:00",
    "status": "active",
    "authenticated": "yes",
    "created_date": "2024-03-07T17:03:51.164032+00:00",
    "corridor": "Tumkur Road",
    "priority": "High",
}


@pytest.mark.asyncio
async def test_ingest_astram_success(client):
    response = await client.post("/ingest/astram", json=SAMPLE_ASTRAM)
    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == "FKIDTEST0001"
    assert body["normalized"] is True
    assert body["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_get_event_after_ingest(client):
    await client.post("/ingest/astram", json=SAMPLE_ASTRAM)
    response = await client.get("/events/FKIDTEST0001")
    assert response.status_code == 200
    event = response.json()
    assert event["event_cause"] == "vehicle_breakdown"
    assert event["corridor"] == "Tumkur Road"
    assert event["source"] == "astram"


@pytest.mark.asyncio
async def test_bbox_rejection(client):
    bad = {**SAMPLE_ASTRAM, "id": "FKIDOUTSIDE", "latitude": 10.0, "longitude": 77.5}
    response = await client.post("/ingest/astram", json=bad)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_test_demo_dropped(client):
    demo = {**SAMPLE_ASTRAM, "id": "FKIDDEMO", "event_cause": "test_demo"}
    response = await client.post("/ingest/astram", json=demo)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_idempotent_upsert(client):
    await client.post("/ingest/astram", json=SAMPLE_ASTRAM)
    updated = {**SAMPLE_ASTRAM, "status": "closed", "closed_datetime": "2024-03-07T19:35:47+00:00"}
    response = await client.post("/ingest/astram", json=updated)
    assert response.status_code == 200
    assert response.json()["status"] == "closed"


@pytest.mark.asyncio
async def test_citizen_unauthenticated(client):
    citizen = {
        **SAMPLE_ASTRAM,
        "id": "CITIZEN001",
        "event_cause": "accident",
    }
    response = await client.post("/ingest/citizen", json=citizen)
    assert response.status_code == 200
    event = await client.get("/events/CITIZEN001")
    assert event.json()["authenticated"] is False
    assert event.json()["source"] == "citizen"


@pytest.mark.asyncio
async def test_health_endpoint(client):
    await client.post("/ingest/astram", json=SAMPLE_ASTRAM)
    response = await client.get("/health/ingest")
    assert response.status_code == 200
    body = response.json()
    assert body["total_events"] >= 1
    assert body["status"] == "healthy"


@pytest.mark.asyncio
async def test_cause_alias_normalization(client):
    payload = {**SAMPLE_ASTRAM, "id": "FKIDFOG", "event_cause": "Fog / Low Visibility"}
    await client.post("/ingest/astram", json=payload)
    event = await client.get("/events/FKIDFOG")
    assert event.json()["event_cause"] == "fog_low_visibility"


@pytest.mark.asyncio
async def test_reporting_lag_computed(client):
    await client.post("/ingest/astram", json={**SAMPLE_ASTRAM, "id": "FKIDLAG"})
    event = await client.get("/events/FKIDLAG")
    lag = event.json()["reporting_lag_minutes"]
    assert lag is not None
    assert 1.0 < lag < 5.0
