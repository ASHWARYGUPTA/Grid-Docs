"""Tier 3 static BTP black spots."""

from grid_unlocked.hotspots.schemas import HotspotCluster, HotspotLayer

BTP_BLACKSPOTS: list[dict] = [
    {
        "label": "Bellandur Flyover",
        "lat": 12.969,
        "lon": 77.701,
        "historical_count": 65,
        "corridor": "ORR East 1",
        "h3": "872830828ffffff",
    },
    {
        "label": "Hebbal Flyover",
        "lat": 13.035,
        "lon": 77.597,
        "historical_count": 48,
        "corridor": "Bellary Road 1",
        "h3": "87283080cffffff",
    },
    {
        "label": "Silk Board Junction",
        "lat": 12.917,
        "lon": 77.622,
        "historical_count": 42,
        "corridor": "Hosur Road",
        "h3": "87283082dffffff",
    },
    {
        "label": "Mysore Road NICE Junction",
        "lat": 12.940,
        "lon": 77.512,
        "historical_count": 38,
        "corridor": "Mysore Road",
        "h3": "872830828ffffff",
    },
    {
        "label": "KR Puram Bridge",
        "lat": 13.004,
        "lon": 77.695,
        "historical_count": 35,
        "corridor": "Old Madras Road",
        "h3": "87283080dffffff",
    },
]


def static_blackspot_clusters() -> list[HotspotCluster]:
    clusters: list[HotspotCluster] = []
    for i, spot in enumerate(BTP_BLACKSPOTS):
        clusters.append(
            HotspotCluster(
                cluster_id=f"static-{i}",
                layer=HotspotLayer.OBSERVED,
                centroid_lat=spot["lat"],
                centroid_lon=spot["lon"],
                density=spot["historical_count"],
                cause_entropy=0.0,
                h3_cells=[spot["h3"]],
                corridors=[spot["corridor"]],
                persistence_score=1.0,
                label=spot["label"],
            )
        )
    return clusters
