"""
HotReloadManager — WebSocket-based dynamic tool registry.

Connects to a Portal Server WebSocket endpoint, receives blueprint_update
messages, diffs them against the current tool registry, and registers /
unregisters tools without requiring a daemon restart.

Features:
  • Configurable WebSocket URL
  • Blueprint validation before applying (no partial updates)
  • Exponential-backoff auto-reconnect
  • Async-safe (asyncio.Lock)
  • Change-notification callbacks for active sessions
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Coroutine, Dict, Optional

import aiohttp
from aiohttp import WSMsgType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class BlueprintValidationError(ValueError):
    """Raised when a received blueprint fails schema validation."""
    pass


# ---------------------------------------------------------------------------
# HotReloadManager
# ---------------------------------------------------------------------------

class HotReloadManager:
    """Manages dynamic tool registration via WebSocket blueprint updates."""

    def __init__(
        self,
        ws_url: str,
        reconnect_base_delay: float = 1.0,
        reconnect_max_delay: float = 60.0,
    ):
        self._ws_url = ws_url
        self._reconnect_base_delay = reconnect_base_delay
        self._reconnect_max_delay = reconnect_max_delay

        # Internal state (protected by _lock)
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._current_version: Optional[str] = None
        self._last_updated: Optional[float] = None
        self._lock = asyncio.Lock()

        # Change-notification callbacks
        self._callbacks: list[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = []

        # Runtime handles
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._session: aiohttp.ClientSession | None = None
        self._running = False
        self._stop_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def current_version(self) -> Optional[str]:
        """The blueprint version currently applied to the registry."""
        return self._current_version

    @property
    def last_updated(self) -> Optional[float]:
        """Unix timestamp of the last successful blueprint update."""
        return self._last_updated

    def get_registered_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return a copy of the current tool registry."""
        return dict(self._registry)

    def register_change_callback(
        self,
        callback: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Register an async callback to be called on every blueprint change.

        Callback receives a dict with keys: ``added``, ``removed``, ``version``.
        """
        self._callbacks.append(callback)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Connect to the WebSocket and enter the receive loop.

        Automatically reconnects on failure with exponential backoff.
        Call :meth:`stop` to shut down gracefully.
        """
        self._running = True
        self._stop_event.clear()
        attempt = 0

        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    self._session = session
                    async with session.ws_connect(
                        self._ws_url,
                        heartbeat=30,
                    ) as ws:
                        self._ws = ws
                        attempt = 0  # reset backoff on successful connect
                        logger.info("HotReloadManager connected to %s", self._ws_url)
                        await self._receive_loop()
            except (aiohttp.ClientError, ConnectionError, OSError) as exc:
                if not self._running:
                    break
                attempt += 1
                delay = min(
                    self._reconnect_base_delay * (2 ** (attempt - 1)),
                    self._reconnect_max_delay,
                )
                logger.warning(
                    "HotReloadManager connection error (%s), retrying in %.1fs (attempt %d)",
                    exc, delay, attempt,
                )
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass  # retry
            except asyncio.CancelledError:
                break
            finally:
                self._ws = None
                self._session = None

        logger.info("HotReloadManager stopped")

    async def stop(self) -> None:
        """Signal the manager to stop and close the WebSocket."""
        self._running = False
        self._stop_event.set()
        if self._ws and not self._ws.closed:
            await self._ws.close()

    # ------------------------------------------------------------------
    # Receive loop
    # ------------------------------------------------------------------

    async def _receive_loop(self) -> None:
        """Read messages from the WebSocket and dispatch them."""
        assert self._ws is not None
        async for msg in self._ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await self._process_message(msg.data)
                except json.JSONDecodeError as exc:
                    logger.error("HotReloadManager received invalid JSON: %s", exc)
                except BlueprintValidationError as exc:
                    logger.error("HotReloadManager blueprint validation failed: %s", exc)
                except Exception:
                    logger.exception("HotReloadManager error processing message")
            elif msg.type in (WSMsgType.CLOSED, WSMsgType.ERROR):
                logger.warning(
                    "HotReloadManager WebSocket %s (code=%s)",
                    "closed" if msg.type == WSMsgType.CLOSED else "error",
                    getattr(self._ws, "close_code", None),
                )
                break

    async def _process_message(self, raw: str) -> None:
        """Parse a raw WebSocket message and apply if it's a blueprint_update."""
        data = json.loads(raw)  # May re-raise JSONDecodeError if caller bypasses receive_loop
        if data.get("type") != "blueprint_update":
            logger.debug("HotReloadManager ignoring message type=%s", data.get("type"))
            return
        await self._handle_blueprint_update(data)

    # ------------------------------------------------------------------
    # Blueprint handling
    # ------------------------------------------------------------------

    async def _handle_blueprint_update(self, data: Dict[str, Any]) -> None:
        """Validate and apply a blueprint_update message."""
        self._validate_blueprint(data)

        new_tools: Dict[str, Dict[str, Any]] = data["blueprint"]["tools"]
        version: str = data["version"]

        async with self._lock:
            # Compute diff
            old_names = set(self._registry.keys())
            new_names = set(new_tools.keys())
            added = new_names - old_names
            removed = old_names - new_names

            # Apply atomically — replace entire registry
            self._registry = dict(new_tools)
            self._current_version = version
            self._last_updated = time.time()

        changes = {
            "added": sorted(added),
            "removed": sorted(removed),
            "version": version,
        }

        if added or removed:
            logger.info(
                "HotReloadManager applied blueprint %s: +%d tools, -%d tools",
                version, len(added), len(removed),
            )
            await self._notify_callbacks(changes)

    def _validate_blueprint(self, data: Dict[str, Any]) -> None:
        """Raise :class:`BlueprintValidationError` if *data* is not a valid blueprint."""
        if not isinstance(data, dict):
            raise BlueprintValidationError("Blueprint must be a JSON object")
        if data.get("type") != "blueprint_update":
            # Not a blueprint_update — caller should skip, but we still validate if called directly
            if "type" in data:
                raise BlueprintValidationError(
                    f"Expected type 'blueprint_update', got '{data['type']}'"
                )
            raise BlueprintValidationError("Missing required field 'type'")
        if "version" not in data:
            raise BlueprintValidationError("Missing required field 'version'")
        if "timestamp" not in data:
            raise BlueprintValidationError("Missing required field 'timestamp'")
        if "blueprint" not in data or not isinstance(data.get("blueprint"), dict):
            raise BlueprintValidationError("Missing or invalid 'blueprint' object")
        blueprint = data["blueprint"]
        if "tools" not in blueprint:
            raise BlueprintValidationError("Blueprint missing required 'tools' field")
        if not isinstance(blueprint["tools"], dict):
            raise BlueprintValidationError("Blueprint 'tools' must be a dict mapping name -> definition")

    # ------------------------------------------------------------------
    # Callback dispatch
    # ------------------------------------------------------------------

    async def _notify_callbacks(self, changes: Dict[str, Any]) -> None:
        """Invoke all registered change-notification callbacks."""
        for cb in self._callbacks:
            try:
                await cb(changes)
            except Exception:
                logger.exception("HotReloadManager callback %r raised", cb)
