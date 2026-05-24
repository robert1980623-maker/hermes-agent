"""Abstract base class for Gateway Adapters.

Every platform adapter (Slack, Feishu, Discord, etc.) inherits from this
class and implements the platform-specific connection, event handling,
and reply logic.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

# A reply callback receives the final response text and optionally
# metadata (e.g. attachments, thread info).
ReplyFn = Callable[[str, Optional[dict[str, Any]]], Awaitable[None]]


class BaseAdapter(ABC):
    """Base class for all messaging platform adapters.

    Adapters are responsible for:
    - Connecting to the platform (via HTTP, WebSocket, Socket Mode, etc.)
    - Listening for incoming messages / events
    - Translating platform events into standard Task dicts
    - Dispatching tasks to the Gateway's SupervisorAgent
    - Posting replies back to the correct conversation thread
    """

    def __init__(self, adapter_id: str) -> None:
        self.adapter_id = adapter_id
        self._running = False
        self._reply_fn: Optional[ReplyFn] = None

    @property
    def is_running(self) -> bool:
        return self._running

    def set_reply_fn(self, fn: ReplyFn) -> None:
        """Register the callback used to send replies back to the platform.

        The Gateway sets this during adapter registration so the adapter
        can dispatch tasks and get replies.
        """
        self._reply_fn = fn

    async def reply(self, reply_data: str, metadata: Optional[dict[str, Any]] = None) -> None:
        """Send a reply via the registered reply callback.

        Args:
            reply_data: The response text to send.
            metadata: Optional platform-specific metadata (thread info, etc.)
        """
        if self._reply_fn is None:
            logger.warning(
                "[%s] No reply function registered — dropping reply: %s",
                self.adapter_id,
                reply_data[:100],
            )
            return
        await self._reply_fn(reply_data, metadata)

    @abstractmethod
    async def start(self) -> None:
        """Start the adapter and begin listening for events.

        Must be idempotent — calling start() on an already-running adapter
        should be a no-op.
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the adapter and release all resources.

        Must be idempotent — calling stop() on a stopped adapter should
        be a no-op.
        """
        ...

    @abstractmethod
    async def on_message(
        self,
        user_id: str,
        channel_id: str,
        text: str,
        callback_url: Optional[str] = None,
    ) -> None:
        """Handle an incoming message from the platform.

        This is called by the platform-specific event handler (e.g. Bolt
        listener for Slack) after the message has been parsed.

        Args:
            user_id: The platform user ID who sent the message.
            channel_id: The platform channel/conversation ID.
            text: The message text content.
            callback_url: Optional callback URL for HTTP-based platforms.
        """
        ...
