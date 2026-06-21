"""M16 FieldOfficerApp tests."""

import asyncio
from datetime import UTC, datetime

import grid_unlocked.db.session as _session_module
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from grid_unlocked.dashboard.bus import dashboard_bus
from grid_unlocked.db.models import FieldClosureRow
from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.main import app
from grid_unlocked.propagation.subscriber import register_propagation_subscribers

HEAVY_ORR = {
    "id": "FKIDFIELD0001",
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


@pytest.fixture
async def client():
    register_feature_subscribers()
    register_propagation_subscribers()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _dispatch_recommendation(client, event: dict) -> str:
    await client.post("/ingest/astram", json=event)
    await asyncio.sleep(0.25)
    resp = await client.post(
        "/dispatch/recommend", json={"event_id": event["id"], "force_greedy": True}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["recommendation_id"]


@pytest.mark.asyncio
async def test_packet_contains_provenance_and_ict_bands(client):
    rec_id = await _dispatch_recommendation(client, HEAVY_ORR)

    resp = await client.get(f"/field/packet/{rec_id}")
    assert resp.status_code == 200, resp.text
    packet = resp.json()
    assert packet["recommendation_id"] == rec_id
    assert packet["event_id"] == HEAVY_ORR["id"]
    assert packet["impact"]["ict_p20_h"] >= 0
    assert packet["impact"]["ict_p50_h"] >= 0
    assert packet["impact"]["ict_p80_h"] >= 0
    assert packet["provenance"] == {
        "dispatch": "M07",
        "impact": "M03",
        "diversion": "M08",
        "tier": "M14",
    }
    assert packet["already_closed"] is False
    assert packet["acknowledged"] is False


@pytest.mark.asyncio
async def test_packet_no_diversion_available(client, monkeypatch):
    from grid_unlocked.diversions.schemas import ScenarioResponse
    from grid_unlocked.diversions.service import DiversionService

    rec_id = await _dispatch_recommendation(client, {**HEAVY_ORR, "id": "FKIDFIELD0010"})

    async def empty_scenarios(self, event_id):
        return ScenarioResponse(
            event_id=event_id,
            corridor=None,
            junction_id="junction:none",
            p_closure=0.2,
            is_peak_hour=False,
            auto_suggest=False,
            routes=[],
            latency_ms=0.0,
        )

    monkeypatch.setattr(DiversionService, "scenarios", empty_scenarios)

    resp = await client.get(f"/field/packet/{rec_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["top_diversion"] is None


@pytest.mark.asyncio
async def test_packet_404_unknown_recommendation(client):
    resp = await client.get("/field/packet/DISP-DOES-NOT-EXIST")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ack_persists_and_is_idempotent(client):
    rec_id = await _dispatch_recommendation(client, {**HEAVY_ORR, "id": "FKIDFIELD0002"})

    first = await client.post(f"/field/ack/{rec_id}", json={"officer_id": "OFF-001"})
    assert first.status_code == 200
    assert first.json()["acknowledged"] is True

    second = await client.post(f"/field/ack/{rec_id}", json={"officer_id": "OFF-002"})
    assert second.status_code == 200

    packet = (await client.get(f"/field/packet/{rec_id}")).json()
    assert packet["acknowledged"] is True
    assert packet["acknowledged_at"] is not None


@pytest.mark.asyncio
async def test_ack_404_unknown_recommendation(client):
    resp = await client.post("/field/ack/DISP-NOPE", json={"officer_id": "OFF-001"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_close_writes_field_closures_and_closes_event(client):
    event_id = "FKIDFIELD0003"
    await _dispatch_recommendation(client, {**HEAVY_ORR, "id": event_id})

    closed_dt = datetime.now(UTC).isoformat()
    resp = await client.post(
        f"/field/close/{event_id}",
        json={
            "closed_datetime": closed_dt,
            "barricades_used": 3,
            "officers_used": 2,
            "diversion_activated": True,
            "notes": "Cleared via crane",
            "officer_id": "OFF-003",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["event_closed"] is True

    event_resp = await client.get(f"/events/{event_id}")
    assert event_resp.json()["status"] == "closed"

    async with _session_module.SessionLocal() as session:
        row = await session.scalar(
            select(FieldClosureRow).where(FieldClosureRow.event_id == event_id)
        )
        assert row is not None
        assert row.barricades_used == 3
        assert row.officers_used == 2
        assert row.diversion_activated is True
        assert row.notes == "Cleared via crane"


@pytest.mark.asyncio
async def test_close_validation_barricades_negative_rejected(client):
    event_id = "FKIDFIELD0004"
    await _dispatch_recommendation(client, {**HEAVY_ORR, "id": event_id})

    resp = await client.post(
        f"/field/close/{event_id}",
        json={
            "closed_datetime": datetime.now(UTC).isoformat(),
            "barricades_used": -1,
            "officers_used": 1,
            "diversion_activated": False,
            "officer_id": "OFF-004",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_close_validation_officers_zero_rejected(client):
    event_id = "FKIDFIELD0005"
    await _dispatch_recommendation(client, {**HEAVY_ORR, "id": event_id})

    resp = await client.post(
        f"/field/close/{event_id}",
        json={
            "closed_datetime": datetime.now(UTC).isoformat(),
            "barricades_used": 0,
            "officers_used": 0,
            "diversion_activated": False,
            "officer_id": "OFF-005",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_close_idempotency_conflict(client):
    event_id = "FKIDFIELD0006"
    await _dispatch_recommendation(client, {**HEAVY_ORR, "id": event_id})

    body = {
        "closed_datetime": datetime.now(UTC).isoformat(),
        "barricades_used": 1,
        "officers_used": 1,
        "diversion_activated": False,
        "officer_id": "OFF-006",
    }
    first = await client.post(f"/field/close/{event_id}", json=body)
    assert first.status_code == 200

    second = await client.post(f"/field/close/{event_id}", json=body)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_close_event_not_found(client):
    resp = await client.post(
        "/field/close/NO-SUCH-EVENT",
        json={
            "closed_datetime": datetime.now(UTC).isoformat(),
            "barricades_used": 1,
            "officers_used": 1,
            "diversion_activated": False,
            "officer_id": "OFF-007",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_tier_proxies_governance(client):
    field_tier = await client.get("/field/tier")
    gov_tier = await client.get("/governance/tier")
    assert field_tier.status_code == 200
    assert gov_tier.status_code == 200
    assert field_tier.json()["tier"] == gov_tier.json()["tier"]
    assert field_tier.json()["shadow_mode"] == gov_tier.json()["shadow_mode"]


@pytest.mark.asyncio
async def test_ack_publishes_field_delta(client):
    rec_id = await _dispatch_recommendation(client, {**HEAVY_ORR, "id": "FKIDFIELD0008"})

    published = []
    original_publish = dashboard_bus.publish

    async def spy_publish(delta):
        published.append(delta)
        await original_publish(delta)

    dashboard_bus.publish = spy_publish
    try:
        await client.post(f"/field/ack/{rec_id}", json={"officer_id": "OFF-008"})
    finally:
        dashboard_bus.publish = original_publish

    assert any(
        d.scope == "field" and d.payload.get("type") == "FieldAcknowledged" for d in published
    )


@pytest.mark.asyncio
async def test_close_publishes_field_delta(client):
    event_id = "FKIDFIELD0009"
    await _dispatch_recommendation(client, {**HEAVY_ORR, "id": event_id})

    published = []
    original_publish = dashboard_bus.publish

    async def spy_publish(delta):
        published.append(delta)
        await original_publish(delta)

    dashboard_bus.publish = spy_publish
    try:
        await client.post(
            f"/field/close/{event_id}",
            json={
                "closed_datetime": datetime.now(UTC).isoformat(),
                "barricades_used": 1,
                "officers_used": 1,
                "diversion_activated": False,
                "officer_id": "OFF-009",
            },
        )
    finally:
        dashboard_bus.publish = original_publish

    assert any(
        d.scope == "field" and d.payload.get("type") == "FieldClosureSubmitted"
        for d in published
    )
