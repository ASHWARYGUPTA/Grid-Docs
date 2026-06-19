import json

from grid_unlocked.features.constants import FEATURE_CACHE_TTL_SECONDS
from grid_unlocked.features.schemas import FeatureVector
from grid_unlocked.redis_client import get_redis

_memory_cache: dict[str, str] = {}


class FeatureCache:
    async def get(self, event_id: str) -> FeatureVector | None:
        key = f"feature:{event_id}"
        raw = await self._read(key)
        if not raw:
            return None
        data = json.loads(raw)
        fv = FeatureVector.model_validate(data)
        fv.cache_hit = True
        return fv

    async def set(self, features: FeatureVector) -> None:
        key = f"feature:{features.event_id}"
        payload = features.model_dump(mode="json")
        payload["cache_hit"] = False
        await self._write(key, json.dumps(payload), FEATURE_CACHE_TTL_SECONDS)

    async def delete(self, event_id: str) -> None:
        key = f"feature:{event_id}"
        try:
            client = await get_redis()
            await client.delete(key)
        except Exception:
            pass
        _memory_cache.pop(key, None)

    async def _read(self, key: str) -> str | None:
        try:
            client = await get_redis()
            value = await client.get(key)
            if value:
                return value
        except Exception:
            pass
        return _memory_cache.get(key)

    async def _write(self, key: str, value: str, ttl: int) -> None:
        try:
            client = await get_redis()
            await client.set(key, value, ex=ttl)
            return
        except Exception:
            pass
        _memory_cache[key] = value


feature_cache = FeatureCache()
