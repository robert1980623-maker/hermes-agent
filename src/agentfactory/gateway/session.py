"""Session management for the AgentFactory Gateway.

Maintains mappings between platform-specific identifiers (user_id + channel_id)
and internal task IDs, enabling conversation tracking across messages.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionContext:
    """Tracks a single conversation session between a user and the gateway.

    Attributes:
        session_id: Unique internal session identifier.
        platform: The adapter/platform that created this session (e.g. "slack").
        user_id: Platform-specific user identifier.
        channel_id: Platform-specific channel/conversation identifier.
        created_at: Unix timestamp when the session was created.
        last_active: Unix timestamp of the last message in this session.
        message_count: Number of messages exchanged in this session.
        metadata: Arbitrary platform-specific metadata.
    """

    session_id: str
    platform: str
    user_id: str
    channel_id: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    message_count: int = 0
    metadata: dict = field(default_factory=dict)

    def touch(self) -> None:
        """Update last_active timestamp and increment message count."""
        self.last_active = time.time()
        self.message_count += 1


class SessionManager:
    """Manages sessions across all adapters.

    Provides methods to create, retrieve, and clean up sessions.
    Sessions are keyed by (platform, user_id, channel_id) tuples.
    """

    def __init__(self, ttl_seconds: int = 3600) -> None:
        """Initialize the session manager.

        Args:
            ttl_seconds: Time-to-live for sessions in seconds.
                         Sessions older than this are considered stale.
        """
        self._sessions: dict[str, SessionContext] = {}
        self._ttl_seconds = ttl_seconds

    def _make_key(self, platform: str, user_id: str, channel_id: str) -> str:
        """Create a unique session key from platform, user, and channel."""
        return f"{platform}:{user_id}:{channel_id}"

    def get_or_create(
        self,
        platform: str,
        user_id: str,
        channel_id: str,
    ) -> SessionContext:
        """Get existing session or create a new one.

        Args:
            platform: The adapter/platform ID.
            user_id: Platform-specific user identifier.
            channel_id: Platform-specific channel identifier.

        Returns:
            The existing or newly created SessionContext.
        """
        key = self._make_key(platform, user_id, channel_id)

        if key in self._sessions:
            session = self._sessions[key]
            session.touch()
            return session

        session = SessionContext(
            session_id=str(uuid.uuid4()),
            platform=platform,
            user_id=user_id,
            channel_id=channel_id,
        )
        self._sessions[key] = session
        logger.info(
            "Created new session: id=%s platform=%s user=%s channel=%s",
            session.session_id,
            platform,
            user_id,
            channel_id,
        )
        return session

    def get(self, platform: str, user_id: str, channel_id: str) -> Optional[SessionContext]:
        """Retrieve a session by its identifiers, or None if not found."""
        key = self._make_key(platform, user_id, channel_id)
        return self._sessions.get(key)

    def remove(self, platform: str, user_id: str, channel_id: str) -> bool:
        """Remove a session. Returns True if it existed."""
        key = self._make_key(platform, user_id, channel_id)
        if key in self._sessions:
            del self._sessions[key]
            return True
        return False

    def cleanup_expired(self) -> int:
        """Remove sessions that have exceeded their TTL.

        Returns:
            Number of sessions removed.
        """
        now = time.time()
        expired_keys = [
            key
            for key, session in self._sessions.items()
            if now - session.last_active > self._ttl_seconds
        ]
        for key in expired_keys:
            del self._sessions[key]
        if expired_keys:
            logger.info("Cleaned up %d expired sessions.", len(expired_keys))
        return len(expired_keys)

    @property
    def active_count(self) -> int:
        """Number of currently active sessions."""
        return len(self._sessions)

    def get_all(self) -> list[SessionContext]:
        """Return a list of all active sessions."""
        return list(self._sessions.values())
