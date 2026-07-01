"""Robustness and degradation tests — M01 through M09 cross-module resilience."""

from __future__ import annotations

import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient

from grid_unlocked.config import settings
from grid_unlocked.dispatch.greedy import greedy_assign
from grid_unlocked.dispatch.incidents import IncidentContext
from grid_unlocked.dispatch.roster import resolve_units
from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.hotspots.service import HotspotService
from grid_unlocked.hotspots.subscriber import register_hotspot_subscribers
from grid_unlocked.impact.registry import registry
from grid_unlocked.main import app
from grid_unlocked.propagation.subscriber import register_propagation_subscribers

BASE_EVENT = {
    "event_type": "unplanned",
    "latitude": 12.969,
    "longitude": 77.701,
    "address": "Bellandur Flyover",
    "event_cause": "accident",
    "requires_road_closure": True,
    "start_datetime": "2024-03-07T16:00:00+00:00",
    "status": "active",
    "authenticated": "yes",
    "created_date": "2024-03-07T16:05:00+00:00",
    "corridor": "ORR East 1",
    "priority": "High",
    "veh_type": "heavy_vehicle",
    "description": "Heavy truck blocking lane",
}


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


async def _ingest_and_wait(client: AsyncClient, event_id: str, **overrides) -> None:
    payload = {**BASE_EVENT, "id": event_id, **overrides}
    resp = await client.post("/ingest/astram", json=payload)
    assert resp.status_code == 200
    for _ in range(6):
        if (await client.get(f"/features/{event_id}")).status_code == 200:
            return
        await asyncio.sleep(0.15)
    pytest.fail(f"features not ready for {event_id}")


# --- M01 rejection & idempotency ---


@pytest.mark.asyncio
async def test_m01_bbox_and_invalid_cause_rejected(wired_client):
    outside = {**BASE_EVENT, "id": "FKIDROB001", "latitude": 10.0}
    assert (await wired_client.post("/ingest/astram", json=outside)).status_code == 422

    demo = {**BASE_EVENT, "id": "FKIDROB002", "event_cause": "test_demo"}
    assert (await wired_client.post("/ingest/astram", json=demo)).status_code == 422


@pytest.mark.asyncio
async def test_m01_upsert_does_not_break_downstream(wired_client):
    eid = "FKIDROB003"
    await _ingest_and_wait(wired_client, eid)

    await wired_client.post("/impact/score", json={"event_id": eid})

    updated = {
        **BASE_EVENT,
        "id": eid,
        "description": "Updated description after upsert",
    }
    await wired_client.post("/ingest/astram", json=updated)
    await asyncio.sleep(0.2)

    score2_resp = await wired_client.post("/impact/score", json={"event_id": eid})
    assert score2_resp.status_code == 200
    assert score2_resp.json()["rci"] > 0
    # RCI may shift slightly after re-materialization; must remain valid
    assert 0 <= score2_resp.json()["rci"] <= 1.0


# --- M02/M03/M04 graceful failures ---


@pytest.mark.asyncio
async def test_downstream_404_for_unknown_event(wired_client):
    ghost = "FKIDGHOST9999"
    assert (await wired_client.get(f"/events/{ghost}")).status_code == 404
    assert (await wired_client.get(f"/features/{ghost}")).status_code == 404
    assert (
        await wired_client.post("/impact/score", json={"event_id": ghost})
    ).status_code == 404
    assert (
        await wired_client.post("/propagation/ripple", json={"event_id": ghost})
    ).status_code == 404
    assert (
        await wired_client.post("/planned/package", json={"event_id": ghost})
    ).status_code in {404, 422}
    assert (
        await wired_client.post("/dispatch/recommend", json={"event_id": ghost})
    ).status_code in {404, 422}
    assert (await wired_client.get(f"/diversions/scenarios/{ghost}")).status_code == 404
    assert (await wired_client.get("/diversions/atlas/junction:GHOST-JUNCTION")).status_code == 404


@pytest.mark.asyncio
async def test_m03_score_before_features_materialized(wired_client):
    """Score immediately after ingest may 422 if M02 subscriber hasn't finished."""
    eid = "FKIDROB004"
    await wired_client.post("/ingest/astram", json={**BASE_EVENT, "id": eid})
    immediate = await wired_client.post("/impact/score", json={"event_id": eid})
    # Either fast materialization (200) or honest 422 — never 500
    assert immediate.status_code in {200, 422}
    if immediate.status_code == 422:
        await asyncio.sleep(0.35)
        retry = await wired_client.post("/impact/score", json={"event_id": eid})
        assert retry.status_code == 200


@pytest.mark.asyncio
async def test_m04_accepts_explicit_seed_rci(wired_client):
    eid = "FKIDROB005"
    await _ingest_and_wait(wired_client, eid)
    custom_rci = 0.77
    ripple = await wired_client.post(
        "/propagation/ripple",
        json={"event_id": eid, "seed_rci": custom_rci},
    )
    assert ripple.status_code == 200
    body = ripple.json()
    assert body["seed_rci"] == custom_rci
    assert body["cascade_risk"] >= custom_rci


# --- M05 empty-state resilience ---


@pytest.mark.asyncio
async def test_m05_endpoints_never_500(wired_client):
    for path in (
        "/hotspots/observed",
        "/hotspots/predicted?horizon_hours=4",
        "/hotspots/anomalies?window_hours=24",
    ):
        resp = await wired_client.get(path)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)
        assert len(body) >= 1


# --- M06 cache & template robustness ---


@pytest.mark.asyncio
async def test_m06_package_idempotent_and_template_unknown(wired_client):
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    eid = "FKIDROBPLAN1"
    planned = {
        "id": eid,
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
    await wired_client.post("/ingest/planned", json=planned)
    await asyncio.sleep(0.35)

    pkg1 = await wired_client.post("/planned/package", json={"event_id": eid})
    pkg2 = await wired_client.post(
        "/planned/package", json={"event_id": eid, "force_refresh": False}
    )
    assert pkg1.status_code == 200
    assert pkg2.status_code == 200
    assert pkg2.json()["cached"] is True
    assert pkg1.json()["template_id"] == pkg2.json()["template_id"]

    bad_template = await wired_client.get("/templates/not_a_real_cause")
    assert bad_template.status_code in {404, 422}


# --- M07 degradation tiers & non-starvation ---


@pytest.mark.asyncio
async def test_m07_tier2_greedy_only(wired_client):
    eid = "FKIDROB006"
    await _ingest_and_wait(wired_client, eid)
    resp = await wired_client.post(
        "/dispatch/recommend",
        json={"event_id": eid, "tier": "2"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["milp_attempted"] is False
    assert body["source"] == "GREEDY_FALLBACK"
    assert len(body["assignments"]) >= 1


@pytest.mark.asyncio
async def test_m07_tier3_nearest_unit(wired_client):
    eid = "FKIDROB007"
    await _ingest_and_wait(wired_client, eid)
    resp = await wired_client.post(
        "/dispatch/recommend",
        json={"event_id": eid, "tier": "3"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["assignments"]) >= 1
    assert resp.json()["tier_at_decision"] == "3"


@pytest.mark.asyncio
async def test_m07_five_incident_cascade_non_starvation(wired_client):
    """PRD cascade drill: 5 concurrent high-RCI incidents all receive assignments."""
    ids = [f"FKIDROBC{i:02d}" for i in range(5)]
    for i, eid in enumerate(ids):
        await _ingest_and_wait(
            wired_client,
            eid,
            latitude=12.96 + i * 0.008,
            longitude=77.68 + i * 0.004,
        )

    t0 = time.perf_counter()
    resp = await wired_client.post(
        "/dispatch/recommend",
        json={
            "event_id": ids[0],
            "active_incident_ids": ids,
            "force_greedy": True,
        },
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert resp.status_code == 200
    body = resp.json()
    assigned_events = {a["event_id"] for a in body["assignments"]}
    assert assigned_events == set(ids)
    assert body["latency_ms"] < settings.dispatch_total_deadline_ms + 500
    assert elapsed_ms < settings.dispatch_total_deadline_ms + 1000


@pytest.mark.asyncio
async def test_m07_concurrent_recommend_requests(wired_client):
    """Parallel dispatch calls must not 500 and return distinct recommendation IDs."""
    ids = ["FKIDROBP01", "FKIDROBP02", "FKIDROBP03"]
    for eid in ids:
        await _ingest_and_wait(wired_client, eid, latitude=12.95, longitude=77.65)

    async def _recommend(eid: str):
        return await wired_client.post(
            "/dispatch/recommend",
            json={"event_id": eid, "force_greedy": True},
        )

    results = await asyncio.gather(*[_recommend(eid) for eid in ids])
    rec_ids = []
    for resp in results:
        assert resp.status_code == 200
        assert len(resp.json()["assignments"]) >= 1
        rec_ids.append(resp.json()["recommendation_id"])
    assert len(set(rec_ids)) == 3


@pytest.mark.asyncio
async def test_m07_dispatch_status_unknown_404(wired_client):
    resp = await wired_client.get("/dispatch/status/DISP-DOESNOTEXIST")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_m07_greedy_deterministic_across_replays():
    """100× identical greedy input → identical output (PRD determinism gate)."""
    units, _ = resolve_units(None)
    incidents = [
        IncidentContext(
            event_id="A",
            latitude=12.97,
            longitude=77.70,
            corridor="ORR East 1",
            priority="High",
            rci=0.81,
            p_closure=0.6,
            cascade_risk=0.79,
            centrality=0.7,
            needs_heavy_tow=True,
            priority_structural=True,
            reporting_bias_weight=2.5,
            hour_ist=16,
            simultaneous_events_2km=3,
        ),
        IncidentContext(
            event_id="B",
            latitude=12.91,
            longitude=77.61,
            corridor="Non-corridor",
            priority="Low",
            rci=0.22,
            p_closure=0.1,
            cascade_risk=0.18,
            centrality=0.2,
            needs_heavy_tow=False,
            priority_structural=False,
            reporting_bias_weight=1.0,
            hour_ist=10,
            simultaneous_events_2km=0,
        ),
    ]
    baseline = greedy_assign(units, incidents)
    for _ in range(99):
        assert greedy_assign(units, incidents) == baseline


@pytest.mark.asyncio
async def test_m07_heavy_incident_never_assigned_patrol_only(wired_client):
    """Equipment gate: heavy vehicle must not get patrol-only when tow available."""
    eid = "FKIDROB008"
    await _ingest_and_wait(
        wired_client,
        eid,
        veh_type="heavy_vehicle",
        description="Container truck cargo spill",
    )
    resp = await wired_client.post(
        "/dispatch/recommend",
        json={"event_id": eid, "force_greedy": True},
    )
    assignment = next(a for a in resp.json()["assignments"] if a["event_id"] == eid)
    assert assignment["equip_type"] == "heavy_tow"


# --- Full-stack stress: ingest burst then dispatch ---


@pytest.mark.asyncio
async def test_burst_ingest_then_full_stack(wired_client):
    """Rapid sequential ingests followed by M03/M04/M07 must remain stable."""
    burst_ids = [f"FKIDBURST{i:02d}" for i in range(8)]
    for i, eid in enumerate(burst_ids):
        await wired_client.post(
            "/ingest/astram",
            json={
                **BASE_EVENT,
                "id": eid,
                "latitude": 12.92 + i * 0.005,
                "longitude": 77.60 + i * 0.005,
                "veh_type": "lcv" if i % 2 else "heavy_vehicle",
            },
        )
    await asyncio.sleep(0.5)

    scored = 0
    for eid in burst_ids:
        resp = await wired_client.post("/impact/score", json={"event_id": eid})
        if resp.status_code == 200:
            scored += 1
            ripple = await wired_client.post("/propagation/ripple", json={"event_id": eid})
            assert ripple.status_code == 200

    assert scored >= 6  # allow 2 race misses from async M02

    dispatch = await wired_client.post(
        "/dispatch/recommend",
        json={"event_id": burst_ids[0], "active_incident_ids": burst_ids, "force_greedy": True},
    )
    assert dispatch.status_code == 200
    assert len(dispatch.json()["assignments"]) >= len(burst_ids) - 2


# --- M08 atlas resilience & gridlock ---


@pytest.mark.asyncio
async def test_m08_atlas_never_500(wired_client):
    """All atlas junction lookups must return 200 or 404 — never 500."""
    index = (await wired_client.get("/diversions/atlas")).json()
    for jid in index:
        resp = await wired_client.get(f"/diversions/atlas/{jid}")
        assert resp.status_code == 200
        assert len(resp.json()["routes"]) >= 1


@pytest.mark.asyncio
async def test_m08_compute_missing_params_422(wired_client):
    resp = await wired_client.post("/diversions/compute", json={"k": 3})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_m08_validate_reentry_into_closed_zone(wired_client):
    """Route that re-enters closed zone after exit must be invalid."""
    resp = await wired_client.post(
        "/diversions/validate",
        json={
            "path": [
                "corridor:Old Airport Road",
                "corridor:Hosur Road",
                "corridor:ORR East 1",
            ],
            "closed_node_id": "corridor:ORR East 1",
        },
    )
    body = resp.json()
    assert body["valid"] is False
    assert body["reenters_closed_zone"] is True


@pytest.mark.asyncio
async def test_m08_concurrent_atlas_lookups(wired_client):
    """Parallel atlas reads must remain stable and under SLA."""
    junctions = ["junction:ORR-Sarjapur", "junction:Mysore-NICE", "junction:Hebbal-flyover"]

    async def _lookup(jid: str):
        return await wired_client.get(f"/diversions/atlas/{jid}")

    results = await asyncio.gather(*[_lookup(j) for j in junctions])
    for resp in results:
        assert resp.status_code == 200
        assert resp.json()["latency_ms"] < 80


@pytest.mark.asyncio
async def test_m08_non_corridor_fallback_routes(wired_client):
    """Tier-3-style fallback: Non-corridor returns generic atlas routes."""
    resp = await wired_client.post(
        "/diversions/compute",
        json={"corridor": "Non-corridor", "k": 3},
    )
    assert resp.status_code == 200
    assert len(resp.json()["routes"]) >= 1


@pytest.mark.asyncio
async def test_m08_m06_diversion_refs_stable_on_cache_hit(wired_client):
    """M06 package diversion refs unchanged across cached re-read."""
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    planned = {
        "id": "FKIDROBM08C1",
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
    await wired_client.post("/ingest/planned", json=planned)
    await asyncio.sleep(0.35)

    pkg1 = (await wired_client.post("/planned/package", json={"event_id": "FKIDROBM08C1"})).json()
    pkg2 = (
        await wired_client.post(
            "/planned/package",
            json={"event_id": "FKIDROBM08C1", "force_refresh": False},
        )
    ).json()
    assert pkg1["diversion_refs"] == pkg2["diversion_refs"]


@pytest.mark.asyncio
async def test_m08_burst_scenario_requests(wired_client):
    """Multiple scenario lookups after ingest burst must not 500."""
    ids = [f"FKIDM08B{i:02d}" for i in range(5)]
    for i, eid in enumerate(ids):
        await wired_client.post(
            "/ingest/astram",
            json={
                **BASE_EVENT,
                "id": eid,
                "latitude": 12.96 + i * 0.005,
                "longitude": 77.68 + i * 0.003,
            },
        )
    await asyncio.sleep(0.4)

    for eid in ids:
        resp = await wired_client.get(f"/diversions/scenarios/{eid}")
        assert resp.status_code in {200, 422}
        if resp.status_code == 200:
            assert len(resp.json()["routes"]) >= 1


# --- M09 recommendation facade resilience ---


@pytest.mark.asyncio
async def test_m09_cached_card_returned_without_recompute(wired_client):
    """Second GET without refresh returns same card_id from cache."""
    eid = "FKIDROBM09C1"
    await _ingest_and_wait(wired_client, eid)

    first = (await wired_client.get(f"/recommendations/{eid}?refresh=true")).json()
    second = (await wired_client.get(f"/recommendations/{eid}")).json()
    assert first["card_id"] == second["card_id"]


@pytest.mark.asyncio
async def test_m09_skeleton_mode_skips_dispatch(wired_client):
    """Skeleton card returns partial status with dispatch_pending."""
    eid = "FKIDROBM09C2"
    await _ingest_and_wait(wired_client, eid)

    card = (await wired_client.get(f"/recommendations/{eid}?mode=skeleton&refresh=true")).json()
    assert card["status"] == "partial"
    assert card["dispatch_pending"] is True
    assert card["dispatch"] is None
    assert card["impact"]["rci"] > 0


@pytest.mark.asyncio
async def test_m09_unknown_event_returns_404(wired_client):
    resp = await wired_client.get("/recommendations/FKID-NO-SUCH")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_m09_burst_card_builds(wired_client):
    """Five concurrent card builds after ingest burst must not 500."""
    ids = [f"FKIDM09B{i:02d}" for i in range(5)]
    for i, eid in enumerate(ids):
        await wired_client.post(
            "/ingest/astram",
            json={**BASE_EVENT, "id": eid, "latitude": 12.96 + i * 0.004},
        )
    await asyncio.sleep(0.4)

    for eid in ids:
        resp = await wired_client.get(f"/recommendations/{eid}?refresh=true")
        assert resp.status_code in {200, 422}
        if resp.status_code == 200:
            assert resp.json()["card_id"].startswith("CARD-")
