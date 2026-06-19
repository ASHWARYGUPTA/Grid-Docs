"""M11 — Mock VMS Webhook Client.

Simulates the VMS board vendor webhook for the hackathon phase.
Returns realistic ACK payloads with configurable failure rates.

DEFERRED D-M11-01: Replace with real HTTP POST to VMS board vendor endpoints
in Phase 1.5. Interface (post_to_board) stays the same.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from dataclasses import dataclass


@dataclass
class WebhookResponse:
    status_code: int
    body: dict
    latency_ms: float


class MockWebhookClient:
    """
    Hackathon mock — simulates VMS board vendor webhook receiver.
    Configurable failure rate for testing retry/DLQ logic.
    """

    def __init__(self, failure_rate: float = 0.0) -> None:
        self._failure_rate = failure_rate

    async def post_to_board(
        self,
        board_id: str,
        board_name: str,
        endpoint: str,
        board_text: str,
        push_id: str,
        event_id: str,
    ) -> WebhookResponse:
        """POST board text to a VMS endpoint. Simulated 30–100 ms latency."""
        latency = random.uniform(30, 100)
        await asyncio.sleep(latency / 1000)

        if random.random() < self._failure_rate:
            return WebhookResponse(
                status_code=503,
                body={
                    "error": "VMS board endpoint unavailable",
                    "board_id": board_id,
                },
                latency_ms=latency,
            )

        ack_id = f"VMSACK-{board_id}-{uuid.uuid4().hex[:6].upper()}"
        return WebhookResponse(
            status_code=200,
            body={
                "ack_id": ack_id,
                "board_id": board_id,
                "board_name": board_name,
                "status": "displayed",
                "push_id": push_id,
                "event_id": event_id,
                "message": f"Board {board_name} updated successfully",
            },
            latency_ms=latency,
        )
