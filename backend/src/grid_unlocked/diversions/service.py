"""Diversion routing orchestration."""

from __future__ import annotations

import time

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.config import settings
from grid_unlocked.diversions.atlas import (
    JUNCTION_REGISTRY,
    get_atlas,
    primary_junction_for_corridor,
    routes_for_corridor,
    _build_routes,
)
from grid_unlocked.diversions.gridlock import detect_gridlock
from grid_unlocked.diversions.schemas import (
    AtlasEntry,
    ComputeRequest,
    ScenarioResponse,
    ValidateRequest,
    ValidateResult,
)
from grid_unlocked.citizen.repository import CitizenRepository
from grid_unlocked.diversions.schemas import DiversionRoute, RouteWaypoint
from grid_unlocked.features.graph_stub import corridor_to_node_id, parse_node_id
from grid_unlocked.features.service import FeatureService
from grid_unlocked.impact.registry import registry
from grid_unlocked.planned.schemas import DiversionRef


class DiversionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.features = FeatureService(session)
        self.citizen_repo = CitizenRepository(session)

    async def _centroid_map(self) -> dict[str, tuple[float, float]]:
        centroids = await self.citizen_repo.get_all_centroids()
        return {name: (lat, lon) for (name, lat, lon) in centroids}

    @staticmethod
    def _resolve_waypoints(
        path: list[str], centroid_map: dict[str, tuple[float, float]]
    ) -> list[RouteWaypoint]:
        """Map proxy node ids -> corridor centroids. Unresolved nodes are
        skipped (never fabricated)."""
        out: list[RouteWaypoint] = []
        for node_id in path:
            corridor = parse_node_id(node_id)
            if corridor is None:
                continue
            point = centroid_map.get(corridor)
            if point is None:
                continue
            lat, lon = point
            out.append(RouteWaypoint(lat=lat, lng=lon, corridor=corridor))
        return out

    def _enrich_routes(
        self,
        routes: list[DiversionRoute],
        centroid_map: dict[str, tuple[float, float]],
    ) -> list[DiversionRoute]:
        return [
            r.model_copy(update={"waypoints": self._resolve_waypoints(r.path, centroid_map)})
            for r in routes
        ]

    async def get_atlas(self, junction_id: str) -> AtlasEntry:
        entry = get_atlas(junction_id)
        if not entry:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"No atlas entry for junction {junction_id}",
            )
        centroid_map = await self._centroid_map()
        return entry.model_copy(update={"routes": self._enrich_routes(entry.routes, centroid_map)})

    async def compute(self, request: ComputeRequest) -> AtlasEntry:
        t0 = time.perf_counter()
        junction_id = request.junction_id
        corridor = request.corridor

        if junction_id and junction_id in JUNCTION_REGISTRY:
            meta = JUNCTION_REGISTRY[junction_id]
            corridor = meta["corridor"]
        elif corridor:
            junction_id = primary_junction_for_corridor(corridor)
            meta = JUNCTION_REGISTRY.get(junction_id, {})
        else:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Provide junction_id or corridor",
            )

        closed = request.closed_node_id or corridor_to_node_id(corridor or "Non-corridor")
        routes = _build_routes(
            junction_id or "junction:computed",
            corridor or parse_node_id(closed) or "Non-corridor",
            meta.get("description", "Computed diversion"),
            meta.get("summary", "On-demand k-shortest path"),
            k=request.k,
        )

        centroid_map = await self._centroid_map()
        return AtlasEntry(
            junction_id=junction_id or "junction:computed",
            source_corridor=corridor or "Non-corridor",
            closed_node_id=closed,
            routes=self._enrich_routes(routes, centroid_map),
            cached=False,
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
        )

    def validate(self, request: ValidateRequest) -> ValidateResult:
        return detect_gridlock(request.path, closed_node_id=request.closed_node_id)

    async def scenarios(self, event_id: str) -> ScenarioResponse:
        t0 = time.perf_counter()
        row = await self.features.repo.get_event_row(event_id)
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Event {event_id} not found")

        features = await self.features.get_features(event_id)
        p_closure = 0.35
        is_peak = False
        if features:
            scored = registry.score(
                features,
                is_planned=row.is_planned,
                event_cause=row.event_cause,
                corridor=row.corridor,
            )
            p_closure = scored.p_closure
            is_peak = features.is_peak_hour

        junction_id = primary_junction_for_corridor(row.corridor)
        routes = routes_for_corridor(row.corridor, k=settings.diversion_k_default)
        auto_suggest = p_closure > settings.closure_alert_threshold and is_peak

        centroid_map = await self._centroid_map()
        return ScenarioResponse(
            event_id=event_id,
            corridor=row.corridor,
            junction_id=junction_id,
            p_closure=p_closure,
            is_peak_hour=is_peak,
            auto_suggest=auto_suggest,
            routes=self._enrich_routes(routes, centroid_map),
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
        )

    @staticmethod
    def refs_for_corridor(corridor: str | None, *, limit: int = 3) -> list[DiversionRef]:
        """M06-compatible diversion refs from atlas."""
        routes = routes_for_corridor(corridor, k=limit)
        return [
            DiversionRef(
                junction_id=r.junction_id,
                description=r.description,
                route_summary=r.route_summary,
                rank=r.rank,
            )
            for r in routes
        ]

    @staticmethod
    def list_junctions() -> list[str]:
        from grid_unlocked.diversions.atlas import list_atlas_junction_ids

        return list_atlas_junction_ids()
