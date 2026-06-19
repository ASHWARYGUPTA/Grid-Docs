import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.models import IngestRejectRow, NormalizedEventRow
from grid_unlocked.ingestion.schemas import NormalizedEvent


def _flags_to_str(flags: list[str]) -> str | None:
    if not flags:
        return None
    return json.dumps(flags)


def _flags_from_str(raw: str | None) -> list[str]:
    if not raw:
        return []
    return json.loads(raw)


def row_to_schema(row: NormalizedEventRow) -> NormalizedEvent:
    return NormalizedEvent(
        event_id=row.event_id,
        source=row.source,
        event_type=row.event_type,
        is_planned=row.is_planned,
        event_cause=row.event_cause,
        status=row.status,
        authenticated=row.authenticated,
        latitude=row.latitude,
        longitude=row.longitude,
        address=row.address,
        corridor=row.corridor,
        zone=row.zone,
        junction=row.junction,
        police_station=row.police_station,
        priority=row.priority,
        requires_road_closure=row.requires_road_closure,
        start_datetime=row.start_datetime,
        end_datetime=row.end_datetime,
        created_date=row.created_date,
        closed_datetime=row.closed_datetime,
        reporting_lag_minutes=row.reporting_lag_minutes,
        description=row.description,
        veh_type=row.veh_type,
        anomaly_flags=_flags_from_str(row.anomaly_flags),
        ingested_at=row.ingested_at,
        updated_at=row.updated_at,
    )


def schema_to_row(event: NormalizedEvent) -> NormalizedEventRow:
    return NormalizedEventRow(
        event_id=event.event_id,
        source=event.source.value if hasattr(event.source, "value") else str(event.source),
        event_type=event.event_type,
        is_planned=event.is_planned,
        event_cause=event.event_cause,
        status=event.status,
        authenticated=event.authenticated,
        latitude=event.latitude,
        longitude=event.longitude,
        address=event.address,
        corridor=event.corridor,
        zone=event.zone,
        junction=event.junction,
        police_station=event.police_station,
        priority=event.priority,
        requires_road_closure=event.requires_road_closure,
        start_datetime=event.start_datetime,
        end_datetime=event.end_datetime,
        created_date=event.created_date,
        closed_datetime=event.closed_datetime,
        reporting_lag_minutes=event.reporting_lag_minutes,
        description=event.description,
        veh_type=event.veh_type,
        anomaly_flags=_flags_to_str(event.anomaly_flags),
        ingested_at=event.ingested_at or datetime.now(UTC),
        updated_at=event.updated_at or datetime.now(UTC),
    )


class IngestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_event(self, event: NormalizedEvent) -> tuple[NormalizedEvent, bool]:
        existing = await self.session.get(NormalizedEventRow, event.event_id)
        was_closed = existing is not None and existing.status != "closed" and event.status == "closed"

        if existing:
            row = schema_to_row(event)
            for column in NormalizedEventRow.__table__.columns:
                name = column.name
                if name in {"ingested_at"}:
                    continue
                setattr(existing, name, getattr(row, name))
            existing.updated_at = datetime.now(UTC)
            await self.session.commit()
            await self.session.refresh(existing)
            return row_to_schema(existing), was_closed

        row = schema_to_row(event)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row_to_schema(row), event.status == "closed"

    async def get_event(self, event_id: str) -> NormalizedEvent | None:
        row = await self.session.get(NormalizedEventRow, event_id)
        return row_to_schema(row) if row else None

    async def record_reject(
        self, source: str, reason: str, raw_payload: str, event_id: str | None = None
    ) -> None:
        self.session.add(
            IngestRejectRow(
                source=source,
                event_id=event_id,
                reason=reason,
                raw_payload=raw_payload,
            )
        )
        await self.session.commit()

    async def health_stats(self) -> dict:
        total_events = await self.session.scalar(select(func.count()).select_from(NormalizedEventRow)) or 0
        total_rejects = await self.session.scalar(select(func.count()).select_from(IngestRejectRow)) or 0
        active_events = (
            await self.session.scalar(
                select(func.count()).select_from(NormalizedEventRow).where(NormalizedEventRow.status == "active")
            )
            or 0
        )
        last_ingested = await self.session.scalar(select(func.max(NormalizedEventRow.ingested_at)))

        lags = (
            await self.session.scalars(
                select(NormalizedEventRow.reporting_lag_minutes)
                .where(NormalizedEventRow.reporting_lag_minutes.is_not(None))
                .order_by(NormalizedEventRow.reporting_lag_minutes)
            )
        ).all()
        lag_p95 = None
        if lags:
            idx = min(len(lags) - 1, int(len(lags) * 0.95))
            lag_p95 = lags[idx]

        attempts = total_events + total_rejects
        error_rate = (total_rejects / attempts * 100.0) if attempts else 0.0

        return {
            "total_events": total_events,
            "total_rejects": total_rejects,
            "active_events": active_events,
            "last_ingested_at": last_ingested,
            "error_rate_pct": round(error_rate, 2),
            "reporting_lag_p95_minutes": lag_p95,
        }
