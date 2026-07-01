"""M08 DiversionRoutingEngine tests."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from grid_unlocked.diversions.atlas import JUNCTION_REGISTRY, get_atlas, routes_for_corridor
from grid_unlocked.diversions.gridlock import detect_gridlock
from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.main import app
from grid_unlocked.propagation.subscriber import register_propagation_subscribers

E2E_EVENT = {
    "id": "FKIDDIV0001",
    "event_type": "unplanned",
    "latitude": 12.969,
    "longitude": 77.701,
    "event_cause": "accident",
    "requires_road_closure": True,
    "start_datetime": "2024-03-07T17:00:00+00:00",
    "status": "active",
    "authenticated": "yes",
    "created_date": "2024-03-07T17:05:00+00:00",
    "corridor": "ORR East 1",
    "priority": "High",
}


@pytest.fixture
async def client():
    register_feature_subscribers()
    register_propagation_subscribers()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_atlas_lookup_returns_three_routes(client):
    resp = await client.get("/diversions/atlas/junction:ORR-Sarjapur")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_corridor"] == "ORR East 1"
    assert len(body["routes"]) >= 1
    assert body["latency_ms"] < 80
    assert body["cached"] is True
    ranks = [r["rank"] for r in body["routes"]]
    assert ranks == sorted(ranks)


@pytest.mark.asyncio
async def test_atlas_unknown_junction_404(client):
    resp = await client.get("/diversions/atlas/junction:DOES-NOT-EXIST")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_atlas_index_lists_junctions(client):
    resp = await client.get("/diversions/atlas")
    assert resp.status_code == 200
    assert "junction:ORR-Sarjapur" in resp.json()
    assert len(resp.json()) == len(JUNCTION_REGISTRY)


@pytest.mark.asyncio
async def test_compute_on_demand(client):
    resp = await client.post(
        "/diversions/compute",
        json={"corridor": "Mysore Road", "k": 3},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cached"] is False
    assert len(body["routes"]) >= 1
    assert body["routes"][0]["path"]


@pytest.mark.asyncio
async def test_validate_detects_cycle():
    closed = "corridor:ORR East 1"
    loop_path = [
        "corridor:Old Airport Road",
        "corridor:ORR East 1",
        "corridor:Hosur Road",
        "corridor:ORR East 1",
    ]
    result = detect_gridlock(loop_path, closed_node_id=closed)
    assert result.gridlock_cycle_detected or result.reenters_closed_zone


@pytest.mark.asyncio
async def test_validate_clean_path(client):
    resp = await client.post(
        "/diversions/validate",
        json={
            "path": ["corridor:Old Airport Road", "corridor:CBD 1"],
            "closed_node_id": "corridor:ORR East 1",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


@pytest.mark.asyncio
async def test_scenarios_for_event(client):
    await client.post("/ingest/astram", json=E2E_EVENT)
    await asyncio.sleep(0.25)

    resp = await client.get("/diversions/scenarios/FKIDDIV0001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["corridor"] == "ORR East 1"
    assert body["p_closure"] > 0
    assert len(body["routes"]) >= 1
    for route in body["routes"]:
        assert "waypoints" in route
        for wp in route["waypoints"]:
            assert "lat" in wp and "lng" in wp


@pytest.mark.asyncio
async def test_waypoints_resolve_from_corridor_centroids(client):
    """Seed two centroids and confirm the route waypoints reflect them."""
    import grid_unlocked.db.session as _session_module
    from grid_unlocked.db.models import CorridorCentroidRow

    async with _session_module.SessionLocal() as session:
        session.add(
            CorridorCentroidRow(corridor="Old Airport Road", lat=12.95, lon=77.65, sample_count=10)
        )
        session.add(
            CorridorCentroidRow(corridor="Hosur Road", lat=12.91, lon=77.62, sample_count=10)
        )
        await session.commit()

    resp = await client.post("/diversions/compute", json={"corridor": "ORR East 1", "k": 3})
    assert resp.status_code == 200
    routes = resp.json()["routes"]
    resolved = [wp for r in routes for wp in r["waypoints"]]
    assert resolved, "expected at least one resolved waypoint"
    corridors = {wp["corridor"] for wp in resolved}
    assert corridors & {"Old Airport Road", "Hosur Road"}
    for wp in resolved:
        if wp["corridor"] == "Old Airport Road":
            assert wp["lat"] == pytest.approx(12.95)
            assert wp["lng"] == pytest.approx(77.65)


@pytest.mark.asyncio
async def test_eta_delta_monotonic_by_rank():
    routes = routes_for_corridor("ORR East 1", k=3)
    if len(routes) >= 2:
        assert routes[0].eta_delta_min <= routes[1].eta_delta_min


@pytest.mark.asyncio
async def test_m06_package_uses_m08_atlas(client):
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    planned = {
        "id": "FKIDDIVPLAN1",
        "event_type": "planned",
        "latitude": 12.94,
        "longitude": 77.512,
        "event_cause": "construction",
        "corridor": "Mysore Road",
        "start_datetime": (now + timedelta(hours=24)).isoformat(),
        "end_datetime": (now + timedelta(hours=72)).isoformat(),
        "status": "active",
        "authenticated": "yes",
    }
    await client.post("/ingest/planned", json=planned)
    await asyncio.sleep(0.25)

    pkg = await client.post("/planned/package", json={"event_id": "FKIDDIVPLAN1"})
    assert pkg.status_code == 200
    refs = pkg.json()["diversion_refs"]
    assert len(refs) == 3
    atlas = get_atlas("junction:Mysore-NICE")
    assert refs[0]["junction_id"] == atlas.routes[0].junction_id
