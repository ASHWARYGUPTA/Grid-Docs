"""PRD / IMPLEMENTATION_MODULES compatibility gates for M08."""

from __future__ import annotations

import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient

from grid_unlocked.config import settings
from grid_unlocked.diversions.atlas import JUNCTION_REGISTRY, get_atlas, list_atlas_junction_ids
from grid_unlocked.diversions.graph import k_shortest_paths
from grid_unlocked.diversions.gridlock import detect_gridlock
from grid_unlocked.features.graph_stub import corridor_to_node_id
from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.hotspots.service import HotspotService
from grid_unlocked.hotspots.subscriber import register_hotspot_subscribers
from grid_unlocked.impact.registry import registry
from grid_unlocked.main import app
from grid_unlocked.propagation.subscriber import register_propagation_subscribers

# PRD M08 testing decisions + interface contracts from IMPLEMENTATION_MODULES § M08
M08_ATLAS_SLA_MS = 80
M08_COMPUTE_SLA_MS = 2000
PRIORITY_CORRIDORS = ("Mysore Road", "ORR East 1", "Bellary Road 1")


@pytest.fixture
async def wired_client():
    register_feature_subscribers()
    register_propagation_subscribers()
    register_hotspot_subscribers()
    registry.load()
    HotspotService.warm()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_req_m08_atlas_all_junctions_return_routes():
    """Atlas coverage: every registered junction returns ≥1 route."""
    for jid in list_atlas_junction_ids():
        entry = get_atlas(jid)
        assert entry is not None
        assert len(entry.routes) >= 1
        for route in entry.routes:
            assert route.junction_id == jid
            assert len(route.path) >= 2
            assert route.eta_delta_min >= 0
            assert route.capacity_class in {"low", "medium", "high"}


@pytest.mark.asyncio
async def test_req_m08_atlas_lookup_under_80ms(wired_client):
    """Latency contract: atlas lookup ≤80 ms P95 (single sample gate)."""
    for jid in ("junction:ORR-Sarjapur", "junction:Mysore-NICE", "junction:Hebbal-flyover"):
        t0 = time.perf_counter()
        resp = await wired_client.get(f"/diversions/atlas/{jid}")
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert resp.status_code == 200
        assert resp.json()["cached"] is True
        assert elapsed_ms < M08_ATLAS_SLA_MS


@pytest.mark.asyncio
async def test_req_m08_compute_under_2s(wired_client):
    """On-demand compute ≤2 s (not on critical path)."""
    t0 = time.perf_counter()
    resp = await wired_client.post(
        "/diversions/compute",
        json={"corridor": "Bellary Road 1", "k": 3},
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert resp.status_code == 200
    assert resp.json()["cached"] is False
    assert elapsed_ms < M08_COMPUTE_SLA_MS


@pytest.mark.asyncio
async def test_req_m08_gridlock_synthetic_loop_flagged(wired_client):
    """Gridlock: synthetic loop route → gridlock_cycle_detected=true."""
    loop_path = [
        "corridor:Old Airport Road",
        "corridor:ORR East 1",
        "corridor:Hosur Road",
        "corridor:ORR East 1",
    ]
    resp = await wired_client.post(
        "/diversions/validate",
        json={"path": loop_path, "closed_node_id": "corridor:ORR East 1"},
    )
    body = resp.json()
    assert body["valid"] is False
    assert body["gridlock_cycle_detected"] is True


@pytest.mark.asyncio
async def test_req_m08_eta_delta_monotonic_in_atlas():
    """ETA delta ranked non-decreasing within single-junction atlas routes."""
    for jid in list_atlas_junction_ids():
        entry = get_atlas(jid)
        if len(entry.routes) < 2:
            continue
        etas = [r.eta_delta_min for r in sorted(entry.routes, key=lambda r: r.rank)]
        assert etas == sorted(etas)


@pytest.mark.asyncio
async def test_req_m08_paths_avoid_closed_corridor():
    """k-shortest paths must not traverse the closed corridor node."""
    closed = corridor_to_node_id("ORR East 1")
    start = corridor_to_node_id("Old Airport Road")
    goal = corridor_to_node_id("Hosur Road")
    for path, _ in k_shortest_paths(start, goal, 3, blocked_nodes={closed}):
        assert closed not in path


@pytest.mark.asyncio
async def test_req_m08_priority_corridors_have_three_refs(wired_client):
    """VIP/construction corridors prioritized — 3 diversion refs each via M06 contract."""
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    for i, corridor in enumerate(PRIORITY_CORRIDORS):
        eid = f"FKIDREQM08{i}"
        planned = {
            "id": eid,
            "event_type": "planned",
            "latitude": 12.94 + i * 0.01,
            "longitude": 77.51 + i * 0.01,
            "event_cause": "construction" if corridor != "Bellary Road 1" else "vip_movement",
            "corridor": corridor,
            "start_datetime": (now + timedelta(hours=24)).isoformat(),
            "end_datetime": (now + timedelta(hours=72)).isoformat(),
            "status": "active",
            "authenticated": "yes",
        }
        await wired_client.post("/ingest/planned", json=planned)
        await asyncio.sleep(0.2)

        pkg = await wired_client.post("/planned/package", json={"event_id": eid})
        assert pkg.status_code == 200
        refs = pkg.json()["diversion_refs"]
        assert len(refs) == settings.diversion_k_default
        junction_ids = {r["junction_id"] for r in refs}
        assert len(junction_ids) >= 2  # distinct junction scenarios
        for ref in refs:
            assert ref["junction_id"] in JUNCTION_REGISTRY


@pytest.mark.asyncio
async def test_req_m08_scenarios_m03_p_closure_wiring(wired_client):
    """M08 scenarios consume M03 p_closure from registry."""
    event = {
        "id": "FKIDREQM08SC",
        "event_type": "unplanned",
        "latitude": 12.969,
        "longitude": 77.701,
        "event_cause": "accident",
        "requires_road_closure": True,
        "start_datetime": "2024-03-07T12:00:00+00:00",  # 17:30 IST peak
        "status": "active",
        "authenticated": "yes",
        "corridor": "ORR East 1",
        "priority": "High",
        "veh_type": "heavy_vehicle",
    }
    await wired_client.post("/ingest/astram", json=event)
    await asyncio.sleep(0.3)

    impact = (await wired_client.post("/impact/score", json={"event_id": "FKIDREQM08SC"})).json()
    scenarios = (await wired_client.get("/diversions/scenarios/FKIDREQM08SC")).json()

    assert scenarios["p_closure"] == impact["p_closure"]
    assert scenarios["corridor"] == "ORR East 1"
    assert len(scenarios["routes"]) == settings.diversion_k_default
    if impact["p_closure"] > settings.closure_alert_threshold and scenarios["is_peak_hour"]:
        assert scenarios["auto_suggest"] is True


@pytest.mark.asyncio
async def test_req_m08_public_interface_contracts(wired_client):
    """All four M08 public endpoints respond per IMPLEMENTATION_MODULES § M08."""
    assert (await wired_client.get("/diversions/atlas/junction:ORR-Sarjapur")).status_code == 200
    assert (
        await wired_client.post("/diversions/compute", json={"corridor": "Mysore Road"})
    ).status_code == 200
    assert (
        await wired_client.post(
            "/diversions/validate",
            json={"path": ["corridor:ORR West 1", "corridor:Mysore Road"]},
        )
    ).status_code == 200
    # scenarios needs event — 404 is valid contract for missing
    assert (await wired_client.get("/diversions/scenarios/NO-SUCH-EVENT")).status_code == 404
