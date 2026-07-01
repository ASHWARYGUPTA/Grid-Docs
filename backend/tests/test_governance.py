"""M14 — GovernanceConsole tests.

Covers every testing decision from the spec:
  1. Chaos: kill M03 -> auto Tier 2 within probe cycle
  2. Manual override logged with operator_id
  3. Shadow: M10 call rejected when shadow_mode=true (already covered by
     test_execution.py / test_vms.py via the live settings proxy; here we
     additionally verify the M14 API path produces the same effect)
  4. Drill: forced timeout -> 100% GREEDY_FALLBACK with latency <1.8s
  5. Promotion: incomplete checklist -> 403 on promote
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from grid_unlocked.config import settings
from grid_unlocked.db import session as _session_module
from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.governance.service import GovernanceService, read_cached_state
from grid_unlocked.impact.registry import registry
from grid_unlocked.main import app
from grid_unlocked.propagation.subscriber import register_propagation_subscribers

HEAVY_ORR = {
    "id": "FKIDGOV0001",
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
}


@pytest.fixture
async def client():
    register_feature_subscribers()
    register_propagation_subscribers()
    registry.load()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Pre-bootstrap proxy behavior (no M14 write yet)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tier_endpoint_reflects_settings_before_any_write(client):
    """GET /governance/tier with no prior M14 write must reflect settings
    defaults (governance_tier=1, shadow_mode=True)."""
    resp = await client.get("/governance/tier")
    assert resp.status_code == 200
    body = resp.json()
    assert body["tier"] == "1"
    assert body["shadow_mode"] is True
    assert body["manual_mode"] is False


# ---------------------------------------------------------------------------
# Manual tier override — logged with operator_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_override_tier_is_logged_with_operator_id(client):
    resp = await client.post(
        "/governance/override-tier",
        json={"tier": "2", "reason": "Maintenance window", "operator_id": "OPS-001"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tier"] == "2"
    assert body["updated_by"] == "OPS-001"

    transitions = (await client.get("/governance/transitions")).json()
    assert transitions["count"] >= 1
    latest = transitions["transitions"][0]
    assert latest["from_tier"] == "1"
    assert latest["to_tier"] == "2"
    assert latest["operator_id"] == "OPS-001"
    assert latest["reason"] == "Maintenance window"


@pytest.mark.asyncio
async def test_override_tier_updates_get_governance_cache(client):
    """Once M14 writes, get_governance() (used by M07/M09/M10/M11) must read
    the new tier — not the static settings default."""
    await client.post(
        "/governance/override-tier",
        json={"tier": "3", "reason": "Cascading outage drill", "operator_id": "OPS-002"},
    )
    cached = read_cached_state()
    assert cached.tier == "3"
    assert cached.manual_mode is True


# ---------------------------------------------------------------------------
# Shadow mode toggle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shadow_mode_toggle_blocks_m10_execution(client):
    """Toggling shadow_mode=false via M14 must allow M10 to actually enqueue,
    and toggling it back to true must re-block — end-to-end through the
    in-process cache, not just the response payload."""
    from grid_unlocked.execution.service import setup_command_queue
    from grid_unlocked.execution.station_client import MockStationClient

    queue = await setup_command_queue(station_client=MockStationClient(failure_rate=0.0))

    off = await client.post(
        "/governance/shadow-mode", json={"enabled": False, "operator_id": "OPS-003"}
    )
    assert off.status_code == 200
    assert off.json()["shadow_mode"] is False

    dispatch_resp = await client.post(
        "/execute/dispatch",
        json={
            "approval_token": "APPR-GOV-001",
            "card_id": "CARD-GOV0001",
            "event_id": "EVT-GOV001",
            "commander_id": "CMD-GOV",
        },
    )
    assert dispatch_resp.status_code == 200, "shadow_mode=false via M14 must unblock M10"
    await asyncio.sleep(0.5)  # let the M10 background worker finish before the next governance write

    on = await client.post(
        "/governance/shadow-mode", json={"enabled": True, "operator_id": "OPS-003"}
    )
    assert on.json()["shadow_mode"] is True

    blocked_resp = await client.post(
        "/execute/dispatch",
        json={
            "approval_token": "APPR-GOV-002",
            "card_id": "CARD-GOV0002",
            "event_id": "EVT-GOV002",
            "commander_id": "CMD-GOV",
        },
    )
    assert blocked_resp.status_code == 403

    await queue.stop()


# ---------------------------------------------------------------------------
# Health rollup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_rollup_reports_all_modules(client):
    resp = await client.get("/governance/health")
    assert resp.status_code == 200
    body = resp.json()
    module_names = {m["module"] for m in body["modules"]}
    assert module_names == {
        "M01_Ingestion",
        "M02_Features",
        "M03_Impact",
        "M07_Dispatch",
        "M10_Execution",
        "M11_VMS",
    }
    assert body["overall_status"] in {"healthy", "degraded", "down"}


@pytest.mark.asyncio
async def test_health_rollup_dispatch_fallback_rate(client):
    """After running greedy-forced dispatches, M07 health must reflect a
    non-zero fallback rate rather than a hardcoded value."""
    await client.post("/ingest/astram", json=HEAVY_ORR)
    await asyncio.sleep(0.3)
    dispatch_resp = await client.post(
        "/dispatch/recommend", json={"event_id": "FKIDGOV0001", "force_greedy": True}
    )
    assert dispatch_resp.status_code == 200

    resp = await client.get("/governance/health")
    dispatch_health = next(m for m in resp.json()["modules"] if m["module"] == "M07_Dispatch")
    assert dispatch_health["metrics"]["fallback_rate"] == 1.0


# ---------------------------------------------------------------------------
# Automatic tier transitions — M03 down -> Tier 2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m03_down_triggers_auto_tier2(client, monkeypatch):
    """Chaos test: when M03's ML models are unavailable (rule-fallback active),
    evaluate_auto_transition() must downgrade to Tier 2."""
    monkeypatch.setattr(registry, "_ml_available", False)

    async with _session_module.SessionLocal() as session:
        await GovernanceService(session).evaluate_auto_transition()

    cached = read_cached_state()
    assert cached.tier == "2"

    transitions = (await client.get("/governance/transitions")).json()
    latest = transitions["transitions"][0]
    assert latest["operator_id"] is None, "Automatic transitions must have no operator_id"
    assert latest["to_tier"] == "2"


@pytest.mark.asyncio
async def test_healthy_system_recovers_to_tier1_after_hysteresis(client, monkeypatch):
    """After a Tier 2 downgrade, once the system is healthy again the auto
    loop must wait out the recovery hysteresis before upgrading back to 1."""
    import grid_unlocked.governance.service as gov_module

    monkeypatch.setattr(gov_module, "RECOVERY_HYSTERESIS_SECONDS", 0)
    monkeypatch.setattr(registry, "_ml_available", False)

    async with _session_module.SessionLocal() as session:
        await GovernanceService(session).evaluate_auto_transition()
    assert read_cached_state().tier == "2"

    monkeypatch.setattr(registry, "_ml_available", True)
    async with _session_module.SessionLocal() as session:
        await GovernanceService(session).evaluate_auto_transition()
    async with _session_module.SessionLocal() as session:
        await GovernanceService(session).evaluate_auto_transition()

    assert read_cached_state().tier == "1"


# ---------------------------------------------------------------------------
# Cascade drill
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cascade_drill_with_no_active_incidents_fails_honestly(client):
    resp = await client.post("/governance/drills/cascade", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["passed"] is False
    assert "no active incidents" in body["detail"].lower()


@pytest.mark.asyncio
async def test_cascade_drill_forced_timeout_yields_100pct_greedy_fallback(client):
    """Forced MILP timeout (force_milp_timeout=True) against an active incident
    must yield 100% GREEDY_FALLBACK within the dispatch deadline."""
    await client.post("/ingest/astram", json=HEAVY_ORR)
    await asyncio.sleep(0.3)

    resp = await client.post(
        "/governance/drills/cascade",
        json={"drill_type": "cascade", "concurrent_closures": 5, "force_milp_timeout": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["passed"] is True
    assert body["fallback_rate"] == 1.0
    assert body["max_latency_ms"] < settings.dispatch_total_deadline_ms

    last = await client.get("/governance/drills/cascade/last")
    assert last.status_code == 200
    assert last.json()["passed"] is True


@pytest.mark.asyncio
async def test_last_drill_404_when_none_run(client):
    resp = await client.get("/governance/drills/cascade/last")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Promotion checklist — incomplete -> 403 on approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_promotion_checklist_incomplete_blocks_approval(client):
    checklist = await client.get("/governance/promotion/checklist/closure-v2")
    assert checklist.status_code == 200
    body = checklist.json()
    assert body["all_complete"] is False
    assert all(not item["complete"] for item in body["items"])

    approve = await client.post(
        "/governance/promotion/approve",
        json={"model_version": "closure-v2", "operator_id": "OPS-004"},
    )
    assert approve.status_code == 403
