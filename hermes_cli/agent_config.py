"""Per-agent configuration — loaded from config.yaml agents: section."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration for a single named agent instance."""

    model: str
    """Model identifier (e.g. 'anthropic/claude-sonnet-4-20250514')."""

    toolset: str | None = None
    """Named toolset from toolsets.py. None = use core tools only."""

    allowed_tools: list[str] = Field(default_factory=list)
    """Explicit allow-list of tool names (overrides toolset)."""

    max_iterations: int = 30
    """Max tool-calling turns per agent run."""

    system_prompt: str | None = None
    """Agent-specific system prompt or prompt fragment."""

    env_overrides: dict[str, str] = Field(default_factory=dict)
    """Environment variable overrides for this agent."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Arbitrary metadata (owner, description, tags)."""

    def resolve_tools(self) -> list[str] | None:
        """Return the effective tool list for this agent.

        Returns None if using default/core tools,
        or a list of tool names if allowed_tools is set.
        """
        if self.allowed_tools:
            return self.allowed_tools
        if self.toolset:
            # TODO: Implement get_toolset_tools in toolsets.py when available.
            # from toolsets import get_toolset_tools
            # return get_toolset_tools(self.toolset)
            return None
        return None
