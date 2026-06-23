"""Stream A — seed ~20 realistic events into a running Grid Unlocked backend.

Usage:
    uv run python scripts/seed_demo.py
    # or to point at a non-default host:
    GRID_API_URL=http://localhost:8000 uv run python scripts/seed_demo.py

All payloads use the canonical M01 vocab (lowercase status, snake_case causes)
so the ingest API returns 200. Coordinates stay inside the Bengaluru bbox
lat [12.8, 13.3], lon [77.3, 77.8]. start_datetime is within the last ~2 h.
"""

from __future__ import annotations

import math
import os
import random
import sys
from datetime import UTC, datetime, timedelta

import httpx

API_URL = os.environ.get("GRID_API_URL", "http://localhost:8000")
INGEST_PATH = "/ingest/astram"

CORRIDORS: list[tuple[str, float, float]] = [
    ("Mysore Road", 12.957, 77.503),
    ("Bellary Road 1", 13.097, 77.594),
    ("Tumkur Road", 13.025, 77.520),
]

CAUSES: list[str] = [
    "accident",
    "vip_movement",
    "public_event",
    "procession",
    "construction",
    "vehicle_breakdown",
]

PRIORITIES: list[str] = ["High", "Medium", "Low"]
EVENT_TYPES: list[str] = ["planned", "unplanned"]


def _jitter(lat: float, lon: float, *, radius_deg: float = 0.012) -> tuple[float, float]:
    """Move a centroid by up to ~1 km in a random direction, clipped to bbox."""
    angle = random.uniform(0, 2 * math.pi)
    r = random.uniform(0, radius_deg)
    nlat = lat + r * math.cos(angle)
    nlon = lon + r * math.sin(angle)
    nlat = max(12.81, min(13.29, nlat))
    nlon = max(77.31, min(77.79, nlon))
    return round(nlat, 5), round(nlon, 5)


def _payload(idx: int, now: datetime) -> dict:
    corridor, c_lat, c_lon = random.choice(CORRIDORS)
    lat, lon = _jitter(c_lat, c_lon)
    cause = random.choice(CAUSES)
    event_type = "planned" if cause in {"vip_movement", "public_event", "procession", "construction"} else random.choice(EVENT_TYPES)
    start = now - timedelta(minutes=random.randint(1, 115))
    return {
        "id": f"SEED{now.strftime('%Y%m%d')}{idx:03d}",
        "event_type": event_type,
        "latitude": lat,
        "longitude": lon,
        "event_cause": cause,
        "requires_road_closure": cause in {"vip_movement", "procession", "accident"},
        "start_datetime": start.isoformat(),
        "status": "active",
        "authenticated": "yes",
        "created_date": start.isoformat(),
        "corridor": corridor,
        "priority": random.choice(PRIORITIES),
        "veh_type": "heavy_vehicle" if cause == "vehicle_breakdown" else None,
    }


def main(count: int = 20, seed: int | None = 42) -> int:
    if seed is not None:
        random.seed(seed)
    now = datetime.now(UTC)
    url = API_URL.rstrip("/") + INGEST_PATH

    ok = 0
    rejected: list[tuple[str, int, str]] = []

    with httpx.Client(timeout=10.0) as client:
        for i in range(1, count + 1):
            payload = _payload(i, now)
            try:
                resp = client.post(url, json=payload)
            except httpx.HTTPError as exc:
                rejected.append((payload["id"], -1, str(exc)))
                continue
            if resp.status_code == 200:
                ok += 1
            else:
                rejected.append((payload["id"], resp.status_code, resp.text[:160]))

    print(f"seed_demo: {ok}/{count} ingested into {url}")
    for event_id, code, detail in rejected:
        print(f"  REJECTED {event_id} ({code}): {detail}")
    return 0 if ok == count else 1


if __name__ == "__main__":
    sys.exit(main())
