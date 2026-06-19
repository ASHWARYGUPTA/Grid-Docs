"""Cross-module integration tests — M01 through M09 end-to-end wiring."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from grid_unlocked.config import settings
from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.hotspots.service import HotspotService
from grid_unlocked.hotspots.subscriber import register_hotspot_subscribers
from grid_unlocked.impact.registry import registry
from grid_unlocked.main import app
from grid_unlocked.planned.templates import MVP_CAUSES
from grid_unlocked.propagation.subscriber import register_propagation_subscribers

NOW = datetime.now(UTC)
PLANNED_START = (NOW + timedelta(hours=22)).isoformat()
PLANNED_END = (NOW + timedelta(hours=70)).isoformat()

E2E_EVENT = {
    "id": "FKIDE2E0001",
    "event_type": "unplanned",
    "latitude": 12.969,
    "longitude": 77.701,
    "address": "Bellandur Flyover, Bengaluru",
    "event_cause": "accident",
    "requires_road_closure": True,
    "start_datetime": "2024-03-07T12:00:00+00:00",
    "status": "active",
    "authenticated": "yes",
    "created_date": "2024-03-07T12:05:00+00:00",
    "corridor": "ORR East 1",
    "priority": "High",
    "veh_type": "heavy_vehicle",
    "description": "Heavy truck blocking lane",
}

PLANNED_CONSTRUCTION = {
    "id": "FKIDE2EPLAN1",
    "event_type": "planned",
    "latitude": 12.940,
    "longitude": 77.512,
    "address": "Mysore Road construction zone",
    "event_cause": "construction",
    "requires_road_closure": True,
    "start_datetime": PLANNED_START,
    "end_datetime": PLANNED_END,
    "status": "active",
    "authenticated": "yes",
    "created_date": NOW.isoformat(),
    "corridor": "Mysore Road",
    "priority": "Medium",
}


@pytest.fixture
async def wired_client():
    """Client with production-equivalent subscriber + warm-cache wiring."""
    register_feature_subscribers()
    register_propagation_subscribers()
    register_hotspot_subscribers()
    registry.load()
    HotspotService.warm()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _wait_features(client: AsyncClient, event_id: str, retries: int = 5) -> dict:
    """Poll M02 until feature materialization completes (async subscriber race)."""
    for _ in range(retries):
        resp = await client.get(f"/features/{event_id}")
        if resp.status_code == 200:
            return resp.json()
        await asyncio.sleep(0.15)
    pytest.fail(f"M02 features not materialized for {event_id}")


@pytest.mark.asyncio
async def test_full_pipeline_m01_through_m08(wired_client):
    """M01→M02→M03→M04→M05→M07→M08→M09 on a single unplanned heavy-vehicle incident."""
    ingest = await wired_client.post("/ingest/astram", json=E2E_EVENT)
    assert ingest.status_code == 200
    assert ingest.json()["normalized"] is True

    event = await wired_client.get("/events/FKIDE2E0001")
    assert event.status_code == 200
    assert event.json()["corridor"] == "ORR East 1"

    fv = await _wait_features(wired_client, "FKIDE2E0001")
    assert fv["graph_node_id"] == "corridor:ORR East 1"
    assert fv["duration_prior_h"] > 0

    centrality = await wired_client.get("/graph/centrality/corridor:ORR East 1")
    assert centrality.status_code == 200
    assert centrality.json()["betweenness_norm"] > 0

    impact = await wired_client.post("/impact/score", json={"event_id": "FKIDE2E0001"})
    assert impact.status_code == 200
    score = impact.json()
    assert score["rci"] > 0
    assert score["severity_band"] in {"Green", "Yellow", "Orange", "Red"}

    explain = await wired_client.get("/impact/explain/FKIDE2E0001")
    assert explain.status_code == 200
    assert len(explain.json()["top_features"]) >= 1

    models = await wired_client.get("/models/versions")
    assert models.status_code == 200
    assert models.json()["closure"]

    ripple = await wired_client.post("/propagation/ripple", json={"event_id": "FKIDE2E0001"})
    assert ripple.status_code == 200
    prop = ripple.json()
    assert prop["seed_rci"] == score["rci"]
    assert prop["cascade_risk"] >= prop["seed_rci"]
    assert len(prop["nodes"]) >= 1

    active = await wired_client.get("/propagation/active")
    assert any(m["event_id"] == "FKIDE2E0001" for m in active.json())

    config = await wired_client.get("/propagation/config")
    assert config.json()["max_hops"] == settings.gcdh_max_hops

    observed = await wired_client.get("/hotspots/observed")
    assert len(observed.json()["clusters"]) >= 1

    predicted = await wired_client.get("/hotspots/predicted?horizon_hours=4")
    assert len(predicted.json()["forecasts"]) >= 1

    anomalies = await wired_client.get("/hotspots/anomalies?window_hours=24")
    assert anomalies.status_code == 200

    h3_cell = fv["h3_res7"]
    cell = await wired_client.get(f"/hotspots/cell/{h3_cell}")
    assert cell.status_code == 200

    dispatch = await wired_client.post(
        "/dispatch/recommend",
        json={"event_id": "FKIDE2E0001", "force_greedy": True},
    )
    assert dispatch.status_code == 200
    disp = dispatch.json()
    assert disp["source"] == "GREEDY_FALLBACK"
    assignment = next(a for a in disp["assignments"] if a["event_id"] == "FKIDE2E0001")
    assert assignment["equip_type"] == "heavy_tow"
    assert assignment["rci"] == score["rci"]
    assert disp["latency_ms"] < settings.dispatch_total_deadline_ms

    status = await wired_client.get(f"/dispatch/status/{disp['recommendation_id']}")
    assert status.json()["complete"] is True

    atlas = await wired_client.get("/diversions/atlas/junction:ORR-Sarjapur")
    assert atlas.status_code == 200
    atlas_body = atlas.json()
    assert atlas_body["latency_ms"] < 80
    assert len(atlas_body["routes"]) >= 1
    closed = atlas_body["closed_node_id"]
    for route in atlas_body["routes"]:
        assert closed not in route["path"]

    scenarios = await wired_client.get("/diversions/scenarios/FKIDE2E0001")
    assert scenarios.status_code == 200
    scen = scenarios.json()
    assert scen["corridor"] == "ORR East 1"
    assert scen["p_closure"] == score["p_closure"]
    assert len(scen["routes"]) == 3
    assert scen["junction_id"] == "junction:ORR-Sarjapur"

    validate = await wired_client.post(
        "/diversions/validate",
        json={"path": scen["routes"][0]["path"], "closed_node_id": closed},
    )
    assert validate.status_code == 200
    assert validate.json()["valid"] is True

    card = await wired_client.get("/recommendations/FKIDE2E0001?mode=complete&refresh=true")
    assert card.status_code == 200
    action = card.json()
    assert action["card_id"].startswith("CARD-")
    assert action["status"] == "complete"
    assert action["impact"]["rci"] == score["rci"]
    assert action["propagation"]["cascade_risk"] == prop["cascade_risk"]
    assert len(action["diversions"]) == 3
    assert action["dispatch"]["provenance"] in {"MILP", "GREEDY_FALLBACK"}
    assert action["evidence"]["top_features"]
    assert action["governance"]["shadow_mode"] is True
    assert action["latency_ms"] < settings.recommendation_complete_sla_ms + 500

    queue = await wired_client.get("/recommendations/queue")
    assert any(i["event_id"] == "FKIDE2E0001" for i in queue.json()["items"])


@pytest.mark.asyncio
async def test_m08_m06_planned_package_diversion_wiring(wired_client):
    """M06 planned package diversion_refs sourced from M08 atlas (not static stub)."""
    ingest = await wired_client.post("/ingest/planned", json=PLANNED_CONSTRUCTION)
    assert ingest.status_code == 200
    await _wait_features(wired_client, "FKIDE2EPLAN1")

    atlas = (await wired_client.get("/diversions/atlas/junction:Mysore-NICE")).json()
    package = (
        await wired_client.post("/planned/package", json={"event_id": "FKIDE2EPLAN1"})
    ).json()

    assert len(package["diversion_refs"]) == 3
    atlas_junctions = {r["junction_id"] for r in atlas["routes"]}
    package_junctions = {r["junction_id"] for r in package["diversion_refs"]}
    assert package_junctions.issubset(set(atlas_junctions) | {"junction:Mysore-Vijayanagar", "junction:Mysore-Gnanabharathi"})
    for ref in package["diversion_refs"]:
        assert ref["description"]
        assert ref["route_summary"]
        assert 1 <= ref["rank"] <= 3


@pytest.mark.asyncio
async def test_m08_compute_fills_cache_miss(wired_client):
    """POST /diversions/compute returns uncached on-demand routes."""
    resp = await wired_client.post(
        "/diversions/compute",
        json={"junction_id": "junction:Hebbal-flyover", "k": 3},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cached"] is False
    assert body["source_corridor"] == "Bellary Road 1"
    assert len(body["routes"]) >= 1
    ranks = [r["rank"] for r in body["routes"]]
    assert ranks == sorted(ranks)


@pytest.mark.asyncio
async def test_m08_scenarios_auto_suggest_peak_vs_off_peak(wired_client):
    """Activation policy: auto_suggest requires p_closure > threshold AND peak hour."""
    peak_event = {
        **E2E_EVENT,
        "id": "FKIDE2EPEAK1",
        "start_datetime": "2024-03-07T12:00:00+00:00",  # 17:30 IST — peak
    }
    offpeak_event = {
        **E2E_EVENT,
        "id": "FKIDE2EOFF1",
        "start_datetime": "2024-03-07T06:30:00+00:00",  # 12:00 IST — off peak
    }
    await wired_client.post("/ingest/astram", json=peak_event)
    await wired_client.post("/ingest/astram", json=offpeak_event)
    await asyncio.sleep(0.35)

    peak_scen = (await wired_client.get("/diversions/scenarios/FKIDE2EPEAK1")).json()
    off_scen = (await wired_client.get("/diversions/scenarios/FKIDE2EOFF1")).json()

    assert peak_scen["is_peak_hour"] is True
    if peak_scen["p_closure"] > settings.closure_alert_threshold:
        assert peak_scen["auto_suggest"] is True
    # off-peak must not auto-suggest regardless of closure probability
    assert off_scen["auto_suggest"] is False


@pytest.mark.asyncio
async def test_planned_pipeline_m01_m06(wired_client):
    """M01 planned ingest → M06 package → templates → upcoming timeline."""
    ingest = await wired_client.post("/ingest/planned", json=PLANNED_CONSTRUCTION)
    assert ingest.status_code == 200

    await _wait_features(wired_client, "FKIDE2EPLAN1")

    package = await wired_client.post(
        "/planned/package",
        json={"event_id": "FKIDE2EPLAN1"},
    )
    assert package.status_code == 200
    pkg = package.json()
    assert pkg["cause"] == "construction"
    assert pkg["impact_overlay"]["p_closure"] >= 0.36
    assert len(pkg["analog_events"]) >= 1
    assert len(pkg["diversion_refs"]) == 3

    cached = await wired_client.post(
        "/planned/package",
        json={"event_id": "FKIDE2EPLAN1", "force_refresh": False},
    )
    assert cached.json()["cached"] is True

    template = await wired_client.get("/templates/construction")
    assert template.status_code == 200
    assert template.json()["cause"] == "construction"

    for cause in MVP_CAUSES:
        resp = await wired_client.get(f"/templates/{cause}")
        assert resp.status_code == 200

    upcoming = await wired_client.get("/planned/upcoming?hours=72")
    assert upcoming.status_code == 200
    assert any(p["event_id"] == "FKIDE2EPLAN1" for p in upcoming.json())


@pytest.mark.asyncio
async def test_m03_m04_m07_rci_signal_chain(wired_client):
    """RCI from M03 propagates to M04 cascade_risk and M07 assignment card."""
    event = {**E2E_EVENT, "id": "FKIDE2E0004"}
    await wired_client.post("/ingest/astram", json=event)
    await _wait_features(wired_client, "FKIDE2E0004")

    score = (await wired_client.post("/impact/score", json={"event_id": "FKIDE2E0004"})).json()
    prop = (
        await wired_client.post("/propagation/ripple", json={"event_id": "FKIDE2E0004"})
    ).json()
    disp = (
        await wired_client.post(
            "/dispatch/recommend",
            json={"event_id": "FKIDE2E0004", "force_greedy": True},
        )
    ).json()

    assert prop["seed_rci"] == score["rci"]
    assert prop["cascade_risk"] >= score["rci"]
    assignment = next(a for a in disp["assignments"] if a["event_id"] == "FKIDE2E0004")
    assert assignment["rci"] == score["rci"]
    assert assignment["cascade_risk"] == prop["cascade_risk"]


@pytest.mark.asyncio
async def test_m02_batch_and_m03_batch(wired_client):
    """Batch feature + impact scoring across multiple ingested events."""
    ids = ["FKIDE2EB01", "FKIDE2EB02"]
    for i, eid in enumerate(ids):
        payload = {**E2E_EVENT, "id": eid, "latitude": 12.969 + i * 0.01}
        await wired_client.post("/ingest/astram", json=payload)

    await asyncio.sleep(0.3)

    features = await wired_client.post("/features/batch", json={"event_ids": ids})
    assert features.status_code == 200
    assert len(features.json()) == 2

    scores = await wired_client.post("/impact/score/batch", json={"event_ids": ids})
    assert scores.status_code == 200
    assert len(scores.json()) == 2


@pytest.mark.asyncio
async def test_event_closed_clears_m04_propagation_cache(wired_client):
    """M01 EventClosed → M04 propagation cache cleanup."""
    event = {**E2E_EVENT, "id": "FKIDE2E0002"}
    await wired_client.post("/ingest/astram", json=event)
    await _wait_features(wired_client, "FKIDE2E0002")

    await wired_client.post("/propagation/ripple", json={"event_id": "FKIDE2E0002"})
    assert any(
        m["event_id"] == "FKIDE2E0002"
        for m in (await wired_client.get("/propagation/active")).json()
    )

    closed = {
        **event,
        "status": "closed",
        "closed_datetime": "2024-03-07T14:00:00+00:00",
    }
    await wired_client.post("/ingest/astram", json=closed)
    await asyncio.sleep(0.1)

    active = (await wired_client.get("/propagation/active")).json()
    assert not any(m["event_id"] == "FKIDE2E0002" for m in active)


@pytest.mark.asyncio
async def test_m04_auto_scores_rci_via_m03_registry(wired_client):
    """M04 seeds RCI from M03 registry when seed_rci omitted."""
    event = {**E2E_EVENT, "id": "FKIDE2E0003"}
    await wired_client.post("/ingest/astram", json=event)
    await _wait_features(wired_client, "FKIDE2E0003")

    ripple = await wired_client.post(
        "/propagation/ripple",
        json={"event_id": "FKIDE2E0003"},
    )
    assert ripple.status_code == 200
    assert ripple.json()["seed_rci"] > 0


@pytest.mark.asyncio
async def test_m07_milp_or_greedy_with_astram_shadow(wired_client):
    """M07 Tier-1 MILP attempt with ASTraM vs RCI shadow comparison."""
    heavy = {**E2E_EVENT, "id": "FKIDE2E0005", "priority": "High"}
    light = {
        **E2E_EVENT,
        "id": "FKIDE2E0006",
        "latitude": 12.912,
        "longitude": 77.610,
        "corridor": "Non-corridor",
        "priority": "Low",
        "veh_type": "two_wheeler",
        "event_cause": "vehicle_breakdown",
        "description": "Scooter breakdown",
    }
    await wired_client.post("/ingest/astram", json=heavy)
    await wired_client.post("/ingest/astram", json=light)
    await asyncio.sleep(0.3)

    resp = await wired_client.post(
        "/dispatch/recommend",
        json={
            "event_id": "FKIDE2E0005",
            "active_incident_ids": ["FKIDE2E0005", "FKIDE2E0006"],
            "tier": "1",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] in {"MILP", "GREEDY_FALLBACK"}
    assert body["milp_attempted"] is True
    assert len(body["assignments"]) == 2
    shadow = {s["event_id"]: s for s in body["astram_shadow"]}
    assert shadow["FKIDE2E0005"]["grid_rci_rank"] == 1

    roster = await wired_client.get("/dispatch/roster")
    assert roster.json()["count"] >= 10


@pytest.mark.asyncio
async def test_m09_planned_event_includes_package_section(wired_client):
    """M09 complete card for planned events includes M06 package summary."""
    await wired_client.post("/ingest/planned", json=PLANNED_CONSTRUCTION)
    await _wait_features(wired_client, "FKIDE2EPLAN1")

    card = (
        await wired_client.get(
            "/recommendations/FKIDE2EPLAN1?mode=complete&refresh=true",
        )
    ).json()
    assert card["status"] == "complete"
    assert card["planned"] is not None
    assert card["planned"]["barricade_count"] >= 1
    assert card["planned"]["template_id"]


@pytest.mark.asyncio
async def test_m09_approve_reject_lifecycle(wired_client):
    """M09 approval workflow persists status and respects shadow mode."""
    event = {**E2E_EVENT, "id": "FKIDE2E0009"}
    await wired_client.post("/ingest/astram", json=event)
    await _wait_features(wired_client, "FKIDE2E0009")

    card = (await wired_client.get("/recommendations/FKIDE2E0009?refresh=true")).json()
    approve = await wired_client.post(
        f"/recommendations/{card['card_id']}/approve",
        json={"commander_id": "CMD-E2E", "override_codes": []},
    )
    assert approve.status_code == 200
    assert approve.json()["execution_enqueued"] is False

    event2 = {**E2E_EVENT, "id": "FKIDE2E0010"}
    await wired_client.post("/ingest/astram", json=event2)
    await _wait_features(wired_client, "FKIDE2E0010")
    card2 = (await wired_client.get("/recommendations/FKIDE2E0010?refresh=true")).json()
    reject = await wired_client.post(
        f"/recommendations/{card2['card_id']}/reject",
        json={"commander_id": "CMD-E2E", "reason_code": "INSUFFICIENT_EVIDENCE", "notes": "test"},
    )
    assert reject.status_code == 200
    assert reject.json()["action"] == "reject"


@pytest.mark.asyncio
async def test_health_endpoints(wired_client):
    """System and M01 ingest health surfaces respond."""
    system = await wired_client.get("/health")
    assert system.status_code == 200
    assert system.json()["database_ok"] is True

    ingest_health = await wired_client.get("/health/ingest")
    assert ingest_health.status_code == 200
    assert ingest_health.json()["total_events"] >= 0
