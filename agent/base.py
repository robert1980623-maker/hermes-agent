"""Base class for all agent workers."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from hermes_cli.agent_config import AgentConfig


@dataclass
class AgentResult:
    """Result returned by an agent worker."""
    success: bool
    output: str
    agent_name: str = ""
    model: str = ""
    duration_seconds: float = 0.0
    tool_calls: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Abstract base for agent workers.

    Subclasses implement the worker loop for a specific agent type
    (DeepAgent, System, CLI, etc.).
    """

    def __init__(self, config: AgentConfig, name: str) -> None:
        self.config = config
        self.name = name
        self._running = False

    @abstractmethod
    def run(self, prompt: str) -> AgentResult:
        """Execute the agent with the given prompt.

        Args:
            prompt: The task prompt.

        Returns:
            AgentResult with the outcome.
        """

    def stop(self) -> None:
        """Signal the agent to stop gracefully."""
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running
