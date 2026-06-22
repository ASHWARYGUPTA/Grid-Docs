"""Stream A — /api/v1/incidents/active and /api/v1/corridors."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

import grid_unlocked.db.session as _session_module
from grid_unlocked.db.models import (
    CorridorCentroidRow,
    ImpactScoreRow,
    NormalizedEventRow,
)
from grid_unlocked.main import app


async def _add(row) -> None:
    async with _session_module.SessionLocal() as session:
        session.add(row)
        await session.commit()


def _event(
    event_id: str,
    *,
    status: str = "active",
    corridor: str = "ORR East 1",
    junction: str | None = "Marathahalli",
    ingested_at: datetime | None = None,
) -> NormalizedEventRow:
    return NormalizedEventRow(
        event_id=event_id,
        source="astram",
        event_type="unplanned",
        is_planned=False,
        event_cause="accident",
        status=status,
        authenticated=True,
        latitude=12.969,
        longitude=77.701,
        corridor=corridor,
        junction=junction,
        priority="High",
        requires_road_closure=True,
        start_datetime=datetime(2024, 3, 7, 12, 0, tzinfo=UTC),
        ingested_at=ingested_at or datetime.now(UTC),
    )


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_incidents_active_returns_real_coords(client):
    await _add(_event("MAP-A-1"))
    resp = await client.get("/api/v1/incidents/active")
    assert resp.status_code == 200
    body = resp.json()
    assert any(i["event_id"] == "MAP-A-1" for i in body["incidents"])
    inc = next(i for i in body["incidents"] if i["event_id"] == "MAP-A-1")
    assert inc["lat"] == pytest.approx(12.969)
    assert inc["lng"] == pytest.approx(77.701)
    assert inc["status"] == "active"
    assert inc["corridor"] == "ORR East 1"
    # Unscored: rci/p_closure/severity_band null, not 500
    assert inc["rci"] is None
    assert inc["p_closure"] is None
    assert inc["severity_band"] is None


@pytest.mark.asyncio
async def test_incidents_active_joins_latest_impact_score(client):
    await _add(_event("MAP-A-2"))
    # Two scores, only the latest should be reflected
    older = ImpactScoreRow(
        event_id="MAP-A-2",
        p_closure=0.3,
        ict_p20_h=1.0,
        ict_p50_h=2.0,
        ict_p80_h=3.0,
        rci=0.4,
        severity_band="LOW",
        source="test",
        closure_model_version="v0",
        ict_model_version="v0",
        staging_recommended=False,
        scored_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    newer = ImpactScoreRow(
        event_id="MAP-A-2",
        p_closure=0.82,
        ict_p20_h=1.0,
        ict_p50_h=2.0,
        ict_p80_h=3.0,
        rci=0.77,
        severity_band="HIGH",
        source="test",
        closure_model_version="v0",
        ict_model_version="v0",
        staging_recommended=True,
        scored_at=datetime.now(UTC),
    )
    await _add(older)
    await _add(newer)

    resp = await client.get("/api/v1/incidents/active")
    assert resp.status_code == 200
    inc = next(i for i in resp.json()["incidents"] if i["event_id"] == "MAP-A-2")
    assert inc["rci"] == pytest.approx(0.77)
    assert inc["p_closure"] == pytest.approx(0.82)
    assert inc["severity_band"] == "HIGH"


@pytest.mark.asyncio
async def test_incidents_active_filters_status_lowercase(client):
    await _add(_event("MAP-A-3", status="closed"))
    await _add(_event("MAP-A-4", status="resolved"))
    await _add(_event("MAP-A-5", status="active"))
    resp = await client.get("/api/v1/incidents/active")
    ids = [i["event_id"] for i in resp.json()["incidents"]]
    assert "MAP-A-5" in ids
    assert "MAP-A-3" not in ids
    assert "MAP-A-4" not in ids


@pytest.mark.asyncio
async def test_incidents_active_respects_limit(client):
    for n in range(5):
        await _add(_event(f"MAP-LIM-{n}"))
    resp = await client.get("/api/v1/incidents/active?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()["incidents"]) <= 2


@pytest.mark.asyncio
async def test_corridors_returns_real_centroids(client):
    await _add(
        CorridorCentroidRow(
            corridor="Mysore Road",
            lat=12.957,
            lon=77.503,
            sample_count=420,
        )
    )
    await _add(
        CorridorCentroidRow(
            corridor="Bellary Road 1",
            lat=13.097,
            lon=77.594,
            sample_count=312,
        )
    )
    resp = await client.get("/api/v1/corridors")
    assert resp.status_code == 200
    body = resp.json()
    by_name = {c["name"]: c for c in body["corridors"]}
    assert by_name["Mysore Road"]["lat"] == pytest.approx(12.957)
    assert by_name["Mysore Road"]["lon"] == pytest.approx(77.503)
    assert by_name["Mysore Road"]["sample_count"] == 420
    assert "Bellary Road 1" in by_name


@pytest.mark.asyncio
async def test_corridors_empty_when_unseeded(client):
    resp = await client.get("/api/v1/corridors")
    assert resp.status_code == 200
    assert resp.json() == {"corridors": []}
