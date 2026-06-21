"""M12 — Mock GTFS-RT client.

Stands in for live BMTC GTFS-RT AVL/load-factor feeds. Returns the route's
static default occupancy — there is no real-time load data in the
hackathon MVP.

DEFERRED D-M12-01: Replace with a real GTFS-RT polling client in Phase 2.
The interface (get_occupancy) stays the same — only the backing data
source changes from a static default to a live feed.
"""

from __future__ import annotations

from grid_unlocked.transit.bmtc_registry import DEFAULT_OCCUPANCY, get_route


class MockGtfsClient:
    def get_occupancy(self, route_id: str) -> int:
        route = get_route(route_id)
        return route.avg_occupancy if route else DEFAULT_OCCUPANCY
