"""M12 — TransitImpactService.

passenger_delay_index = Σ_route (avg_occupancy × predicted_delay_minutes × overlap_fraction)

predicted_delay_minutes is M03's ict_p50_h applied as a corridor travel-time
multiplier (ict_p50_h * 60). transfer_overload_risk is an MVP stand-in
(route-count heuristic) — see D-M12-03.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.features.service import FeatureService
from grid_unlocked.impact.service import ImpactService
from grid_unlocked.recommendations.governance import get_governance
from grid_unlocked.transit.bmtc_registry import get_routes_for_corridor
from grid_unlocked.transit.mock_gtfs import MockGtfsClient
from grid_unlocked.transit.repository import TransitImpactRepository
from grid_unlocked.transit.schemas import (
    AffectedRoute,
    AffectedRoutesResponse,
    MockTransitDemoResponse,
    TransitImpactIndex,
)

CACHE_TTL_MINUTES = 15
TRANSFER_OVERLOAD_DIVISOR = 5  # MVP heuristic — see D-M12-03

_MOCK_DEMO_CORRIDOR = "ORR East 1"
_MOCK_DEMO_DELAY_MIN = 35.0


class TransitImpactService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.features = FeatureService(session)
        self.impact = ImpactService(session)
        self.repo = TransitImpactRepository(session)
        self.gtfs = MockGtfsClient()

    async def compute_impact(self, event_id: str) -> TransitImpactIndex:
        t0 = time.perf_counter()
        event_row = await self.features.repo.get_event_row(event_id)
        if not event_row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Event {event_id} not found")

        corridor = event_row.corridor
        gov = get_governance()

        if gov.tier == "3":
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return TransitImpactIndex(
                event_id=event_id,
                corridor=corridor,
                tier=gov.tier,
                degraded=True,
                passenger_delay_index=0.0,
                transfer_overload_risk=0.0,
                affected_routes=[],
                advisory_message=f"BMTC services may be affected near {corridor or 'this location'}.",
                cached=False,
                latency_ms=latency_ms,
                generated_at=datetime.now(UTC),
            )

        cached_json = await self.repo.get_cached(event_id)
        if cached_json is not None:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            result = TransitImpactIndex.model_validate_json(cached_json)
            return result.model_copy(update={"cached": True, "latency_ms": latency_ms})

        impact = await self.impact.score(event_id)
        predicted_delay_min = impact.ict_p50_h * 60

        affected: list[AffectedRoute] = []
        passenger_delay_index = 0.0
        for route, overlap_fraction in get_routes_for_corridor(corridor):
            occupancy = self.gtfs.get_occupancy(route.route_id)
            affected.append(
                AffectedRoute(
                    route_id=route.route_id,
                    name=route.name,
                    occupancy=occupancy,
                    predicted_delay_min=round(predicted_delay_min, 1),
                    overlap_fraction=overlap_fraction,
                )
            )
            passenger_delay_index += occupancy * predicted_delay_min * overlap_fraction

        transfer_overload_risk = min(1.0, len(affected) / TRANSFER_OVERLOAD_DIVISOR)
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        result = TransitImpactIndex(
            event_id=event_id,
            corridor=corridor,
            tier=gov.tier,
            degraded=False,
            passenger_delay_index=round(passenger_delay_index, 1),
            transfer_overload_risk=round(transfer_overload_risk, 2),
            affected_routes=affected,
            cached=False,
            latency_ms=latency_ms,
            generated_at=datetime.now(UTC),
        )
        await self.repo.save_cache(event_id, result.model_dump_json(), CACHE_TTL_MINUTES)
        return result

    def get_affected_routes(self, corridor: str | None) -> AffectedRoutesResponse:
        routes = [
            AffectedRoute(
                route_id=route.route_id,
                name=route.name,
                occupancy=self.gtfs.get_occupancy(route.route_id),
                predicted_delay_min=0.0,
                overlap_fraction=overlap_fraction,
            )
            for route, overlap_fraction in get_routes_for_corridor(corridor)
        ]
        return AffectedRoutesResponse(corridor=corridor, routes=routes)

    def get_mock_demo(self) -> MockTransitDemoResponse:
        routes = [
            AffectedRoute(
                route_id=route.route_id,
                name=route.name,
                occupancy=route.avg_occupancy,
                predicted_delay_min=_MOCK_DEMO_DELAY_MIN,
                overlap_fraction=overlap_fraction,
            )
            for route, overlap_fraction in get_routes_for_corridor(_MOCK_DEMO_CORRIDOR)
        ]
        index = sum(r.occupancy * r.predicted_delay_min * r.overlap_fraction for r in routes)
        passengers = round(index / _MOCK_DEMO_DELAY_MIN) if _MOCK_DEMO_DELAY_MIN else 0
        return MockTransitDemoResponse(
            corridor=_MOCK_DEMO_CORRIDOR,
            passenger_delay_index=round(index, 1),
            affected_routes=routes,
            message=f"~{passengers} passengers delayed on {_MOCK_DEMO_CORRIDOR}",
        )
