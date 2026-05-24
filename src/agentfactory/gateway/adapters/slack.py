"""Slack Adapter using slack-bolt with Socket Mode.

Handles Slack bot mentions in channels, acknowledges immediately,
dispatches tasks to the SupervisorAgent asynchronously, and replies
in the same thread when processing completes.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

from .base import BaseAdapter

logger = logging.getLogger(__name__)


class SlackAdapter(BaseAdapter):
    """Slack platform adapter using Bolt framework + Socket Mode.

    Required environment variables (or constructor args):
        SLACK_BOT_TOKEN: Bot User OAuth Token (xoxb-...)
        SLACK_APP_TOKEN: App-Level Token with connections:write scope (xapp-...)
    """

    def __init__(
        self,
        adapter_id: str = "slack",
        bot_token: Optional[str] = None,
        app_token: Optional[str] = None,
    ) -> None:
        super().__init__(adapter_id)
        self.bot_token = bot_token or os.environ.get("SLACK_BOT_TOKEN", "")
        self.app_token = app_token or os.environ.get("SLACK_APP_TOKEN", "")
        self._app: Any = None
        self._socket_mode: Any = None
        self._supervisor: Any = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _validate_tokens(self) -> None:
        """Validate that required Slack tokens are configured."""
        if not self.bot_token:
            raise ValueError(
                "SLACK_BOT_TOKEN is required. "
                "Set it via --slack-token flag or SLACK_BOT_TOKEN env var."
            )
        if not self.app_token:
            raise ValueError(
                "SLACK_APP_TOKEN is required. "
                "Set it via --slack-app-token flag or SLACK_APP_TOKEN env var."
            )

    def set_supervisor(self, supervisor: Any) -> None:
        """Store a reference to the SupervisorAgent for task dispatch."""
        self._supervisor = supervisor

    async def start(self) -> None:
        """Start the Slack adapter with Socket Mode.

        Initializes the Bolt app, registers event listeners, and connects
        via Socket Mode WebSocket.
        """
        if self._running:
            logger.info("[%s] Already running, skipping start.", self.adapter_id)
            return

        self._validate_tokens()

        # Import bolt lazily so the module loads even without slack-bolt installed.
        from slack_bolt.app import App
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

        self._app = App(token=self.bot_token)

        # Register message listener for bot mentions
        @self._app.event("app_mention")
        async def handle_mention(event: dict, say: Any, client: Any) -> None:
            await self._handle_mention(event=event, say=say, client=client)

        # Start Socket Mode
        self._socket_mode = AsyncSocketModeHandler(self._app, self.app_token)
        self._running = True

        # Run Socket Mode in a background task so it doesn't block the event loop
        self._loop = asyncio.get_event_loop()
        asyncio.create_task(self._socket_mode.start_async())

        logger.info("[%s] Slack adapter started via Socket Mode.", self.adapter_id)

    async def stop(self) -> None:
        """Disconnect from Slack Socket Mode."""
        if not self._running:
            return

        if self._socket_mode is not None:
            try:
                await self._socket_mode.close()
            except Exception:
                logger.exception("[%s] Error closing Socket Mode.", self.adapter_id)

        self._running = False
        logger.info("[%s] Slack adapter stopped.", self.adapter_id)

    async def _handle_mention(self, event: dict, say: Any, client: Any) -> None:
        """Handle a bot mention event from Slack.

        1. Ack immediately with "Received, processing..."
        2. Dispatch the task to SupervisorAgent asynchronously
        3. Reply in the same thread when done
        """
        user_id = event.get("user", "unknown")
        channel_id = event.get("channel", "unknown")
        text = event.get("text", "").strip()
        thread_ts = event.get("thread_ts") or event.get("ts")

        logger.info(
            "[%s] Mention from user=%s channel=%s thread_ts=%s",
            self.adapter_id,
            user_id,
            channel_id,
            thread_ts,
        )

        # Step 1: Immediate acknowledgment
        ack_msg = "Received, processing..."
        try:
            await say(text=ack_msg, thread_ts=thread_ts)
        except Exception:
            logger.exception("[%s] Failed to send acknowledgment.", self.adapter_id)

        # Step 2: Dispatch to SupervisorAgent asynchronously (non-blocking)
        if self._supervisor is None:
            logger.error(
                "[%s] Supervisor not set — cannot process message.",
                self.adapter_id,
            )
            return

        asyncio.create_task(
            self._process_and_reply(
                user_id=user_id,
                channel_id=channel_id,
                text=text,
                thread_ts=thread_ts,
                client=client,
            )
        )

    async def _process_and_reply(
        self,
        user_id: str,
        channel_id: str,
        text: str,
        thread_ts: Optional[str],
        client: Any,
    ) -> None:
        """Run the supervisor processing and reply in the thread.

        This runs as a background task — the Slack handler returns
        immediately after calling this.
        """
        try:
            # Dispatch to SupervisorAgent (async)
            response = await self._supervisor.process(
                user_id=user_id,
                channel_id=channel_id,
                text=text,
                adapter_id=self.adapter_id,
            )

            # Step 3: Reply in the same thread
            await self._send_reply(
                client=client,
                channel_id=channel_id,
                thread_ts=thread_ts,
                text=response,
            )
        except Exception:
            logger.exception("[%s] Error processing message.", self.adapter_id)
            try:
                await self._send_reply(
                    client=client,
                    channel_id=channel_id,
                    thread_ts=thread_ts,
                    text="Sorry, an error occurred while processing your request.",
                )
            except Exception:
                logger.exception("[%s] Failed to send error reply.", self.adapter_id)

    async def _send_reply(
        self,
        client: Any,
        channel_id: str,
        thread_ts: Optional[str],
        text: str,
    ) -> None:
        """Send a reply message in a Slack thread."""
        kwargs: dict[str, Any] = {
            "channel": channel_id,
            "text": text,
        }
        if thread_ts:
            kwargs["thread_ts"] = thread_ts

        await client.chat_postMessage(**kwargs)

    async def on_message(
        self,
        user_id: str,
        channel_id: str,
        text: str,
        callback_url: Optional[str] = None,
    ) -> None:
        """Handle an incoming message (called by Gateway dispatch).

        For Slack Socket Mode, messages come through the Bolt event handler
        rather than this method. This exists for API compatibility with
        the BaseAdapter interface and HTTP-based message injection.
        """
        logger.info(
            "[%s] on_message called — user=%s channel=%s text=%s",
            self.adapter_id,
            user_id,
            channel_id,
            text[:100],
        )

        if self._supervisor is None:
            logger.error("[%s] Supervisor not set.", self.adapter_id)
            return

        try:
            response = await self._supervisor.process(
                user_id=user_id,
                channel_id=channel_id,
                text=text,
                adapter_id=self.adapter_id,
            )
            if self._reply_fn:
                await self._reply_fn(response, {"channel_id": channel_id})
        except Exception:
            logger.exception("[%s] Error in on_message.", self.adapter_id)
