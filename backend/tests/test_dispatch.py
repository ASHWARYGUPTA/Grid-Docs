"""M07 DispatchOrchestrator tests."""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from grid_unlocked.config import settings
from grid_unlocked.dispatch.greedy import greedy_assign
from grid_unlocked.dispatch.incidents import IncidentContext
from grid_unlocked.dispatch.roster import resolve_units
from grid_unlocked.dispatch.schemas import EquipType, UnitOverride
from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.main import app
from grid_unlocked.propagation.subscriber import register_propagation_subscribers

HEAVY_ORR = {
    "id": "FKIDDISP0001",
    "event_type": "unplanned",
    "latitude": 12.969,
    "longitude": 77.701,
    "address": "ORR East heavy truck",
    "event_cause": "accident",
    "requires_road_closure": True,
    "start_datetime": "2024-03-07T16:00:00+00:00",
    "status": "active",
    "authenticated": "yes",
    "created_date": "2024-03-07T16:05:00+00:00",
    "corridor": "ORR East 1",
    "priority": "High",
    "veh_type": "heavy_vehicle",
    "description": "Heavy truck with steel coils blocking lane",
}

LIGHT_SIDE = {
    "id": "FKIDDISP0002",
    "event_type": "unplanned",
    "latitude": 12.912,
    "longitude": 77.610,
    "address": "Residential side road",
    "event_cause": "vehicle_breakdown",
    "requires_road_closure": False,
    "start_datetime": "2024-03-07T16:10:00+00:00",
    "status": "active",
    "authenticated": "yes",
    "created_date": "2024-03-07T16:12:00+00:00",
    "corridor": "Non-corridor",
    "priority": "Low",
    "veh_type": "two_wheeler",
}


def _incident(
    event_id: str,
    lat: float,
    lon: float,
    rci: float,
    *,
    needs_heavy_tow: bool = False,
    priority: str = "Medium",
    structural: bool = True,
) -> IncidentContext:
    return IncidentContext(
        event_id=event_id,
        latitude=lat,
        longitude=lon,
        corridor="ORR East 1",
        priority=priority,
        rci=rci,
        p_closure=0.5 if rci > 0.5 else 0.2,
        cascade_risk=rci * 0.9,
        centrality=0.6,
        needs_heavy_tow=needs_heavy_tow,
        priority_structural=structural,
        reporting_bias_weight=2.8,
        hour_ist=16,
        simultaneous_events_2km=2,
    )


@pytest.fixture
async def client():
    register_feature_subscribers()
    register_propagation_subscribers()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_dispatch_recommend_heavy_vehicle(client):
    await client.post("/ingest/astram", json=HEAVY_ORR)
    await asyncio.sleep(0.25)

    response = await client.post(
        "/dispatch/recommend",
        json={"event_id": "FKIDDISP0001", "force_greedy": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "GREEDY_FALLBACK"
    assert len(body["assignments"]) >= 1
    primary = next(a for a in body["assignments"] if a["event_id"] == "FKIDDISP0001")
    assert primary["equip_type"] == "heavy_tow"
    assert primary["needs_heavy_tow"] is True
    assert body["latency_ms"] < settings.dispatch_total_deadline_ms
    assert body["recommendation_id"].startswith("DISP-")


@pytest.mark.asyncio
async def test_dispatch_dual_incident_astram_shadow(client):
    await client.post("/ingest/astram", json=HEAVY_ORR)
    await client.post("/ingest/astram", json=LIGHT_SIDE)
    await asyncio.sleep(0.25)

    response = await client.post(
        "/dispatch/recommend",
        json={
            "event_id": "FKIDDISP0001",
            "active_incident_ids": ["FKIDDISP0001", "FKIDDISP0002"],
            "force_greedy": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["assignments"]) == 2
    shadow = {s["event_id"]: s for s in body["astram_shadow"]}
    assert shadow["FKIDDISP0001"]["astram_rank"] <= shadow["FKIDDISP0002"]["astram_rank"]
    assert shadow["FKIDDISP0001"]["grid_rci_rank"] == 1


@pytest.mark.asyncio
async def test_greedy_deterministic_100x():
    units, _ = resolve_units(None)
    incidents = [
        _incident("A", 12.97, 77.70, 0.81, needs_heavy_tow=True, priority="High"),
        _incident("B", 12.91, 77.61, 0.22, priority="Low", structural=False),
    ]
    first = greedy_assign(units, incidents)
    for _ in range(99):
        assert greedy_assign(units, incidents) == first


@pytest.mark.asyncio
async def test_greedy_tie_breaker_station_id():
    units, _ = resolve_units(
        [
            UnitOverride(
                unit_id="PATROL-A",
                station_id="ST-ZZZ",
                equip_type=EquipType.PATROL,
                latitude=12.97,
                longitude=77.60,
            ),
            UnitOverride(
                unit_id="PATROL-B",
                station_id="ST-AAA",
                equip_type=EquipType.PATROL,
                latitude=12.97,
                longitude=77.60,
            ),
        ]
    )
    incidents = [_incident("X", 12.97, 77.60, 0.5)]
    assignments = greedy_assign(units, incidents)
    assert assignments[0].unit_id == "PATROL-B"
    assert assignments[0].station_id == "ST-AAA"


@pytest.mark.asyncio
async def test_dispatch_status_after_recommend(client):
    await client.post("/ingest/astram", json=HEAVY_ORR)
    await asyncio.sleep(0.25)

    rec = await client.post(
        "/dispatch/recommend",
        json={"event_id": "FKIDDISP0001", "force_greedy": True},
    )
    rid = rec.json()["recommendation_id"]

    status = await client.get(f"/dispatch/status/{rid}")
    assert status.status_code == 200
    assert status.json()["complete"] is True
    assert status.json()["source"] == "GREEDY_FALLBACK"


@pytest.mark.asyncio
async def test_dispatch_roster(client):
    response = await client.get("/dispatch/roster")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 10
    assert any(u["equip_type"] == "heavy_tow" for u in body["units"])


@pytest.mark.asyncio
async def test_milp_or_greedy_within_deadline(client):
    await client.post("/ingest/astram", json=HEAVY_ORR)
    await asyncio.sleep(0.25)

    response = await client.post(
        "/dispatch/recommend",
        json={"event_id": "FKIDDISP0001", "tier": "1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] in {"MILP", "GREEDY_FALLBACK"}
    assert body["latency_ms"] <= settings.dispatch_total_deadline_ms + 500
    assert body["milp_attempted"] is True
