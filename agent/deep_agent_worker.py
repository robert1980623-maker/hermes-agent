"""DeepAgentWorker — wraps the existing AIAgent for deep task execution."""
from __future__ import annotations

import time
from typing import Any

from hermes_cli.agent_config import AgentConfig
from agent.base import BaseAgent, AgentResult
from run_agent import AIAgent


class DeepAgentWorker(BaseAgent):
    """Agent worker that uses the internal AIAgent for deep task execution.

    This is the primary worker — it creates an AIAgent instance with the
    configured model and runs the conversation loop.
    """

    def __init__(self, config: AgentConfig, name: str, **kwargs: Any) -> None:
        """Initialize the DeepAgentWorker.

        Args:
            config: AgentConfig with model, toolset, etc.
            name: Human-readable name for this agent instance.
            **kwargs: Additional args passed to AIAgent (provider, etc.).
        """
        super().__init__(config, name)
        self._kwargs = kwargs
        self._agent = None

    def _build_agent(self) -> Any:
        """Build and return an AIAgent instance.

        Lazily creates the agent on first run() call.
        """
        if self._agent is None:
            self._agent = AIAgent(
                model=self.config.model,
                max_iterations=self.config.max_iterations,
                **self._kwargs
            )
        return self._agent

    def run(self, prompt: str) -> AgentResult:
        """Execute the agent with the given prompt.

        Args:
            prompt: The task prompt.

        Returns:
            AgentResult with success/failure and output.
        """
        self._running = True
        start_time = time.monotonic()
        try:
            agent = self._build_agent()
            output = agent.run_conversation(
                user_message=prompt,
                system_prompt=self.config.system_prompt,
            )
            elapsed = time.monotonic() - start_time
            return AgentResult(
                success=True,
                output=output or "",
                agent_name=self.name,
                model=self.config.model,
                duration_seconds=elapsed,
            )
        except Exception as exc:
            elapsed = time.monotonic() - start_time
            return AgentResult(
                success=False,
                output="",
                agent_name=self.name,
                model=self.config.model,
                duration_seconds=elapsed,
                error=str(exc),
            )
        finally:
            self._running = False
