import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.main import app
from grid_unlocked.propagation.gcdh import run_gcdh
from grid_unlocked.propagation.schemas import GcdhParams
from grid_unlocked.propagation.subscriber import register_propagation_subscribers

ORR_SAMPLE = {
    "id": "FKIDPROP0001",
    "event_type": "unplanned",
    "latitude": 12.9352,
    "longitude": 77.6784,
    "address": "ORR Bellandur, Bengaluru",
    "event_cause": "accident",
    "requires_road_closure": True,
    "start_datetime": "2024-03-07T12:15:00+00:00",
    "status": "active",
    "authenticated": "yes",
    "created_date": "2024-03-07T12:20:00+00:00",
    "corridor": "ORR East 1",
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


@pytest.mark.asyncio
async def test_propagation_ripple_after_ingest(client):
    await client.post("/ingest/astram", json=ORR_SAMPLE)
    await asyncio.sleep(0.2)
    response = await client.post(
        "/propagation/ripple",
        json={"event_id": "FKIDPROP0001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == "FKIDPROP0001"
    assert body["seed_node_id"] == "corridor:ORR East 1"
    assert body["cascade_risk"] >= body["seed_rci"]
    assert len(body["nodes"]) >= 2
    assert body["latency_ms"] < 150
    assert body["gcdh_params"]["lambda"] == 0.35


@pytest.mark.asyncio
async def test_propagation_active_list(client):
    await client.post("/ingest/astram", json=ORR_SAMPLE)
    await asyncio.sleep(0.2)
    await client.post("/propagation/ripple", json={"event_id": "FKIDPROP0001"})
    active = await client.get("/propagation/active")
    assert active.status_code == 200
    ids = {m["event_id"] for m in active.json()}
    assert "FKIDPROP0001" in ids


@pytest.mark.asyncio
async def test_propagation_config(client):
    response = await client.get("/propagation/config")
    assert response.status_code == 200
    body = response.json()
    assert body["lambda"] == 0.35
    assert body["k"] == 0.15
    assert body["epsilon"] == 0.02
    assert body["max_hops"] == 5


def test_gcdh_decay_along_single_path():
    """Risk at hop 2 along one path is lower than the hop-1 parent on that path."""
    params = GcdhParams(**{"lambda": 0.35, "k": 0.15, "epsilon": 0.001, "max_hops": 2})
    pmap = run_gcdh("test", "corridor:ORR East 1", 0.9, params)
    hop1_east2 = next(n for n in pmap.nodes if n.corridor == "ORR East 2" and n.hop == 1)
    hop2_madras = next(
        (n for n in pmap.nodes if n.corridor == "Old Madras Road" and n.hop == 2),
        None,
    )
    assert hop2_madras is not None
    assert hop2_madras.risk < hop1_east2.risk


def test_gcdh_centrality_amplification():
    params = GcdhParams(**{"lambda": 0.35, "k": 0.15, "epsilon": 0.001, "max_hops": 1})
    pmap = run_gcdh("test", "corridor:ORR East 1", 0.9, params)
    hop1 = {n.corridor: n.risk for n in pmap.nodes if n.hop == 1}
    assert hop1["ORR East 2"] > hop1["Hosur Road"]


def test_gcdh_epsilon_stops_expansion():
    params = GcdhParams(**{"lambda": 0.35, "k": 0.15, "epsilon": 0.5, "max_hops": 5})
    pmap = run_gcdh("test", "corridor:ORR East 1", 0.3, params)
    assert len(pmap.nodes) == 1


def test_gcdh_explainability_parent_edges():
    params = GcdhParams(**{"lambda": 0.35, "k": 0.15, "epsilon": 0.001, "max_hops": 2})
    pmap = run_gcdh("test", "corridor:Mysore Road", 0.8, params)
    for node in pmap.nodes:
        if node.hop > 0:
            assert node.parent_edge is not None
            assert "->" in node.parent_edge
