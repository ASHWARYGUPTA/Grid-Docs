from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.models import (
    CorridorCentroidRow,
    ImpactScoreRow,
    NormalizedEventRow,
)
from grid_unlocked.maps.schemas import (
    ActiveIncident,
    ActiveIncidentsResponse,
    CorridorCentroid,
    CorridorsResponse,
)


class MapsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def active_incidents(self, *, limit: int = 100) -> ActiveIncidentsResponse:
        # Latest impact score per event_id (max scored_at)
        latest_scored = (
            select(
                ImpactScoreRow.event_id.label("event_id"),
                func.max(ImpactScoreRow.scored_at).label("latest_scored_at"),
            )
            .group_by(ImpactScoreRow.event_id)
            .subquery()
        )

        stmt = (
            select(
                NormalizedEventRow,
                ImpactScoreRow.rci,
                ImpactScoreRow.p_closure,
                ImpactScoreRow.severity_band,
            )
            .where(NormalizedEventRow.status == "active")
            .outerjoin(
                latest_scored,
                latest_scored.c.event_id == NormalizedEventRow.event_id,
            )
            .outerjoin(
                ImpactScoreRow,
                (ImpactScoreRow.event_id == latest_scored.c.event_id)
                & (ImpactScoreRow.scored_at == latest_scored.c.latest_scored_at),
            )
            .order_by(desc(NormalizedEventRow.ingested_at))
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        incidents = [
            ActiveIncident(
                event_id=event.event_id,
                corridor=event.corridor,
                junction=event.junction,
                event_type=event.event_type,
                event_cause=event.event_cause,
                lat=event.latitude,
                lng=event.longitude,
                rci=rci,
                p_closure=p_closure,
                severity_band=severity_band,
                status=event.status,
                ingested_at=event.ingested_at,
            )
            for (event, rci, p_closure, severity_band) in rows
        ]
        return ActiveIncidentsResponse(incidents=incidents)

    async def corridors(self) -> CorridorsResponse:
        result = await self.session.execute(
            select(CorridorCentroidRow).order_by(CorridorCentroidRow.corridor)
        )
        rows = result.scalars().all()
        corridors = [
            CorridorCentroid(
                name=r.corridor,
                lat=r.lat,
                lon=r.lon,
                sample_count=r.sample_count,
            )
            for r in rows
        ]
        return CorridorsResponse(corridors=corridors)
