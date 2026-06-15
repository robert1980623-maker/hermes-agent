"""Memorix memory provider plugin for Hermes Agent.

This plugin wraps memorix's Hermes integration to provide local-first
persistent memory with semantic search, automatic turn extraction,
and session handoff capabilities.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class MemorixProvider:
    """Hermes MemoryProvider backed by memorix.

    This is a wrapper around memorix's MemorixMemoryProvider that adapts
    it to Hermes's plugin interface.
    """

    def __init__(self) -> None:
        self._provider: Any = None
        self._config: Dict[str, Any] = {}
        self._hermes_home: str = ""

    @property
    def name(self) -> str:
        """Short identifier for this provider."""
        return "memorix"

    def is_available(self) -> bool:
        """Check if memorix is installed and configured.

        Returns True if:
        - memorix package is importable
        - Either MEMORIX_DB_PATH env var is set OR
          hermes_home/{memorix.yaml, memorix.json} exists
        """
        try:
            import memorix  # noqa: F401
        except ImportError:
            return False

        # Check for config
        if os.environ.get("MEMORIX_DB_PATH"):
            return True

        # Check for config file in hermes_home (YAML preferred, JSON legacy)
        if self._hermes_home:
            for name in ("memorix.yaml", "memorix.yml", "memorix.json"):
                if (Path(self._hermes_home) / name).exists():
                    return True

        # Default to available (will use default config)
        return True

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        """Initialize memorix for this session.

        Args:
            session_id: The session identifier
            **kwargs: Must include hermes_home (str) and platform (str)
        """
        self._hermes_home = kwargs.get("hermes_home", "")

        # Load config from file if exists (YAML preferred, JSON legacy)
        hermes_home = Path(self._hermes_home) if self._hermes_home else None
        if hermes_home is not None:
            for name in ("memorix.yaml", "memorix.yml"):
                config_path = hermes_home / name
                if config_path.exists():
                    try:
                        import yaml
                        self._config = yaml.safe_load(config_path.read_text()) or {}
                    except Exception as e:
                        logger.warning("Failed to load %s: %s", name, e)
                        self._config = {}
                    break
            else:
                config_path = hermes_home / "memorix.json"
                if config_path.exists():
                    try:
                        self._config = json.loads(config_path.read_text())
                    except Exception as e:
                        logger.warning("Failed to load memorix.json: %s", e)
                        self._config = {}

        # Override with env vars
        if os.environ.get("MEMORIX_DB_PATH"):
            self._config["db_path"] = os.environ["MEMORIX_DB_PATH"]
        if os.environ.get("MEMORIX_PROJECT"):
            self._config["project"] = os.environ["MEMORIX_PROJECT"]

        # Set default db_path if not configured
        if "db_path" not in self._config:
            default_db_path = str(Path(self._hermes_home) / "memorix.db")
            self._config["db_path"] = default_db_path

        # Import and create memorix provider
        try:
            from memorix.integrations.hermes.config import MemorixHermesConfig
            from memorix.integrations.hermes.provider import MemorixMemoryProvider

            # Create config
            mc = MemorixHermesConfig(**self._config)

            # Create and initialize provider
            self._provider = MemorixMemoryProvider(mc)
            self._provider.initialize(session_id=session_id, **kwargs)

            logger.info("Memorix provider initialized with db_path=%s", self._config.get("db_path"))
        except Exception as e:
            logger.error("Failed to initialize memorix provider: %s", e)
            raise

    def system_prompt_block(self) -> str:
        """Return text to include in the system prompt."""
        if self._provider is None:
            return ""
        return self._provider.system_prompt_block()

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Recall relevant context for the upcoming turn."""
        if self._provider is None:
            return ""
        # memorix's prefetch is async, but Hermes expects sync
        # We'll use asyncio.run to bridge
        import asyncio
        try:
            return asyncio.run(self._provider.prefetch(query, session_id=session_id))
        except Exception as e:
            logger.warning("Memorix prefetch failed: %s", e)
            return ""

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        """Queue a background recall for the next turn."""
        if self._provider is None:
            return
        self._provider.queue_prefetch(query, session_id=session_id)

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        """Persist a completed turn to the backend."""
        if self._provider is None:
            return
        import asyncio
        try:
            asyncio.run(self._provider.sync_turn(
                user_msg=user_content,
                assistant_msg=assistant_content,
                session_id=session_id
            ))
        except Exception as e:
            logger.warning("Memorix sync_turn failed: %s", e)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return tool schemas this provider exposes."""
        if self._provider is None:
            return []
        return self._provider.get_tool_schemas()

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs: Any) -> str:
        """Handle a tool call for one of this provider's tools."""
        if self._provider is None:
            return json.dumps({"error": "Memorix provider not initialized"})
        return self._provider.handle_tool_call(tool_name, args, **kwargs)

    def shutdown(self) -> None:
        """Clean shutdown."""
        if self._provider is not None:
            try:
                self._provider.shutdown()
            except Exception as e:
                logger.warning("Memorix shutdown failed: %s", e)
            self._provider = None

    def on_turn_start(self, turn_number: int, message: str, **kwargs: Any) -> None:
        """Called at the start of each turn."""
        if self._provider is not None:
            self._provider.on_turn_start(turn=turn_number, message=message, **kwargs)

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        """Called when a session ends."""
        if self._provider is not None:
            self._provider.on_session_end(messages)

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        """Called before context compression."""
        if self._provider is None:
            return ""
        return self._provider.on_pre_compress(messages)

    def on_memory_write(self, action: str, target: str, content: str) -> None:
        """Called when built-in memory tool writes an entry."""
        if self._provider is not None:
            self._provider.on_memory_write(action=action, target=target, content=content)

    def on_delegation(self, task: str, result: str, *, child_session_id: str = "", **kwargs: Any) -> None:
        """Called when a subagent completes."""
        if self._provider is not None:
            self._provider.on_delegation(task=task, result=result, child_session_id=child_session_id, **kwargs)

    def get_config_schema(self) -> List[Dict[str, Any]]:
        """Return config fields this provider needs."""
        return [
            {
                "key": "db_path",
                "description": "Path to memorix database file",
                "secret": False,
                "required": False,
                "default": "~/.hermes/memorix.db",
            },
            {
                "key": "project",
                "description": "Project name for memory isolation",
                "secret": False,
                "required": False,
                "default": "hermes",
            },
            {
                "key": "auto_save",
                "description": "Automatically save turns to memory",
                "secret": False,
                "required": False,
                "default": True,
            },
            {
                "key": "turn_extraction",
                "description": "Use LLM to extract facts from turns",
                "secret": False,
                "required": False,
                "default": False,
            },
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        """Write config to memorix.json."""
        config_path = Path(hermes_home) / "memorix.json"
        config_path.write_text(json.dumps(values, indent=2))
        logger.info("Saved memorix config to %s", config_path)


def register(ctx: Any) -> None:
    """Register the memorix memory provider with Hermes."""
    ctx.register_memory_provider(MemorixProvider())
