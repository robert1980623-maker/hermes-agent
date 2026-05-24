"""
Stream Worker

Consumes agent event streams and dispatches Slack updates through a
MessageThrottler to avoid excessive API calls.

The worker:
  1. Receives events from an event stream (queue, generator, etc.)
  2. Pushes each event through the MessageThrottler
  3. The throttler coalesces rapid updates and flushes them at controlled
     intervals to the DispatchProcessor
  4. The DispatchProcessor renders Slack Block Kit cards which are sent
     to the Slack API
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Iterator, Optional

from protocol.protocol import EventPayload
from gateway.slack_dispatch import DispatchProcessor
from worker.throttler import MessageThrottler

logger = logging.getLogger(__name__)


class StreamWorker:
    """
    Processes a stream of agent events with throttled Slack updates.

    Usage:
        processor = DispatchProcessor()
        worker = StreamWorker(
            dispatch_processor=processor,
            slack_sender=client.chat_postMessage,
        )
        worker.start()
        for event in event_stream:
            worker.process_event(event)
        worker.stop()
    """

    def __init__(
        self,
        dispatch_processor: DispatchProcessor,
        slack_sender: Any,
        batch_interval: float = 0.5,
        max_batch_size: int = 10,
    ):
        """
        Args:
            dispatch_processor: Processes dispatch events into Slack blocks.
            slack_sender: Callable to send/edit Slack messages.
                         Expected signature: (channel, blocks, text, ts=None)
            batch_interval: Throttle interval in seconds.
            max_batch_size: Max events per batch.
        """
        self._processor = dispatch_processor
        self._slack_sender = slack_sender
        self._throttler = MessageThrottler(
            on_flush=self._handle_flush,
            batch_interval=batch_interval,
            max_batch_size=max_batch_size,
        )

    def start(self) -> None:
        """Start the worker and its throttler."""
        self._throttler.start()
        logger.info("[stream_worker] Worker started")

    def stop(self) -> None:
        """Stop the worker and flush remaining events."""
        self._throttler.stop()
        logger.info("[stream_worker] Worker stopped")

    def process_event(self, event: EventPayload) -> None:
        """
        Queue an event for throttled processing.

        Instead of sending a Slack update immediately, the event is
        pushed to the throttler which will coalesce rapid updates.
        """
        # For start events, send immediately (need message_ts for subsequent edits)
        if event.event_type == "start":
            result = self._processor.handle_event(event)
            if result.get("action") == "send":
                self._send_slack(event, result)
            return

        # For all other events, push through the throttler
        self._throttler.push(event)

    def _handle_flush(self, event: EventPayload) -> None:
        """
        Called by the throttler when it's time to flush events.

        Processes the event through the DispatchProcessor and sends
        the resulting Slack update.
        """
        result = self._processor.handle_event(event)
        if result.get("action") in ("send", "edit"):
            self._send_slack(event, result)
        elif result.get("action") == "noop":
            logger.debug(
                "[stream_worker] Noop event flushed: task_id=%s event_type=%s",
                getattr(event, "task_id", ""),
                getattr(event, "event_type", ""),
            )

    def _send_slack(self, event: EventPayload, result: dict) -> None:
        """Send or edit a Slack message based on the processor result."""
        task_id = event.task_id
        state = self._processor.get_state(task_id)

        try:
            if result["action"] == "send":
                response = self._slack_sender(
                    channel=state.channel_id if state else "",
                    blocks=result["blocks"],
                    text=result["text"],
                )
                # Register the message ts for future edits
                ts = response.get("ts", "")
                channel = response.get("channel", "")
                if ts and state:
                    self._processor.register_message_ts(task_id, ts, channel)
                    logger.info(
                        "[stream_worker] Sent dispatch card: task_id=%s ts=%s",
                        task_id,
                        ts,
                    )

            elif result["action"] == "edit":
                ts = state.message_ts if state else ""
                if ts:
                    self._slack_sender(
                        channel=state.channel_id if state else "",
                        blocks=result["blocks"],
                        text=result["text"],
                        ts=ts,
                    )
                    logger.debug(
                        "[stream_worker] Edited dispatch card: task_id=%s ts=%s",
                        task_id,
                        ts,
                    )
                else:
                    logger.warning(
                        "[stream_worker] Cannot edit: no message_ts for task_id=%s",
                        task_id,
                    )
        except Exception:
            logger.exception(
                "[stream_worker] Failed to send Slack update for task_id=%s",
                task_id,
            )

    async def run_stream(self, event_stream: AsyncIterator[EventPayload]) -> None:
        """
        Process events from an async stream until exhausted.

        Args:
            event_stream: An async iterator yielding EventPayload objects.
        """
        self.start()
        try:
            async for event in event_stream:
                self.process_event(event)
        finally:
            self.stop()

    def run_stream_sync(self, event_stream: Iterator[EventPayload]) -> None:
        """
        Process events from a sync iterator until exhausted.

        Args:
            event_stream: An iterator yielding EventPayload objects.
        """
        self.start()
        try:
            for event in event_stream:
                self.process_event(event)
        finally:
            self.stop()
