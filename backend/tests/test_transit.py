"""M12 — TransitImpactService tests.

Covers every testing decision from the spec:
  1. Mock demo returns a consistent canned index, latency well under 50ms
  2. Spatial join: a mapped corridor returns known BMTC routes
  3. /transit/impact/{event_id} 404 on unknown event
  4. Impact computation uses M03 ict_p50_h as the delay multiplier
  5. Tier 3 -> static advisory, no per-route breakdown
  6. Cache hit within TTL skips recomputation
  7. Unmapped corridor falls back to default routes (non-error)
  8. /transit/routes/affected with no corridor -> default list, not 422
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from grid_unlocked.config import settings
from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.impact.schemas import ImpactScore, ModelVersions, SeverityBand
from grid_unlocked.impact.service import ImpactService
from grid_unlocked.main import app
from grid_unlocked.propagation.subscriber import register_propagation_subscribers

HOSUR_EVENT = {
    "id": "TRANSIT0001",
    "event_type": "unplanned",
    "latitude": 12.9,
    "longitude": 77.64,
    "event_cause": "accident",
    "requires_road_closure": True,
    "start_datetime": "2024-03-07T16:00:00+00:00",
    "status": "active",
    "authenticated": "yes",
    "created_date": "2024-03-07T16:05:00+00:00",
    "corridor": "Hosur Road",
    "priority": "High",
    "veh_type": "heavy_vehicle",
}


@pytest.fixture
async def client():
    register_feature_subscribers()
    register_propagation_subscribers()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _ingest(client, event: dict) -> None:
    resp = await client.post("/ingest/astram", json=event)
    assert resp.status_code in (200, 201), resp.text
    await asyncio.sleep(0.25)


@pytest.mark.asyncio
async def test_mock_demo_returns_consistent_index(client):
    r1 = await client.get("/mock/transit/demo")
    r2 = await client.get("/mock/transit/demo")
    assert r1.status_code == 200
    assert r1.json() == r2.json()
    assert r1.json()["passenger_delay_index"] > 0
    assert "passengers delayed" in r1.json()["message"]


@pytest.mark.asyncio
async def test_mock_demo_latency_under_50ms(client):
    import time

    t0 = time.perf_counter()
    resp = await client.get("/mock/transit/demo")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert resp.status_code == 200
    assert elapsed_ms < 50


@pytest.mark.asyncio
async def test_affected_routes_for_mapped_corridor(client):
    resp = await client.get("/transit/routes/affected", params={"corridor": "Hosur Road"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["corridor"] == "Hosur Road"
    route_ids = {r["route_id"] for r in body["routes"]}
    assert "BMTC-G4" in route_ids


@pytest.mark.asyncio
async def test_affected_routes_unmapped_corridor_falls_back(client):
    resp = await client.get("/transit/routes/affected", params={"corridor": "Nonexistent Road XYZ"})
    assert resp.status_code == 200
    assert len(resp.json()["routes"]) > 0


@pytest.mark.asyncio
async def test_affected_routes_no_corridor_param_returns_default(client):
    resp = await client.get("/transit/routes/affected")
    assert resp.status_code == 200
    assert resp.json()["corridor"] is None
    assert len(resp.json()["routes"]) > 0


@pytest.mark.asyncio
async def test_impact_404_on_unknown_event(client):
    resp = await client.get("/transit/impact/UNKNOWN-EVT")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_impact_uses_ict_p50_as_delay_multiplier(monkeypatch, client):
    await _ingest(client, HOSUR_EVENT)

    fixed_score = ImpactScore(
        event_id=HOSUR_EVENT["id"],
        p_closure=0.5,
        ict_p20_h=0.5,
        ict_p50_h=1.0,
        ict_p80_h=2.0,
        rci=0.5,
        severity_band=SeverityBand.YELLOW,
        priority_structural=True,
        staging_recommended=False,
        model_versions=ModelVersions(closure="test", ict="test", source="test"),
        latency_ms=1.0,
        scored_at=datetime.now(UTC),
    )

    async def _fake_score(self, event_id):
        return fixed_score

    monkeypatch.setattr(ImpactService, "score", _fake_score)

    resp = await client.get(f"/transit/impact/{HOSUR_EVENT['id']}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["degraded"] is False

    predicted_delay_min = 1.0 * 60
    expected_index = sum(
        r["occupancy"] * predicted_delay_min * r["overlap_fraction"] for r in body["affected_routes"]
    )
    assert body["passenger_delay_index"] == pytest.approx(round(expected_index, 1))
    for route in body["affected_routes"]:
        assert route["predicted_delay_min"] == pytest.approx(predicted_delay_min, abs=0.1)


@pytest.mark.asyncio
async def test_tier3_returns_static_advisory(monkeypatch, client):
    await _ingest(client, HOSUR_EVENT)
    monkeypatch.setattr(settings, "governance_tier", "3")

    resp = await client.get(f"/transit/impact/{HOSUR_EVENT['id']}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["degraded"] is True
    assert body["affected_routes"] == []
    assert body["passenger_delay_index"] == 0.0
    assert body["advisory_message"] is not None
    assert "BMTC" in body["advisory_message"]


@pytest.mark.asyncio
async def test_cache_hit_skips_recomputation(monkeypatch, client):
    await _ingest(client, HOSUR_EVENT)

    call_count = {"n": 0}
    original_score = ImpactService.score

    async def _counting_score(self, event_id):
        call_count["n"] += 1
        return await original_score(self, event_id)

    monkeypatch.setattr(ImpactService, "score", _counting_score)

    r1 = await client.get(f"/transit/impact/{HOSUR_EVENT['id']}")
    r2 = await client.get(f"/transit/impact/{HOSUR_EVENT['id']}")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert call_count["n"] == 1, "second call within TTL must hit the cache"
    assert r1.json()["cached"] is False
    assert r2.json()["cached"] is True
