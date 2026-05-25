"""CLIAgentWorker — delegates tasks to external CLI agents."""
from __future__ import annotations

import subprocess
import time
from typing import Any

from hermes_cli.agent_config import AgentConfig
from agent.base import BaseAgent, AgentResult


# Supported CLI agent commands
SUPPORTED_AGENTS = {
    "cline": "cline",
    "codex": "openai-codex",
}


class CLIAgentWorker(BaseAgent):
    """Agent worker that delegates to external CLI coding agents.

    Supports Cline, OpenAI Codex, and other CLI-based agents.
    The external agent runs as a subprocess and returns output.
    """

    def __init__(
        self, config: AgentConfig, name: str,
        agent_type: str = "cline",
        timeout: int = 600,
        workdir: str | None = None,
        extra_args: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the CLI agent worker.

        Args:
            config: AgentConfig for this agent.
            name: Human-readable name.
            agent_type: Type of CLI agent ("cline", "codex").
            timeout: Max seconds to wait for the agent.
            workdir: Working directory for the agent.
            extra_args: Additional CLI arguments.
        """
        super().__init__(config, name)
        if agent_type not in SUPPORTED_AGENTS:
            raise ValueError(
                f"Unsupported agent type: {agent_type}. "
                f"Supported: {list(SUPPORTED_AGENTS.keys())}"
            )
        self.agent_type = agent_type
        self.timeout = timeout
        self.workdir = workdir
        self.extra_args = extra_args or []

    def _build_command(self, prompt: str) -> list[str]:
        """Build the CLI command to execute."""
        cmd = [SUPPORTED_AGENTS[self.agent_type]]
        cmd.extend(self.extra_args)
        cmd.append(prompt)
        return cmd

    def run(self, prompt: str) -> AgentResult:
        """Delegate the prompt to the external CLI agent.

        Args:
            prompt: The task prompt.

        Returns:
            AgentResult with the agent's output.
        """
        self._running = True
        start_time = time.monotonic()
        try:
            cmd = self._build_command(prompt)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.workdir,
            )
            elapsed = time.monotonic() - start_time
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr

            return AgentResult(
                success=result.returncode == 0,
                output=output.strip(),
                agent_name=self.name,
                model=self.config.model,
                duration_seconds=elapsed,
                tool_calls=1,
                metadata={
                    "agent_type": self.agent_type,
                    "exit_code": result.returncode,
                },
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start_time
            return AgentResult(
                success=False,
                output="",
                agent_name=self.name,
                model=self.config.model,
                duration_seconds=elapsed,
                error=f"{self.agent_type} timed out after {self.timeout}s",
            )
        except FileNotFoundError:
            elapsed = time.monotonic() - start_time
            return AgentResult(
                success=False,
                output="",
                agent_name=self.name,
                model=self.config.model,
                duration_seconds=elapsed,
                error=f"{self.agent_type} command not found. Is it installed?",
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
