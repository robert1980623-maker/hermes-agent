"""
Message Throttler

Batches and throttles Slack update events to prevent excessive API calls.
Workers push events into the throttler, which coalesces rapid updates
and flushes them at controlled intervals.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MessageThrottler:
    """
    Throttles and batches Slack update events.

    Instead of sending every progress update immediately, the throttler
    collects events and flushes them either when the batch interval
    elapses or when the batch reaches a maximum size.

    Usage:
        throttler = MessageThrottler(on_flush=dispatch_processor.handle_event)
        throttler.start()
        throttler.push(event)  # queues event for batched delivery
        throttler.stop()       # flushes remaining events
    """

    def __init__(
        self,
        on_flush: Callable[[Any], Any],
        batch_interval: float = 0.5,
        max_batch_size: int = 10,
    ):
        """
        Args:
            on_flush: Callback invoked with each flushed event.
            batch_interval: Seconds to wait before flushing a batch.
            max_batch_size: Maximum number of events to accumulate before flush.
        """
        self._on_flush = on_flush
        self._batch_interval = batch_interval
        self._max_batch_size = max_batch_size

        # Per-task pending events. Latest event per (task_id, subtask_id) wins.
        self._pending: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._last_flush: float = time.monotonic()
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None

    @property
    def pending_count(self) -> int:
        """Total number of unique (task, subtask) pairs pending flush."""
        return sum(len(v) for v in self._pending.values())

    def push(self, event: Any) -> None:
        """
        Queue an event for throttled delivery.

        Events for the same (task_id, subtask_id) are coalesced — only the
        latest update is kept. This prevents sending stale progress data.
        """
        task_id = getattr(event, "task_id", "")
        subtask_id = getattr(event, "subtask_id", "") or getattr(event, "agent_id", "")
        key = subtask_id or "global"

        self._pending[task_id][key] = event
        self._last_flush = time.monotonic()

    async def _flush_loop(self) -> None:
        """Background loop that flushes pending events at the batch interval."""
        while self._running:
            await asyncio.sleep(self._batch_interval)
            await self.flush()

    async def flush(self) -> None:
        """Flush all pending events through the on_flush callback."""
        if not self._pending:
            return

        # Snapshot and clear pending
        snapshot = dict(self._pending)
        self._pending.clear()

        for task_id, events in snapshot.items():
            for key, event in events.items():
                try:
                    self._on_flush(event)
                except Exception:
                    logger.exception(
                        "[throttler] Error flushing event for task=%s key=%s",
                        task_id,
                        key,
                    )

        self._last_flush = time.monotonic()

    def start(self) -> None:
        """Start the background flush loop."""
        if self._running:
            return
        self._running = True
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._task = loop.create_task(self._flush_loop())
        except RuntimeError:
            # No running event loop — caller must flush manually
            logger.debug(
                "[throttler] No running event loop; flush must be called manually"
            )

    def stop(self) -> None:
        """Stop the background loop and flush any remaining events."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

        # Synchronous flush for any remaining events
        # (used when no async loop is available)
        if self._pending:
            snapshot = dict(self._pending)
            self._pending.clear()
            for task_id, events in snapshot.items():
                for key, event in events.items():
                    try:
                        self._on_flush(event)
                    except Exception:
                        logger.exception(
                            "[throttler] Error flushing event on stop for task=%s key=%s",
                            task_id,
                            key,
                        )
