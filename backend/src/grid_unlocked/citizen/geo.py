from grid_unlocked.hotspots.geo import haversine_km


def nearest_corridor(
    lat: float, lon: float, centroids: list[tuple[str, float, float]]
) -> str | None:
    """centroids: list of (corridor, lat, lon). Returns nearest corridor by haversine distance."""
    if not centroids:
        return None
    best_corridor, _ = min(
        ((corridor, haversine_km(lat, lon, clat, clon)) for corridor, clat, clon in centroids),
        key=lambda pair: pair[1],
    )
    return best_corridor
