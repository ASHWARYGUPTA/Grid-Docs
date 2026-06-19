import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.ingestion.bus import event_bus
from grid_unlocked.ingestion.normalizer import normalize_payload, payload_to_json
from grid_unlocked.ingestion.repository import IngestRepository
from grid_unlocked.ingestion.schemas import (
    EventClosedMessage,
    EventNormalizedMessage,
    IngestAck,
    IngestHealth,
    IngestSource,
    NormalizedEvent,
)
from grid_unlocked.ingestion.validator import IngestValidationError


class IngestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = IngestRepository(session)

    async def ingest(
        self, payload: dict[str, Any], source: IngestSource
    ) -> IngestAck | tuple[None, str]:
        started = time.perf_counter()
        raw_json = payload_to_json(payload)
        event_id = str(payload.get("event_id") or payload.get("id") or "")

        try:
            normalized = normalize_payload(payload, source=source)
            stored, became_closed = await self.repo.upsert_event(normalized)

            await event_bus.publish_normalized(
                EventNormalizedMessage(event=stored)
            )

            if became_closed or stored.status == "closed":
                await event_bus.publish_closed(
                    EventClosedMessage(
                        event_id=stored.event_id,
                        closed_datetime=stored.closed_datetime,
                        requires_road_closure=stored.requires_road_closure,
                        status=stored.status,
                        payload=stored.model_dump(mode="json"),
                    )
                )

            latency_ms = (time.perf_counter() - started) * 1000
            return IngestAck(
                event_id=stored.event_id,
                status=stored.status,
                normalized=True,
                anomaly_flags=stored.anomaly_flags,
                latency_ms=round(latency_ms, 2),
            )
        except IngestValidationError as exc:
            await self.repo.record_reject(
                source=source.value,
                reason=exc.reason,
                raw_payload=raw_json,
                event_id=event_id or None,
            )
            return None, exc.reason

    async def get_event(self, event_id: str) -> NormalizedEvent | None:
        return await self.repo.get_event(event_id)

    async def health(self) -> IngestHealth:
        stats = await self.repo.health_stats()
        return IngestHealth(
            status="healthy",
            total_events=stats["total_events"],
            total_rejects=stats["total_rejects"],
            active_events=stats["active_events"],
            last_ingested_at=stats["last_ingested_at"],
            error_rate_pct=stats["error_rate_pct"],
            reporting_lag_p95_minutes=stats["reporting_lag_p95_minutes"],
        )
