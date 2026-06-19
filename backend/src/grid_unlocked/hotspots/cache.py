import json
import time
from datetime import UTC, datetime

from grid_unlocked.config import settings
from grid_unlocked.hotspots.schemas import ObservedHotspotsResponse, PredictedHotspotsResponse
from grid_unlocked.redis_client import get_redis

_memory: dict[str, tuple[float, str]] = {}


class HotspotCache:
    async def get_observed(self) -> ObservedHotspotsResponse | None:
        raw = await self._read("hotspots:observed")
        if not raw:
            return None
        return ObservedHotspotsResponse.model_validate_json(raw)

    async def set_observed(self, response: ObservedHotspotsResponse) -> None:
        await self._write(
            "hotspots:observed",
            response.model_dump_json(),
            settings.hotspot_observed_cache_ttl,
        )

    async def get_predicted(self, horizon: int) -> PredictedHotspotsResponse | None:
        raw = await self._read(f"hotspots:predicted:{horizon}")
        if not raw:
            return None
        return PredictedHotspotsResponse.model_validate_json(raw)

    async def set_predicted(self, horizon: int, response: PredictedHotspotsResponse) -> None:
        await self._write(
            f"hotspots:predicted:{horizon}",
            response.model_dump_json(),
            settings.hotspot_forecast_cache_ttl,
        )

    async def _read(self, key: str) -> str | None:
        entry = _memory.get(key)
        if entry:
            expires, value = entry
            if time.time() < expires:
                return value
            _memory.pop(key, None)

        try:
            client = await get_redis()
            value = await client.get(key)
            if value:
                return value
        except Exception:
            pass
        return None

    async def _write(self, key: str, value: str, ttl: int) -> None:
        _memory[key] = (time.time() + ttl, value)
        try:
            client = await get_redis()
            await client.set(key, value, ex=ttl)
        except Exception:
            pass


hotspot_cache = HotspotCache()
