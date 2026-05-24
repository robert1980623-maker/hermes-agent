"""
Tests for HotReloadManager — WebSocket-based dynamic tool registry updates.

Uses unittest.mock to simulate WebSocket server responses.
All tests are async (pytest-asyncio).
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import WSMsgType

from src.hot_reload_manager import (
    HotReloadManager,
    BlueprintValidationError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_blueprint(version: str, tools: dict) -> dict:
    """Build a minimal valid blueprint dict."""
    return {
        "type": "blueprint_update",
        "version": version,
        "timestamp": time.time(),
        "blueprint": {
            "tools": tools,
        },
    }


def make_tool(name: str, description: str = "", parameters: dict | None = None) -> dict:
    """Build a minimal tool definition."""
    return {
        "name": name,
        "description": description or f"Tool {name}",
        "parameters": parameters or {"type": "object", "properties": {}},
    }


def make_ws_msg(**kwargs):
    """Create a mock WS message with the given attributes."""
    msg = MagicMock()
    for k, v in kwargs.items():
        setattr(msg, k, v)
    return msg


def make_ws_cm(ws_mock):
    """Wrap a mock WS response in an async context manager."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=ws_mock)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def make_session_with_ws(ws_mock):
    """Create a mock aiohttp session whose ws_connect returns *ws_mock* wrapped."""
    session = AsyncMock()
    ws_cm = make_ws_cm(ws_mock)
    session.ws_connect = MagicMock(return_value=ws_cm)
    return session


def setup_ws_iterator(ws_mock, messages):
    """Set up ws_mock to iterate over *messages* via async-for."""
    async def fake_aiter(_self=None):
        for m in messages:
            yield m
    ws_mock.__aiter__ = fake_aiter
    # Also make ws.closed work
    ws_mock.closed = False
    ws_mock.close_code = None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ws_mock():
    """Return a mock WebSocket connection."""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def manager(ws_mock):
    """Return a HotReloadManager with its _ws pre-set to the mock."""
    mgr = HotReloadManager(ws_url="ws://localhost:9000/blueprints")
    mgr._ws = ws_mock
    return mgr


# ---------------------------------------------------------------------------
# Test 1 — WebSocket connection and message reception
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connection_and_message_reception():
    """Manager connects, receives a blueprint_update, and applies it."""
    messages = [
        make_ws_msg(type=WSMsgType.TEXT,
                     data=json.dumps(make_blueprint("v1", {
                         "search": make_tool("search"),
                     }))),
        make_ws_msg(type=WSMsgType.CLOSED),
    ]

    ws = AsyncMock()
    setup_ws_iterator(ws, messages)
    ws.send = AsyncMock()
    ws.close = AsyncMock()

    session = make_session_with_ws(ws)

    with patch("src.hot_reload_manager.aiohttp.ClientSession") as MockSession:
        MockSession.return_value.__aenter__ = AsyncMock(return_value=session)
        MockSession.return_value.__aexit__ = AsyncMock(return_value=None)

        mgr = HotReloadManager(
            ws_url="ws://localhost:9000/blueprints",
            reconnect_base_delay=0.01,
        )

        task = asyncio.create_task(mgr.start())
        await asyncio.sleep(0.15)
        await mgr.stop()
        await task

        assert "search" in mgr.get_registered_tools()
        assert mgr.current_version == "v1"


# ---------------------------------------------------------------------------
# Test 2 — Blueprint update adds new tools to registry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_blueprint_adds_new_tools(manager):
    """Applying a blueprint_update registers new tools."""
    blueprint = make_blueprint("v2", {
        "weather": make_tool("weather", "Get weather"),
        "calendar": make_tool("calendar", "Get calendar"),
    })

    await manager._handle_blueprint_update(blueprint)

    tools = manager.get_registered_tools()
    assert "weather" in tools
    assert "calendar" in tools
    assert tools["weather"]["description"] == "Get weather"
    assert manager.current_version == "v2"


# ---------------------------------------------------------------------------
# Test 3 — Blueprint update removes old tools from registry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_blueprint_removes_old_tools(manager):
    """Tools not in the new blueprint are unregistered."""
    manager._registry = {
        "old_tool": make_tool("old_tool"),
        "keep_tool": make_tool("keep_tool"),
    }

    blueprint = make_blueprint("v3", {
        "keep_tool": make_tool("keep_tool"),
        "new_tool": make_tool("new_tool"),
    })

    await manager._handle_blueprint_update(blueprint)

    tools = manager.get_registered_tools()
    assert "old_tool" not in tools
    assert "keep_tool" in tools
    assert "new_tool" in tools


# ---------------------------------------------------------------------------
# Test 4 — Invalid blueprint rejected (no partial updates)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_blueprint_rejected_no_partial_update(manager):
    """If the blueprint is malformed, the registry must NOT change."""
    manager._registry = {
        "existing": make_tool("existing"),
    }

    bad_blueprint = {
        "type": "blueprint_update",
        "version": "v_bad",
        "timestamp": time.time(),
        "blueprint": {"no_tools_key": True},
    }

    with pytest.raises(BlueprintValidationError):
        await manager._handle_blueprint_update(bad_blueprint)

    assert "existing" in manager.get_registered_tools()
    assert len(manager.get_registered_tools()) == 1


@pytest.mark.asyncio
async def test_non_json_message_rejected():
    """A message that is not valid JSON is rejected during processing."""
    mgr = HotReloadManager(ws_url="ws://localhost:9000/blueprints")

    with pytest.raises(json.JSONDecodeError):
        await mgr._process_message("not json at all {{{")

    assert len(mgr.get_registered_tools()) == 0


@pytest.mark.asyncio
async def test_wrong_message_type_ignored(manager):
    """_process_message silently ignores non-blueprint_update types."""
    manager._registry = {"existing": make_tool("existing")}

    other_msg = json.dumps({"type": "heartbeat", "data": "ping"})
    await manager._process_message(other_msg)

    assert "existing" in manager.get_registered_tools()
    assert manager.current_version is None


# ---------------------------------------------------------------------------
# Test 5 — Auto-reconnect after disconnection (exponential backoff)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_reconnect_with_exponential_backoff():
    """After a connection error, the manager retries with increasing delay."""
    connect_calls = []

    def make_ws_with_close():
        ws = AsyncMock()
        setup_ws_iterator(ws, [make_ws_msg(type=WSMsgType.CLOSED)])
        return ws

    def make_ws_connect(*_args, **_kwargs):
        connect_calls.append(time.monotonic())
        if len(connect_calls) < 3:
            raise ConnectionError("server down")
        ws = make_ws_with_close()
        return make_ws_cm(ws)

    session = AsyncMock()
    session.ws_connect = MagicMock(side_effect=make_ws_connect)

    with patch("src.hot_reload_manager.aiohttp.ClientSession") as MockSession:
        MockSession.return_value.__aenter__ = AsyncMock(return_value=session)
        MockSession.return_value.__aexit__ = AsyncMock(return_value=None)

        mgr = HotReloadManager(
            ws_url="ws://localhost:9000/blueprints",
            reconnect_base_delay=0.01,
            reconnect_max_delay=0.1,
        )
        task = asyncio.create_task(mgr.start())
        await asyncio.sleep(0.5)
        await mgr.stop()
        await task

        assert len(connect_calls) >= 3

        delay_1 = connect_calls[1] - connect_calls[0]
        delay_2 = connect_calls[2] - connect_calls[1]
        assert delay_2 >= delay_1


# ---------------------------------------------------------------------------
# Test 6 — Version tracking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_version_tracking(manager):
    """current_version and last_updated are tracked correctly."""
    assert manager.current_version is None
    assert manager.last_updated is None

    blueprint = make_blueprint("v5", {
        "tool_a": make_tool("tool_a"),
    })
    await manager._handle_blueprint_update(blueprint)

    assert manager.current_version == "v5"
    assert manager.last_updated is not None

    blueprint2 = make_blueprint("v6", {
        "tool_a": make_tool("tool_a"),
        "tool_b": make_tool("tool_b"),
    })
    await manager._handle_blueprint_update(blueprint2)

    assert manager.current_version == "v6"


# ---------------------------------------------------------------------------
# Test 7 — Session change notification callbacks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_session_notification_on_change(manager):
    """Registered callbacks are called when the blueprint changes."""
    notified_changes = []

    async def on_change(changes):
        notified_changes.append(changes)

    manager.register_change_callback(on_change)

    blueprint = make_blueprint("v1", {
        "alpha": make_tool("alpha"),
        "beta": make_tool("beta"),
    })
    await manager._handle_blueprint_update(blueprint)

    assert len(notified_changes) == 1
    changes = notified_changes[0]
    assert "alpha" in changes["added"]
    assert "beta" in changes["added"]


@pytest.mark.asyncio
async def test_session_notification_on_removal(manager):
    """Callbacks report removed tools correctly."""
    manager._registry = {
        "to_remove": make_tool("to_remove"),
        "to_keep": make_tool("to_keep"),
    }
    notified_changes = []

    async def on_change(changes):
        notified_changes.append(changes)

    manager.register_change_callback(on_change)

    blueprint = make_blueprint("v2", {
        "to_keep": make_tool("to_keep"),
        "new_one": make_tool("new_one"),
    })
    await manager._handle_blueprint_update(blueprint)

    assert len(notified_changes) == 1
    changes = notified_changes[0]
    assert "to_remove" in changes["removed"]
    assert "new_one" in changes["added"]


# ---------------------------------------------------------------------------
# Test 8 — Blueprint validation edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_blueprint_missing_version_rejected(manager):
    """Blueprint without version field is rejected."""
    bad = {
        "type": "blueprint_update",
        "timestamp": time.time(),
        "blueprint": {"tools": {}},
    }
    with pytest.raises(BlueprintValidationError):
        await manager._handle_blueprint_update(bad)


@pytest.mark.asyncio
async def test_blueprint_tools_not_dict_rejected(manager):
    """If tools is not a dict, reject."""
    bad = {
        "type": "blueprint_update",
        "version": "vX",
        "timestamp": time.time(),
        "blueprint": {"tools": ["not", "a", "dict"]},
    }
    with pytest.raises(BlueprintValidationError):
        await manager._handle_blueprint_update(bad)


@pytest.mark.asyncio
async def test_blueprint_missing_timestamp_rejected(manager):
    """Blueprint without timestamp is rejected."""
    bad = {
        "type": "blueprint_update",
        "version": "vX",
        "blueprint": {"tools": {"x": make_tool("x")}},
    }
    with pytest.raises(BlueprintValidationError):
        await manager._handle_blueprint_update(bad)
