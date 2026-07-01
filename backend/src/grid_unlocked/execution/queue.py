"""M10 — CommandQueue.

Async fire-and-forget command queue with background worker.

Architecture:
  - asyncio.Queue is the transport (in-process, non-durable).
  - Durability / restart-safety: D-M10-03 (Phase 1.5 → Redis Streams).
  - Worker pulls commands and calls ExecutionService._process_command().
  - Queue is a singleton started on app lifespan; stopped on shutdown.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Coroutine, Any

logger = logging.getLogger(__name__)


@dataclass
class QueuedCommand:
    execution_id: str
    approval_token: str
    card_id: str
    event_id: str
    command_type: str  # "dispatch" | "barricade"
    station_id: str | None
    barricade_count: int
    recommendation_id: str | None


# Module-level sentinel
_STOP = object()


class CommandQueue:
    """
    Singleton async queue + background worker.

    Usage:
        queue = CommandQueue(processor_fn)
        await queue.start()
        await queue.enqueue(cmd)
        await queue.stop()
    """

    def __init__(
        self,
        processor: Callable[[QueuedCommand], Coroutine[Any, Any, None]],
        maxsize: int = 256,
    ) -> None:
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._processor = processor
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._worker(), name="m10-command-worker")
            logger.info("M10 CommandQueue worker started")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            await self._queue.put(_STOP)
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
            logger.info("M10 CommandQueue worker stopped")

    async def enqueue(self, cmd: QueuedCommand) -> None:
        """Non-blocking enqueue — caller gets control back immediately."""
        await self._queue.put(cmd)
        logger.debug("Enqueued command %s (type=%s)", cmd.execution_id, cmd.command_type)

    async def _worker(self) -> None:
        while True:
            item = await self._queue.get()
            if item is _STOP:
                self._queue.task_done()
                break
            try:
                await self._processor(item)
            except Exception:
                logger.exception("Unhandled error processing command %s", item.execution_id)
            finally:
                self._queue.task_done()


# ---------------------------------------------------------------------------
# Module-level singleton — initialised in ExecutionService.setup()
# ---------------------------------------------------------------------------
_command_queue: CommandQueue | None = None


def get_command_queue() -> CommandQueue:
    if _command_queue is None:
        raise RuntimeError("CommandQueue not initialised — call setup_command_queue() at startup")
    return _command_queue


def set_command_queue(q: CommandQueue) -> None:
    global _command_queue
    _command_queue = q
