import json
import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grid_unlocked.db.models import (
    CausePriorRow,
    CorridorCausePriorRow,
    FeatureSnapshotRow,
    HourBiasWeightRow,
    NormalizedEventRow,
)
from grid_unlocked.features.constants import (
    DEFAULT_PRIOR_CLOSURE_RATE,
    DEFAULT_PRIOR_ICT_H,
    DEFAULT_VEH_COMPLEXITY,
    VEH_COMPLEXITY_BASE,
)
from grid_unlocked.features.schemas import CorridorCausePrior, FeatureVector


class FeatureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_event_row(self, event_id: str) -> NormalizedEventRow | None:
        return await self.session.get(NormalizedEventRow, event_id)

    async def get_bias_weight(self, hour_ist: int) -> float:
        row = await self.session.get(HourBiasWeightRow, hour_ist)
        return row.bias_weight if row else 1.0

    async def get_corridor_cause_prior(
        self, corridor: str | None, cause: str
    ) -> tuple[float, float, int, bool]:
        corridor_key = corridor or "Non-corridor"
        row = await self.session.get(CorridorCausePriorRow, (corridor_key, cause))
        if row and row.sample_count >= 5:
            return row.closure_rate, row.median_ict_h, row.sample_count, False

        cause_row = await self.session.get(CausePriorRow, cause)
        if cause_row:
            return (
                cause_row.global_closure_rate,
                cause_row.global_median_ict_h,
                cause_row.sample_count,
                True,
            )
        return DEFAULT_PRIOR_CLOSURE_RATE, DEFAULT_PRIOR_ICT_H, 0, True

    async def get_cause_global_median(self, cause: str) -> float:
        row = await self.session.get(CausePriorRow, cause)
        return row.global_median_ict_h if row else DEFAULT_PRIOR_ICT_H

    async def get_corridor_cause_prior_api(
        self, corridor: str, cause: str
    ) -> CorridorCausePrior | None:
        row = await self.session.get(CorridorCausePriorRow, (corridor, cause))
        if not row:
            return None
        return CorridorCausePrior(
            corridor=row.corridor,
            cause=row.cause,
            closure_rate=row.closure_rate,
            median_ict_h=row.median_ict_h,
            sample_count=row.sample_count,
        )

    async def count_active_within_km(
        self, lat: float, lon: float, exclude_event_id: str, radius_km: float = 2.0
    ) -> int:
        delta_lat = radius_km / 111.0
        cos_lat = max(math.cos(math.radians(lat)), 0.01)
        delta_lon = radius_km / (111.0 * cos_lat)

        rows = (
            await self.session.scalars(
                select(NormalizedEventRow).where(
                    NormalizedEventRow.status == "active",
                    NormalizedEventRow.event_id != exclude_event_id,
                    NormalizedEventRow.latitude.between(lat - delta_lat, lat + delta_lat),
                    NormalizedEventRow.longitude.between(lon - delta_lon, lon + delta_lon),
                )
            )
        ).all()

        count = 0
        for row in rows:
            if _haversine_km(lat, lon, row.latitude, row.longitude) <= radius_km:
                count += 1
        return count

    async def save_snapshot(self, features: FeatureVector) -> None:
        row = await self.session.get(FeatureSnapshotRow, features.event_id)
        payload = features.model_dump(mode="json")
        payload.pop("cache_hit", None)
        json_payload = json.dumps(payload)
        if row:
            row.feature_json = json_payload
        else:
            self.session.add(
                FeatureSnapshotRow(event_id=features.event_id, feature_json=json_payload)
            )
        await self.session.commit()

    async def get_snapshot(self, event_id: str) -> FeatureVector | None:
        row = await self.session.get(FeatureSnapshotRow, event_id)
        if not row:
            return None
        data = json.loads(row.feature_json)
        return FeatureVector.model_validate(data)


def veh_complexity_score(veh_type: str | None) -> float:
    if not veh_type:
        return DEFAULT_VEH_COMPLEXITY
    key = veh_type.strip().lower()
    return VEH_COMPLEXITY_BASE.get(key, DEFAULT_VEH_COMPLEXITY)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
