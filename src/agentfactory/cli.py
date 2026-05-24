"""CLI entry point for the AgentFactory Gateway.

Usage:
    af serve                          # Start gateway with defaults
    af serve --host 0.0.0.0 --port 8000
    af serve --slack-token xoxb-... --slack-app-token xapp-...
    af serve --provider openai --model gpt-4o
    af gateway                        # Run a single task via stdin/stdout (JSONL)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
import uvicorn

from agentfactory.gateway import GatewayApp, ProviderConfig
from agentfactory.gateway.adapters.slack import SlackAdapter
from agentfactory.gateway.core import SupervisorAgent


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the af CLI."""
    parser = argparse.ArgumentParser(
        prog="af",
        description="AgentFactory Gateway Service CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── af serve ────────────────────────────────────────────────
    serve_parser = subparsers.add_parser("serve", help="Start the gateway service")
    serve_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)",
    )
    serve_parser.add_argument(
        "--slack-token",
        default=None,
        help="Slack Bot User OAuth Token (xoxb-...). Falls back to SLACK_BOT_TOKEN env var.",
    )
    serve_parser.add_argument(
        "--slack-app-token",
        default=None,
        help="Slack App-Level Token (xapp-...). Falls back to SLACK_APP_TOKEN env var.",
    )
    serve_parser.add_argument(
        "--provider",
        default="openai",
        help="LLM provider name (default: openai)",
    )
    serve_parser.add_argument(
        "--model",
        default="gpt-4o",
        help="LLM model identifier (default: gpt-4o)",
    )
    serve_parser.add_argument(
        "--base-url",
        default=None,
        help="Custom API base URL for the provider.",
    )
    serve_parser.add_argument(
        "--api-key",
        default=None,
        help="API key for the provider. Falls back to provider-specific env vars.",
    )
    serve_parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    # ── af gateway ──────────────────────────────────────────────
    gateway_parser = subparsers.add_parser(
        "gateway",
        help="Run a single task via stdin/stdout (JSONL streaming)",
    )
    gateway_parser.add_argument(
        "--provider",
        default="openai",
        help="LLM provider name (default: openai)",
    )
    gateway_parser.add_argument(
        "--model",
        default="gpt-4o",
        help="LLM model identifier (default: gpt-4o)",
    )
    gateway_parser.add_argument(
        "--base-url",
        default=None,
        help="Custom API base URL for the provider.",
    )
    gateway_parser.add_argument(
        "--api-key",
        default=None,
        help="API key for the provider. Falls back to provider-specific env vars.",
    )
    gateway_parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: WARNING)",
    )

    return parser


async def _run_gateway(args: argparse.Namespace) -> None:
    """Execute the 'af gateway' command — reads one JSON from stdin,
    processes it through the SupervisorAgent, and emits JSONL events
    to stdout."""

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,  # Logs to stderr so they don't corrupt JSONL stdout
    )

    def emit(event: str, task_id: str, data: dict) -> None:
        """Write a single JSONL line to stdout and flush."""
        line = json.dumps({"event": event, "task_id": task_id, "data": data})
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

    # Read and parse input from stdin
    raw_input = sys.stdin.read()
    try:
        input_data = json.loads(raw_input)
    except json.JSONDecodeError as e:
        emit("error", "unknown", {"error": f"Invalid JSON input: {e}"})
        sys.exit(1)

    task_id = input_data.get("task_id", "unknown")
    user_id = input_data.get("user_id", "anonymous")
    channel_id = input_data.get("channel_id", "default")
    text = input_data.get("text", "")

    # Emit start event
    emit("start", task_id, {"input": text})

    # Build provider config and supervisor
    provider_config = ProviderConfig(
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
    )

    supervisor = SupervisorAgent(provider_config)
    await supervisor.initialize()

    start_time = time.monotonic()

    # Run the supervisor and emit progress + done events.
    # Since SupervisorAgent.run/process is blocking (async but single response),
    # we emit an intermediate progress event and then the done event.
    # For a real streaming implementation, the supervisor would support
    # a callback or async-generator interface.

    emit(
        "progress",
        task_id,
        {
            "progress": 30,
            "msg": "Thinking...",
            "meta": {"tokens": 0, "elapsed_ms": 0},
        },
    )

    try:
        result = await supervisor.process(
            user_id=user_id,
            channel_id=channel_id,
            text=text,
            adapter_id="cli",
        )

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        emit(
            "progress",
            task_id,
            {
                "progress": 90,
                "msg": "Finalizing...",
                "meta": {"tokens": len(result), "elapsed_ms": elapsed_ms},
            },
        )

        # Emit done event
        emit(
            "done",
            task_id,
            {"output": result, "code_snippet": ""},
        )
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        emit(
            "error",
            task_id,
            {"error": str(e), "elapsed_ms": elapsed_ms},
        )
        sys.exit(1)
    finally:
        await supervisor.shutdown()


async def _run_serve(args: argparse.Namespace) -> None:
    """Execute the 'af serve' command."""
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Build provider config
    provider_config = ProviderConfig(
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
    )

    # Create gateway
    gateway = GatewayApp(provider_config=provider_config)

    # Register Slack adapter if tokens are provided
    if args.slack_token or args.slack_app_token:
        slack = SlackAdapter(
            adapter_id="slack",
            bot_token=args.slack_token,
            app_token=args.slack_app_token,
        )
        gateway.register_adapter(slack)
        logging.info("Slack adapter registered.")

    # Get the FastAPI app
    app = gateway.app

    logging.info(
        "Starting AgentFactory Gateway on %s:%d (provider=%s, model=%s)",
        args.host,
        args.port,
        args.provider,
        args.model,
    )
    if "slack" in gateway.adapters:
        logging.info("Slack adapter enabled — listening for mentions via Socket Mode.")

    config = uvicorn.Config(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
    )
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    """Main entry point for the af CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "serve":
        asyncio.run(_run_serve(args))
    elif args.command == "gateway":
        asyncio.run(_run_gateway(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
