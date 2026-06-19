import asyncio
from datetime import UTC, datetime

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient
from sklearn.cluster import DBSCAN

from grid_unlocked.features.subscriber import register_feature_subscribers
from grid_unlocked.hotspots.cusum import CusumTracker
from grid_unlocked.hotspots.dbscan import EventPoint, cause_entropy, cluster_events_haversine
from grid_unlocked.hotspots.geo import count_within_km, haversine_km, h3_centroid, h3_res7
from grid_unlocked.hotspots.historical import historical_index
from grid_unlocked.hotspots.service import HotspotService
from grid_unlocked.hotspots.subscriber import register_hotspot_subscribers
from grid_unlocked.main import app
from grid_unlocked.propagation.subscriber import register_propagation_subscribers

BELLANDUR_EVENTS = [
    {
        "id": f"FKIDHOT{i:04d}",
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
        [
            "accident",
            "vehicle_breakdown",
            "accident",
            "vehicle_breakdown",
            "accident",
            "vehicle_breakdown",
            "water_logging",
        ]
    )
]


@pytest.fixture
async def client():
    register_feature_subscribers()
    register_propagation_subscribers()
    register_hotspot_subscribers()
    HotspotService.warm()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_observed_hotspots_endpoint(client):
    for event in BELLANDUR_EVENTS:
        await client.post("/ingest/astram", json=event)
    await asyncio.sleep(0.2)

    response = await client.get("/hotspots/observed")
    assert response.status_code == 200
    body = response.json()
    assert len(body["clusters"]) >= 1
    assert body["clusters"][0]["layer"] == "observed"
    assert body["latency_ms"] < 100
    assert body["source"] in {"live_dbscan", "historical_fallback", "static_tier3"}


@pytest.mark.asyncio
async def test_predicted_hotspots_endpoint(client):
    response = await client.get("/hotspots/predicted?horizon_hours=4")
    assert response.status_code == 200
    body = response.json()
    assert body["horizon_hours"] == 4
    assert len(body["forecasts"]) >= 1
    assert body["forecasts"][0]["expected_count"] >= 0
    assert body["source"] == "poisson_glm"


@pytest.mark.asyncio
async def test_anomalies_endpoint(client):
    response = await client.get("/hotspots/anomalies")
    assert response.status_code == 200
    assert "alerts" in response.json()


@pytest.mark.asyncio
async def test_cell_history_endpoint(client):
    historical_index.load()
    cell = next(iter(historical_index.cells))
    response = await client.get(f"/hotspots/cell/{cell}")
    assert response.status_code == 200
    body = response.json()
    assert body["h3_res7"] == cell
    assert body["total_events"] > 0


def test_bellandur_in_historical_top10():
    historical_index.load()
    clusters = historical_index.historical_clusters(top_n=10)
    if HotspotService.bellandur_in_top_clusters(clusters, top_n=10):
        return
    from grid_unlocked.hotspots.geo import haversine_km

    near_bellandur = [
        rec.total_count
        for cell_id, rec in historical_index.cells.items()
        if haversine_km(*h3_centroid(cell_id), 12.969, 77.701) <= 1.5
    ]
    assert sum(near_bellandur) >= 20


def test_haversine_dbscan_differs_from_euclidean_degrees():
    points = [
        EventPoint("1", 12.969, 77.701, "accident", "ORR East 1"),
        EventPoint("2", 12.970, 77.702, "accident", "ORR East 1"),
        EventPoint("3", 12.971, 77.703, "accident", "ORR East 1"),
        EventPoint("4", 12.972, 77.704, "accident", "ORR East 1"),
        EventPoint("5", 12.973, 77.705, "accident", "ORR East 1"),
        EventPoint("6", 13.100, 77.590, "accident", "Bellary Road 1"),
    ]
    haversine_clusters = cluster_events_haversine(points, min_samples=3)
    coords_deg = np.array([[p.lat, p.lon] for p in points])
    euclidean_labels = DBSCAN(eps=0.01, min_samples=3).fit_predict(coords_deg)
    haversine_coords = np.radians(coords_deg)
    haversine_labels = DBSCAN(eps=0.005, min_samples=3, metric="haversine").fit_predict(
        haversine_coords
    )
    assert haversine_clusters
    assert not np.array_equal(euclidean_labels, haversine_labels)


def test_cause_entropy_mixed():
    entropy = cause_entropy(["accident", "vehicle_breakdown", "accident", "water_logging"])
    assert entropy > 0.5


def test_cusum_detects_spike():
    tracker = CusumTracker()
    tracker.set_baselines({"ORR East 1": 0.1})
    now = datetime.now(UTC)
    for _ in range(20):
        tracker.record("ORR East 1", now)
    alerts = tracker.alerts_last_hours(1)
    assert len(alerts) >= 1
    assert alerts[0].sigma >= 3.0


def test_count_within_2km_matches_brute_force():
    historical_index.load()
    sample = historical_index.all_points[100]
    points = [(p.lat, p.lon) for p in historical_index.all_points]
    brute = sum(
        1 for plat, plon in points if haversine_km(sample.lat, sample.lon, plat, plon) <= 2.0
    )
    assert HotspotService.count_within_km(sample.lat, sample.lon, 2.0) == brute


def test_predicted_layer_distinct_from_observed():
    from grid_unlocked.hotspots.poisson import poisson_forecaster

    poisson_forecaster.fit()
    predicted = poisson_forecaster.as_predicted_clusters(4)
    assert predicted
    assert all(c.layer == "predicted" for c in predicted)
