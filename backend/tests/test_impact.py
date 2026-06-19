import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.impact.rci import compute_rci, severity_band_from_rci
from grid_unlocked.impact.schemas import SeverityBand
from grid_unlocked.main import app

SAMPLE_ASTRAM = {
    "id": "FKIDIMP0001",
    "event_type": "unplanned",
    "latitude": 13.0400041,
    "longitude": 77.5180991,
    "address": "Tumkur Road, Bengaluru",
    "event_cause": "vehicle_breakdown",
    "requires_road_closure": False,
    "start_datetime": "2024-03-07T11:00:00+00:00",
    "status": "active",
    "authenticated": "yes",
    "created_date": "2024-03-07T17:03:51+00:00",
    "corridor": "Mysore Road",
    "priority": "High",
    "veh_type": "lcv",
}

PLANNED_SAMPLE = {
    **SAMPLE_ASTRAM,
    "id": "FKIDIMP0002",
    "event_type": "planned",
    "event_cause": "vip_movement",
    "requires_road_closure": True,
}


@pytest.fixture
async def client():
    register_feature_subscribers()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_impact_score_after_ingest(client):
    await client.post("/ingest/astram", json=SAMPLE_ASTRAM)
    await asyncio.sleep(0.2)
    response = await client.post("/impact/score", json={"event_id": "FKIDIMP0001"})
    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == "FKIDIMP0001"
    assert 0 <= body["p_closure"] <= 1
    assert body["ict_p20_h"] <= body["ict_p50_h"] <= body["ict_p80_h"]
    assert body["severity_band"] in {b.value for b in SeverityBand}
    assert body["model_versions"]["source"] in {"ml", "rule_fallback"}


@pytest.mark.asyncio
async def test_vip_movement_elevates_closure(client):
    await client.post("/ingest/planned", json=PLANNED_SAMPLE)
    await asyncio.sleep(0.2)
    response = await client.post("/impact/score", json={"event_id": "FKIDIMP0002"})
    assert response.status_code == 200
    assert response.json()["p_closure"] >= 0.80
    assert response.json()["staging_recommended"] is True


@pytest.mark.asyncio
async def test_impact_explain(client):
    await client.post("/ingest/astram", json=SAMPLE_ASTRAM)
    await asyncio.sleep(0.2)
    await client.post("/impact/score", json={"event_id": "FKIDIMP0001"})
    response = await client.get("/impact/explain/FKIDIMP0001")
    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == "FKIDIMP0001"
    assert len(body["top_features"]) >= 1


@pytest.mark.asyncio
async def test_model_versions_endpoint(client):
    response = await client.get("/models/versions")
    assert response.status_code == 200
    body = response.json()
    assert body["closure"] in {"rule-v1", "lgbm-v1"}
    assert body["source"] in {"rule_fallback", "ml"}


@pytest.mark.asyncio
async def test_impact_batch(client):
    await client.post("/ingest/astram", json=SAMPLE_ASTRAM)
    await asyncio.sleep(0.2)
    response = await client.post(
        "/impact/score/batch",
        json={"event_ids": ["FKIDIMP0001", "missing-id"]},
    )
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_rci_severity_bands():
    from datetime import UTC, datetime

    from grid_unlocked.features.schemas import FeatureVector

    fv = FeatureVector(
        event_id="x",
        graph_node_id="corridor:Mysore Road",
        hour_ist=16,
        dow=3,
        hour_sin=0.0,
        hour_cos=1.0,
        dow_sin=0.0,
        dow_cos=1.0,
        is_peak_hour=True,
        is_weekend=False,
        reporting_bias_weight=1.0,
        betweenness_norm=0.5,
        degree_norm=0.3,
        h3_res7="872830828ffffff",
        h3_res9="892830828bfffff",
        is_named_corridor=True,
        corridor_cause_closure_rate=0.1,
        corridor_cause_median_ict_h=1.0,
        duration_prior_h=1.0,
        cause_median_resolution_global_h=1.0,
        veh_complexity_score=0.2,
        simultaneous_events_2km=0,
        materialized_at=datetime.now(UTC),
    )
    low_rci = compute_rci(fv, p_closure=0.05)
    assert severity_band_from_rci(low_rci) == SeverityBand.GREEN

    high_rci = compute_rci(fv, p_closure=0.95)
    assert severity_band_from_rci(high_rci) in {SeverityBand.ORANGE, SeverityBand.RED}
