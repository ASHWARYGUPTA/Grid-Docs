import time
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.config import settings
from grid_unlocked.hotspots.cache import hotspot_cache
from grid_unlocked.hotspots.cusum import cusum_tracker
from grid_unlocked.hotspots.dbscan import cluster_events_haversine
from grid_unlocked.hotspots.geo import haversine_km
from grid_unlocked.hotspots.historical import historical_index
from grid_unlocked.hotspots.poisson import poisson_forecaster
from grid_unlocked.hotspots.repository import HotspotRepository
from grid_unlocked.hotspots.schemas import (
    AnomaliesResponse,
    CellDensityPoint,
    CellHistorySummary,
    DensityHotspotsResponse,
    ObservedHotspotsResponse,
    PredictedHotspotsResponse,
)
from grid_unlocked.hotspots.static_blackspots import static_blackspot_clusters


class HotspotService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = HotspotRepository(session)

    @staticmethod
    def warm() -> None:
        historical_index.load()
        poisson_forecaster.fit()
        cusum_tracker.set_baselines(historical_index.corridor_baselines)

    async def get_observed(self, *, use_cache: bool = True) -> ObservedHotspotsResponse:
        if use_cache:
            cached = await hotspot_cache.get_observed()
            if cached:
                return cached

        t0 = time.perf_counter()
        points = await self.repo.get_observable_events()
        clusters = cluster_events_haversine(
            points,
            eps_rad=settings.hotspot_dbscan_eps_rad,
            min_samples=settings.hotspot_dbscan_min_samples,
            persistence=historical_index.persistence_scores,
        )

        source = "live_dbscan"
        if not clusters:
            clusters = historical_index.historical_clusters(top_n=10)
            source = "historical_fallback"
        if not clusters:
            clusters = static_blackspot_clusters()
            source = "static_tier3"

        response = ObservedHotspotsResponse(
            clusters=clusters[:10],
            refreshed_at=datetime.now(UTC).isoformat(),
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
            source=source,
        )
        await hotspot_cache.set_observed(response)
        return response

    async def get_predicted(self, horizon_hours: int = 4, *, use_cache: bool = True) -> PredictedHotspotsResponse:
        if use_cache:
            cached = await hotspot_cache.get_predicted(horizon_hours)
            if cached:
                return cached

        t0 = time.perf_counter()
        forecasts = poisson_forecaster.forecast(horizon_hours)
        response = PredictedHotspotsResponse(
            horizon_hours=horizon_hours,
            forecasts=forecasts,
            refreshed_at=datetime.now(UTC).isoformat(),
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
            source="poisson_glm",
        )
        await hotspot_cache.set_predicted(horizon_hours, response)
        return response

    def get_density(self, min_count: int = 1) -> DensityHotspotsResponse:
        t0 = time.perf_counter()
        historical_index.load()
        cells = [
            CellDensityPoint(h3_res7=cell_id, centroid_lat=lat, centroid_lon=lon, count=count)
            for cell_id, lat, lon, count in historical_index.all_cell_densities(min_count=min_count)
        ]
        return DensityHotspotsResponse(
            cells=cells,
            refreshed_at=datetime.now(UTC).isoformat(),
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
        )

    def get_anomalies(self, window_hours: int = 24) -> AnomaliesResponse:
        return AnomaliesResponse(
            alerts=cusum_tracker.alerts_last_hours(window_hours),
            window_hours=window_hours,
        )

    def get_cell_history(self, h3_cell: str) -> CellHistorySummary:
        historical_index.load()
        summary = historical_index.cell_summary(h3_cell)
        return CellHistorySummary(**summary)

    @staticmethod
    def count_within_km(lat: float, lon: float, radius_km: float = 2.0) -> int:
        historical_index.load()
        points = [(p.lat, p.lon) for p in historical_index.all_points]
        from grid_unlocked.hotspots.geo import count_within_km

        return count_within_km(lat, lon, points, radius_km)

    @staticmethod
    def bellandur_in_top_clusters(clusters: list, top_n: int = 10) -> bool:
        for cluster in clusters[:top_n]:
            lat, lon = cluster.centroid_lat, cluster.centroid_lon
            if haversine_km(lat, lon, 12.969, 77.701) <= 1.5:
                return True
            if cluster.label and "Bellandur" in cluster.label:
                return True
        return False
