"""M10 — MockStationClient.

Simulates the police station dispatch API for the hackathon phase.
Returns realistic payloads with configurable success/failure behaviour.

DEFERRED (D-M10-01): Replace with StationHttpClient in Phase 1.5 — real
HTTP POST to BTP station endpoints with auth headers and cert pinning.
DEFERRED (D-M10-02): Barricade reservation via BTP asset API in Phase 1.5.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from dataclasses import dataclass


@dataclass
class StationResponse:
    status_code: int
    body: dict
    latency_ms: float


# Station roster — mock BTP station registry
# Phase 1.5: load from real station API / DB table
_MOCK_STATIONS = [
    {"id": "HAL", "name": "HAL Airport Road", "zone": "East"},
    {"id": "WHTFLD", "name": "Whitefield", "zone": "East"},
    {"id": "MRVTH", "name": "Marthahalli", "zone": "East"},
    {"id": "KOR", "name": "Koramangala", "zone": "South"},
    {"id": "BTGLK", "name": "Battarahalli", "zone": "East"},
    {"id": "SARJ", "name": "Sarjapur", "zone": "South"},
    {"id": "BSNG", "name": "Basnashankari", "zone": "West"},
]


class MockStationClient:
    """
    Hackathon mock — simulates station dispatch API.
    Configurable failure rate for testing retry/DLQ logic.
    """

    def __init__(self, failure_rate: float = 0.0) -> None:
        """
        Args:
            failure_rate: Fraction [0, 1] of calls that return HTTP 500.
                          Default 0.0 = always succeed (demo mode).
                          Set to ~0.6 in tests to exercise retry path.
        """
        self._failure_rate = failure_rate

    async def dispatch_unit(
        self, station_id: str | None, event_id: str, card_id: str, recommendation_id: str | None
    ) -> StationResponse:
        """Simulate dispatching a unit to an event. ~40–120 ms latency."""
        latency = random.uniform(40, 120)
        await asyncio.sleep(latency / 1000)

        station = self._pick_station(station_id)

        if random.random() < self._failure_rate:
            return StationResponse(
                status_code=500,
                body={"error": "Station API temporarily unavailable", "station_id": station["id"]},
                latency_ms=latency,
            )

        unit_id = f"MOCK-{station['id']}-{uuid.uuid4().hex[:4].upper()}"
        return StationResponse(
            status_code=200,
            body={
                "unit_id": unit_id,
                "station_id": station["id"],
                "station_name": station["name"],
                "event_id": event_id,
                "card_id": card_id,
                "status": "acknowledged",
                "ack_id": f"ACK-{uuid.uuid4().hex[:8].upper()}",
                "eta_minutes": random.randint(5, 20),
                "message": f"Unit {unit_id} dispatched from {station['name']} to event {event_id}",
            },
            latency_ms=latency,
        )

    async def reserve_barricades(
        self, station_id: str | None, event_id: str, barricade_count: int
    ) -> StationResponse:
        """
        Simulate barricade reservation via BTP asset API.

        DEFERRED D-M10-02: Real BTP asset API call in Phase 1.5.
        Currently returns mock reservation IDs.
        """
        latency = random.uniform(20, 60)
        await asyncio.sleep(latency / 1000)

        if barricade_count == 0:
            return StationResponse(
                status_code=200,
                body={"message": "No barricades required", "reservation_ids": []},
                latency_ms=latency,
            )

        station = self._pick_station(station_id)

        if random.random() < self._failure_rate:
            return StationResponse(
                status_code=503,
                body={"error": "Asset inventory unavailable"},
                latency_ms=latency,
            )

        reservation_ids = [f"BAR-{uuid.uuid4().hex[:6].upper()}" for _ in range(barricade_count)]
        return StationResponse(
            status_code=200,
            body={
                "reservation_ids": reservation_ids,
                "station_id": station["id"],
                "barricade_count": barricade_count,
                "event_id": event_id,
                "status": "reserved",
            },
            latency_ms=latency,
        )

    @staticmethod
    def _pick_station(station_id: str | None) -> dict:
        if station_id:
            for s in _MOCK_STATIONS:
                if s["id"] == station_id:
                    return s
        return random.choice(_MOCK_STATIONS)  # noqa: S311

    def with_failure_rate(self, rate: float) -> "MockStationClient":
        """Return a new client with specified failure rate (useful in tests)."""
        return MockStationClient(failure_rate=rate)
