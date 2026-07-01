"""M17 CitizenReportService tests."""

import io

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from grid_unlocked.citizen.centroid_seed import centroids_need_seed, seed_corridor_centroids_from_csv
from grid_unlocked.citizen.cause_hint import infer_cause_hint
from grid_unlocked.citizen.geo import nearest_corridor
from grid_unlocked.citizen.repository import CitizenRepository
from grid_unlocked.citizen.service import CitizenService
import grid_unlocked.db.session as _session_module
from grid_unlocked.dashboard.bus import dashboard_bus
from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.hotspots.geo import h3_res7
from grid_unlocked.hotspots.subscriber import register_hotspot_subscribers
from grid_unlocked.impact.registry import registry
from grid_unlocked.ingestion.vocab import VALID_CAUSES
from grid_unlocked.ingestion.validator import normalize_cause
from grid_unlocked.main import app
from grid_unlocked.propagation.subscriber import register_propagation_subscribers


def _jpeg_bytes(*, with_gps: tuple[float, float] | None = None) -> bytes:
    img = Image.new("RGB", (4, 4), color="red")
    out = io.BytesIO()
    if with_gps is None:
        img.save(out, format="JPEG")
    else:
        lat, lon = with_gps
        exif = Image.Exif()
        gps_ifd = exif.get_ifd(0x8825)
        gps_ifd[1] = "N" if lat >= 0 else "S"
        gps_ifd[2] = (abs(lat), 0.0, 0.0)
        gps_ifd[3] = "E" if lon >= 0 else "W"
        gps_ifd[4] = (abs(lon), 0.0, 0.0)
        img.save(out, format="JPEG", exif=exif.tobytes())
    return out.getvalue()


async def _ensure_centroids_seeded() -> None:
    async with _session_module.SessionLocal() as session:
        if await centroids_need_seed(session):
            await seed_corridor_centroids_from_csv(session)


@pytest.fixture
async def client():
    register_feature_subscribers()
    register_propagation_subscribers()
    register_hotspot_subscribers()
    registry.load()
    await _ensure_centroids_seeded()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


BLR_LAT, BLR_LON = 12.9698, 77.701  # inside Bengaluru bbox, near ORR East 1 corridor data


@pytest.mark.asyncio
async def test_corridor_snap_matches_independently_computed_centroid(client):
    """The service's nearest_corridor() must agree with an independently-built
    centroid table for the same set of sample points — verifies the seeded
    lookup and the haversine-nearest logic are wired together correctly."""
    async with _session_module.SessionLocal() as session:
        centroids = await CitizenRepository(session).get_all_centroids()
    assert len(centroids) >= 15  # sanity: most named corridors + Non-corridor seeded

    samples = [
        (13.0400041, 77.5180991),
        (12.9218755, 77.6451585),
        (12.97884, 77.59954),
        (13.00085, 77.68137),
        (12.94457, 77.5274),
        (13.04189, 77.59471),
        (12.97528, 77.62569),
        (13.06339, 77.59335),
        (13.00014, 77.58406),
        (12.90712, 77.62864),
        (12.90774, 77.60057),
        (13.0447, 77.58285),
        (12.97892, 77.5644),
        (12.95461, 77.64234),
        (12.93613, 77.5187),
        (13.01273, 77.55451),
        (12.98075, 77.60282),
        (12.96252, 77.64157),
        (13.03795, 77.62577),
        (13.03941, 77.64146),
    ]
    assert len(samples) == 20

    for lat, lon in samples:
        resp = await client.post(
            "/citizen/report",
            data={"lat": lat, "lon": lon},
            files={"photo": ("p.jpg", _jpeg_bytes(), "image/jpeg")},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["corridor"] == nearest_corridor(lat, lon, centroids)
        assert body["h3_cell"] == h3_res7(lat, lon)


@pytest.mark.asyncio
async def test_missing_gps_and_exif_returns_400(client):
    resp = await client.post(
        "/citizen/report",
        files={"photo": ("p.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert resp.status_code == 400
    assert "location" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_exif_gps_fallback_when_no_device_coords(client):
    resp = await client.post(
        "/citizen/report",
        files={"photo": ("p.jpg", _jpeg_bytes(with_gps=(BLR_LAT, BLR_LON)), "image/jpeg")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["h3_cell"] == h3_res7(BLR_LAT, BLR_LON)


@pytest.mark.asyncio
async def test_outside_bbox_returns_400(client):
    resp = await client.post(
        "/citizen/report",
        data={"lat": 10.0, "lon": 77.5},
        files={"photo": ("p.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_ict_quote_returned_in_same_response(client):
    resp = await client.post(
        "/citizen/report",
        data={"lat": BLR_LAT, "lon": BLR_LON, "description": "water logging near signal"},
        files={"photo": ("p.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["ict_p50"] > 0
    assert body["ict_p80"] >= body["ict_p50"]
    assert 0.0 <= body["p_closure"] <= 1.0
    assert body["cause_hint"] == "water_logging"
    assert body["event_id"] is not None


@pytest.mark.asyncio
async def test_unverified_citizen_event_does_not_trigger_dispatch(client):
    resp = await client.post(
        "/citizen/report",
        data={"lat": BLR_LAT, "lon": BLR_LON},
        files={"photo": ("p.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    body = resp.json()
    event_id = body["event_id"]
    assert event_id is not None

    card_resp = await client.get(f"/recommendations/{event_id}?mode=complete&refresh=true")
    assert card_resp.status_code == 200
    card = card_resp.json()
    assert card["dispatch"] is None
    assert card["dispatch_pending"] is True
    assert card["provenance"]["dispatch"] == "awaiting_citizen_verification"
    assert card["source"] == "citizen"


@pytest.mark.asyncio
async def test_verify_promotes_event_and_enables_dispatch(client):
    resp = await client.post(
        "/citizen/report",
        data={"lat": BLR_LAT, "lon": BLR_LON},
        files={"photo": ("p.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    report_id = resp.json()["report_id"]
    event_id = resp.json()["event_id"]
    assert event_id is not None

    verify_resp = await client.post(
        f"/citizen/verify/{report_id}", json={"commander_id": "CMD-001"}
    )
    assert verify_resp.status_code == 200, verify_resp.text
    card = verify_resp.json()
    assert card["dispatch"] is not None
    assert card["source"] == "citizen"

    refetch = await client.get(f"/recommendations/{event_id}?mode=complete&refresh=true")
    assert refetch.json()["dispatch"] is not None

    status_resp = await client.get(f"/citizen/report/{report_id}")
    assert status_resp.json()["status"] == "verified"


@pytest.mark.asyncio
async def test_reject_is_audit_only(client):
    resp = await client.post(
        "/citizen/report",
        data={"lat": BLR_LAT, "lon": BLR_LON},
        files={"photo": ("p.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    report_id = resp.json()["report_id"]
    event_id = resp.json()["event_id"]

    reject_resp = await client.post(
        f"/citizen/reject/{report_id}", json={"reason_code": "DUPLICATE"}
    )
    assert reject_resp.status_code == 200

    status_resp = await client.get(f"/citizen/report/{report_id}")
    assert status_resp.json()["status"] == "rejected"

    if event_id:
        event_resp = await client.get(f"/events/{event_id}")
        assert event_resp.json()["authenticated"] is False


@pytest.mark.asyncio
async def test_photo_size_and_type_validation(client):
    oversized = b"\xff" * (5 * 1024 * 1024 + 1)
    resp = await client.post(
        "/citizen/report",
        data={"lat": BLR_LAT, "lon": BLR_LON},
        files={"photo": ("p.jpg", oversized, "image/jpeg")},
    )
    assert resp.status_code == 400

    resp2 = await client.post(
        "/citizen/report",
        data={"lat": BLR_LAT, "lon": BLR_LON},
        files={"photo": ("p.gif", _jpeg_bytes(), "image/gif")},
    )
    assert resp2.status_code == 400


@pytest.mark.asyncio
async def test_subscribe_and_unsubscribe(client):
    resp = await client.post(
        "/citizen/subscribe",
        json={"user_ref": "USER-001", "corridors": ["ORR East 1"], "h3_cells": []},
    )
    assert resp.status_code == 200
    sub_id = resp.json()["subscription_id"]

    delete_resp = await client.delete(f"/citizen/subscribe/{sub_id}")
    assert delete_resp.status_code == 200

    delete_again = await client.delete(f"/citizen/subscribe/{sub_id}")
    assert delete_again.status_code == 404


@pytest.mark.asyncio
async def test_subscribe_requires_corridor_or_h3(client):
    resp = await client.post(
        "/citizen/subscribe", json={"user_ref": "USER-002", "corridors": [], "h3_cells": []}
    )
    assert resp.status_code == 400


BELLANDUR_CLUSTER_EVENTS = [
    {
        "id": f"FKIDCTZ{i:04d}",
        "event_type": "unplanned",
        "latitude": 12.969 + i * 0.0003,
        "longitude": 77.701 + i * 0.0003,
        "address": "Bellandur Flyover",
        "event_cause": cause,
        "requires_road_closure": False,
        "start_datetime": "2024-03-07T12:00:00+00:00",
        "status": "active",
        "authenticated": "yes",
        "created_date": "2024-03-07T12:05:00+00:00",
        "corridor": "ORR East 1",
        "priority": "High",
        "veh_type": "lcv",
    }
    for i, cause in enumerate(
        ["accident", "vehicle_breakdown", "accident", "vehicle_breakdown", "accident", "vehicle_breakdown", "water_logging"]
    )
]


@pytest.mark.asyncio
async def test_subscription_pre_alert_via_check_pre_alerts(client):
    for event in BELLANDUR_CLUSTER_EVENTS:
        await client.post("/ingest/astram", json=event)

    sub_resp = await client.post(
        "/citizen/subscribe",
        json={"user_ref": "USER-003", "corridors": ["ORR East 1"], "h3_cells": []},
    )
    assert sub_resp.status_code == 200

    published = []
    original_publish = dashboard_bus.publish

    async def spy_publish(delta):
        published.append(delta)
        await original_publish(delta)

    dashboard_bus.publish = spy_publish
    try:
        async with _session_module.SessionLocal() as session:
            count = await CitizenService(session).check_pre_alerts()
    finally:
        dashboard_bus.publish = original_publish

    assert count > 0
    assert any(d.payload.get("type") == "CitizenPreAlert" for d in published)


@pytest.mark.asyncio
async def test_check_pre_alerts_returns_zero_with_no_subscriptions(client):
    async with _session_module.SessionLocal() as session:
        count = await CitizenService(session).check_pre_alerts()
    assert count == 0


# --- Regression tests for bugs found while reading the existing codebase ---


def test_unknown_obstruction_cause_passes_validation():
    """Pre-existing bug: unknown_obstruction was a VALID_CAUSES member but missing
    from CAUSE_ALIASES, so normalize_cause() raised. M17's default low-confidence
    cause depends on this working."""
    assert normalize_cause("unknown_obstruction") == "unknown_obstruction"


def test_cause_hint_vocabulary_is_valid():
    """Every cause infer_cause_hint() can emit must be a real VALID_CAUSES member —
    regression guard against the exact vocabulary-drift bug found above."""
    descriptions = [
        None,
        "water logging near junction",
        "accident on flyover",
        "vehicle breakdown blocking lane",
        "tree fall after storm",
        "pothole damaged car",
        "some random unrelated text",
    ]
    for desc in descriptions:
        cause, confidence = infer_cause_hint(desc)
        assert cause in VALID_CAUSES
        assert 0.0 <= confidence <= 1.0


@pytest.mark.asyncio
async def test_build_card_gates_dispatch_on_authenticated(client):
    """Regression: build_card() previously had no check on authenticated at all —
    any event (not just citizen-sourced) would flow into M07 dispatch. Isolate the
    gate from the rest of the M17 pipeline by ingesting directly via /ingest/astram."""
    unauth_event = {
        "id": "FKIDUNAUTH01",
        "event_type": "unplanned",
        "latitude": BLR_LAT,
        "longitude": BLR_LON,
        "event_cause": "accident",
        "requires_road_closure": False,
        "start_datetime": "2024-03-07T12:00:00+00:00",
        "status": "active",
        "authenticated": "no",
        "corridor": "ORR East 1",
        "priority": "High",
    }
    await client.post("/ingest/astram", json=unauth_event)

    card_resp = await client.get("/recommendations/FKIDUNAUTH01?mode=complete&refresh=true")
    assert card_resp.json()["dispatch"] is None

    # flip authenticated directly and confirm dispatch becomes available
    async with _session_module.SessionLocal() as session:
        await CitizenRepository(session).set_event_authenticated("FKIDUNAUTH01", True)

    refreshed = await client.get("/recommendations/FKIDUNAUTH01?mode=complete&refresh=true")
    assert refreshed.json()["dispatch"] is not None


@pytest.mark.asyncio
async def test_corridor_centroid_seeding_idempotent():
    async with _session_module.SessionLocal() as session:
        assert await centroids_need_seed(session) is True
        first = await seed_corridor_centroids_from_csv(session)
    assert first["corridors_seeded"] > 0

    async with _session_module.SessionLocal() as session:
        assert await centroids_need_seed(session) is False
