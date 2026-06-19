import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.main import app

SAMPLE_ASTRAM = {
    "id": "FKIDFEAT0001",
    "event_type": "unplanned",
    "latitude": 13.0400041,
    "longitude": 77.5180991,
    "address": "Tumkur Road, Bengaluru",
    "event_cause": "vehicle_breakdown",
    "requires_road_closure": False,
    "start_datetime": "2024-03-07T11:00:00+00:00",  # 16:30 IST
    "status": "active",
    "authenticated": "yes",
    "created_date": "2024-03-07T17:03:51+00:00",
    "corridor": "Mysore Road",
    "priority": "High",
    "veh_type": "lcv",
}

MORNING_SAMPLE = {
    **SAMPLE_ASTRAM,
    "id": "FKIDFEAT0002",
    "start_datetime": "2024-03-07T03:00:00+00:00",  # 08:30 IST
}


@pytest.fixture
async def client():
    register_feature_subscribers()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_features_materialized_after_ingest(client):
    await client.post("/ingest/astram", json=SAMPLE_ASTRAM)
    await asyncio.sleep(0.2)
    response = await client.get("/features/FKIDFEAT0001")
    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == "FKIDFEAT0001"
    assert body["h3_res7"]
    assert body["duration_prior_h"] > 0
    assert body["is_named_corridor"] is True


@pytest.mark.asyncio
async def test_evening_bias_weight_higher_than_morning(client):
    await client.post("/ingest/astram", json=SAMPLE_ASTRAM)
    await client.post("/ingest/astram", json=MORNING_SAMPLE)
    await asyncio.sleep(0.2)
    evening = (await client.get("/features/FKIDFEAT0001")).json()
    morning = (await client.get("/features/FKIDFEAT0002")).json()
    assert evening["reporting_bias_weight"] > morning["reporting_bias_weight"]


@pytest.mark.asyncio
async def test_corridor_cause_prior_endpoint(client):
    response = await client.get("/priors/corridor-cause/Mysore%20Road/vehicle_breakdown")
    assert response.status_code == 200
    body = response.json()
    assert body["corridor"] == "Mysore Road"
    assert body["cause"] == "vehicle_breakdown"
    assert body["sample_count"] > 0


@pytest.mark.asyncio
async def test_graph_centrality_orr_high(client):
    response = await client.get("/graph/centrality/corridor:ORR%20East%201")
    assert response.status_code == 200
    orr = response.json()["betweenness_norm"]
    response2 = await client.get("/graph/centrality/corridor:Non-corridor")
    non = response2.json()["betweenness_norm"]
    assert orr > non


@pytest.mark.asyncio
async def test_feature_cache_hit(client):
    await client.post("/ingest/astram", json=SAMPLE_ASTRAM)
    await asyncio.sleep(0.2)
    first = await client.get("/features/FKIDFEAT0001")
    second = await client.get("/features/FKIDFEAT0001")
    assert first.status_code == 200
    assert second.json()["cache_hit"] is True


@pytest.mark.asyncio
async def test_features_batch(client):
    await client.post("/ingest/astram", json=SAMPLE_ASTRAM)
    await client.post("/ingest/astram", json=MORNING_SAMPLE)
    await asyncio.sleep(0.2)
    response = await client.post(
        "/features/batch",
        json={"event_ids": ["FKIDFEAT0001", "FKIDFEAT0002"]},
    )
    assert response.status_code == 200
    assert len(response.json()) == 2
