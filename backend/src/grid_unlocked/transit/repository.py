"""M12 — TransitImpactRepository.

Handles reads/writes for the transit_impact_cache table. TTL is checked
at read-time (no cleanup job), same pattern as other caches in this
codebase.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.models import TransitImpactCacheRow


class TransitImpactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_cached(self, event_id: str) -> str | None:
        row = await self.session.get(TransitImpactCacheRow, event_id)
        if row is None:
            return None
        # SQLite round-trips datetimes as naive even when stored tz-aware;
        # compare against a same-awareness "now" rather than assume tzinfo.
        now = datetime.now(UTC)
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            now = now.replace(tzinfo=None)
        if expires_at < now:
            return None
        return row.payload_json

    async def save_cache(self, event_id: str, payload_json: str, ttl_minutes: int) -> None:
        expires_at = datetime.now(UTC) + timedelta(minutes=ttl_minutes)
        row = await self.session.get(TransitImpactCacheRow, event_id)
        if row is None:
            row = TransitImpactCacheRow(
                event_id=event_id, payload_json=payload_json, expires_at=expires_at
            )
            self.session.add(row)
        else:
            row.payload_json = payload_json
            row.expires_at = expires_at
        await self.session.commit()
