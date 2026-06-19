"""Travel time estimates for dispatch scoring."""

from __future__ import annotations

from grid_unlocked.hotspots.geo import haversine_km


def eta_minutes(
    unit_lat: float,
    unit_lon: float,
    incident_lat: float,
    incident_lon: float,
    avg_speed_kmh: float = 30.0,
) -> float:
    km = haversine_km(unit_lat, unit_lon, incident_lat, incident_lon)
    speed = max(avg_speed_kmh, 5.0)
    return round((km / speed) * 60.0, 2)
