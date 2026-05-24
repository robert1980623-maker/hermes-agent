"""Tests for the `af gateway` CLI command — JSONL streaming output."""

import asyncio
import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project src is importable
PROJECT_ROOT = Path(__file__).parent.parent / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_input():
    """Standard input payload for the gateway command."""
    return {
        "task_id": "task-123",
        "user_id": "U123",
        "channel_id": "C123",
        "text": "Hello, world!",
    }


def _parse_jsonl(text: str) -> list[dict]:
    """Parse JSONL text into a list of dicts."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


@pytest.mark.asyncio
async def test_gateway_jsonl_emits_start_progress_done(sample_input):
    """Verify the gateway command emits the expected JSONL event sequence."""

    # Capture stdout
    captured_stdout = StringIO()

    # Build a fake args namespace
    class Args:
        provider = "openai"
        model = "gpt-4o"
        base_url = None
        api_key = None
        log_level = "WARNING"

    # Create a mock supervisor that returns a known result
    mock_supervisor = AsyncMock()
    mock_supervisor.initialize = AsyncMock()
    mock_supervisor.process = AsyncMock(return_value="Processed: Hello, world!")
    mock_supervisor.shutdown = AsyncMock()

    with patch("agentfactory.cli.SupervisorAgent", return_value=mock_supervisor), \
         patch("agentfactory.cli.sys.stdin", StringIO(json.dumps(sample_input))), \
         patch("agentfactory.cli.sys.stdout", captured_stdout), \
         patch("agentfactory.cli.time.monotonic", side_effect=[0.0, 0.042]):

        from agentfactory.cli import _run_gateway
        await _run_gateway(Args())

    events = _parse_jsonl(captured_stdout.getvalue())

    # Should have at least: start, progress(30), progress(90), done
    assert len(events) == 4

    # Check start event
    assert events[0]["event"] == "start"
    assert events[0]["task_id"] == "task-123"
    assert events[0]["data"]["input"] == "Hello, world!"

    # Check first progress event
    assert events[1]["event"] == "progress"
    assert events[1]["task_id"] == "task-123"
    assert events[1]["data"]["progress"] == 30
    assert events[1]["data"]["msg"] == "Thinking..."
    assert "meta" in events[1]["data"]

    # Check second progress event
    assert events[2]["event"] == "progress"
    assert events[2]["task_id"] == "task-123"
    assert events[2]["data"]["progress"] == 90
    assert events[2]["data"]["msg"] == "Finalizing..."

    # Check done event
    assert events[3]["event"] == "done"
    assert events[3]["task_id"] == "task-123"
    assert events[3]["data"]["output"] == "Processed: Hello, world!"
    assert "code_snippet" in events[3]["data"]


@pytest.mark.asyncio
async def test_gateway_jsonl_invalid_input():
    """Verify the gateway command handles invalid JSON input gracefully."""

    captured_stdout = StringIO()

    class Args:
        provider = "openai"
        model = "gpt-4o"
        base_url = None
        api_key = None
        log_level = "WARNING"

    with patch("agentfactory.cli.sys.stdin", StringIO("not json")), \
         patch("agentfactory.cli.sys.stdout", captured_stdout):

        from agentfactory.cli import _run_gateway

        with pytest.raises(SystemExit):
            await _run_gateway(Args())

    events = _parse_jsonl(captured_stdout.getvalue())
    assert len(events) == 1
    assert events[0]["event"] == "error"
    assert "Invalid JSON" in events[0]["data"]["error"]


@pytest.mark.asyncio
async def test_gateway_jsonl_supervisor_error(sample_input):
    """Verify the gateway command handles supervisor errors gracefully."""

    captured_stdout = StringIO()

    class Args:
        provider = "openai"
        model = "gpt-4o"
        base_url = None
        api_key = None
        log_level = "WARNING"

    mock_supervisor = AsyncMock()
    mock_supervisor.initialize = AsyncMock()
    mock_supervisor.process = AsyncMock(side_effect=RuntimeError("LLM connection failed"))
    mock_supervisor.shutdown = AsyncMock()

    with patch("agentfactory.cli.SupervisorAgent", return_value=mock_supervisor), \
         patch("agentfactory.cli.sys.stdin", StringIO(json.dumps(sample_input))), \
         patch("agentfactory.cli.sys.stdout", captured_stdout), \
         patch("agentfactory.cli.time.monotonic", side_effect=[0.0, 0.042]):

        from agentfactory.cli import _run_gateway

        with pytest.raises(SystemExit):
            await _run_gateway(Args())

    events = _parse_jsonl(captured_stdout.getvalue())
    # start + progress(30) + error
    assert len(events) == 3
    assert events[0]["event"] == "start"
    assert events[1]["event"] == "progress"
    assert events[2]["event"] == "error"
    assert "LLM connection failed" in events[2]["data"]["error"]
    # shutdown should still be called
    mock_supervisor.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_gateway_jsonl_uses_correct_process_params(sample_input):
    """Verify the supervisor.process is called with the right parameters."""

    captured_stdout = StringIO()

    class Args:
        provider = "openai"
        model = "gpt-4o"
        base_url = None
        api_key = None
        log_level = "WARNING"

    mock_supervisor = AsyncMock()
    mock_supervisor.initialize = AsyncMock()
    mock_supervisor.process = AsyncMock(return_value="OK")
    mock_supervisor.shutdown = AsyncMock()

    with patch("agentfactory.cli.SupervisorAgent", return_value=mock_supervisor), \
         patch("agentfactory.cli.sys.stdin", StringIO(json.dumps(sample_input))), \
         patch("agentfactory.cli.sys.stdout", captured_stdout), \
         patch("agentfactory.cli.time.monotonic", side_effect=[0.0, 0.042]):

        from agentfactory.cli import _run_gateway
        await _run_gateway(Args())

    mock_supervisor.process.assert_awaited_once_with(
        user_id="U123",
        channel_id="C123",
        text="Hello, world!",
        adapter_id="cli",
    )


@pytest.mark.asyncio
async def test_gateway_jsonl_supervisor_initialized_and_shutdown(sample_input):
    """Verify the supervisor lifecycle (initialize → process → shutdown)."""

    captured_stdout = StringIO()

    class Args:
        provider = "openai"
        model = "gpt-4o"
        base_url = None
        api_key = None
        log_level = "WARNING"

    mock_supervisor = AsyncMock()
    mock_supervisor.initialize = AsyncMock()
    mock_supervisor.process = AsyncMock(return_value="OK")
    mock_supervisor.shutdown = AsyncMock()

    with patch("agentfactory.cli.SupervisorAgent", return_value=mock_supervisor), \
         patch("agentfactory.cli.sys.stdin", StringIO(json.dumps(sample_input))), \
         patch("agentfactory.cli.sys.stdout", captured_stdout), \
         patch("agentfactory.cli.time.monotonic", side_effect=[0.0, 0.042]):

        from agentfactory.cli import _run_gateway
        await _run_gateway(Args())

    mock_supervisor.initialize.assert_awaited_once()
    mock_supervisor.shutdown.assert_awaited_once()


def test_gateway_cli_parser_exists():
    """Verify the 'gateway' subcommand is registered in the CLI parser."""
    from agentfactory.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["gateway"])
    assert args.command == "gateway"
    assert args.provider == "openai"
    assert args.model == "gpt-4o"


def test_serve_command_still_works():
    """Verify existing 'serve' command is not broken."""
    from agentfactory.cli import build_parser

    parser = build_parser()
    args = parser.parse_args([
        "serve",
        "--host", "127.0.0.1",
        "--port", "9000",
        "--provider", "anthropic",
        "--model", "claude-sonnet-4-20250514",
    ])
    assert args.command == "serve"
    assert args.host == "127.0.0.1"
    assert args.port == 9000
    assert args.provider == "anthropic"
    assert args.model == "claude-sonnet-4-20250514"
