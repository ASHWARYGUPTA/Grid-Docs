import json

from grid_unlocked.features.constants import FEATURE_CACHE_TTL_SECONDS
from grid_unlocked.propagation.schemas import PropagationMap
from grid_unlocked.redis_client import get_redis

_memory_maps: dict[str, str] = {}
_active_events: set[str] = set()


class PropagationCache:
    async def get(self, event_id: str) -> PropagationMap | None:
        raw = await self._read(f"propagation:{event_id}")
        if not raw:
            return None
        return PropagationMap.model_validate_json(raw)

    async def set(self, propagation: PropagationMap) -> None:
        key = f"propagation:{propagation.event_id}"
        payload = propagation.model_dump_json()
        await self._write(key, payload, FEATURE_CACHE_TTL_SECONDS)
        _active_events.add(propagation.event_id)

    async def list_active(self) -> list[PropagationMap]:
        results: list[PropagationMap] = []
        for event_id in sorted(_active_events):
            pmap = await self.get(event_id)
            if pmap:
                results.append(pmap)
        return results

    async def delete(self, event_id: str) -> None:
        key = f"propagation:{event_id}"
        try:
            client = await get_redis()
            await client.delete(key)
        except Exception:
            pass
        _memory_maps.pop(key, None)
        _active_events.discard(event_id)

    async def _read(self, key: str) -> str | None:
        try:
            client = await get_redis()
            value = await client.get(key)
            if value:
                return value
        except Exception:
            pass
        return _memory_maps.get(key)

    async def _write(self, key: str, value: str, ttl: int) -> None:
        try:
            client = await get_redis()
            await client.set(key, value, ex=ttl)
            return
        except Exception:
            pass
        _memory_maps[key] = value


propagation_cache = PropagationCache()
