"""SystemWorker — executes shell commands as an agent."""
from __future__ import annotations

import subprocess
import time
from typing import Any

from hermes_cli.agent_config import AgentConfig
from agent.base import BaseAgent, AgentResult


class SystemWorker(BaseAgent):
    """Agent worker that executes shell commands.

    Used for system administration tasks: file operations,
    package management, service control, etc.
    """

    def __init__(
        self, config: AgentConfig, name: str,
        timeout: int = 300,
        shell: str = "bash",
        workdir: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, name)
        self.timeout = timeout
        self.shell = shell
        self.workdir = workdir

    def run(self, prompt: str) -> AgentResult:
        """Execute the prompt as a shell command.

        Args:
            prompt: The shell command to execute.

        Returns:
            AgentResult with stdout/stderr and exit code.
        """
        self._running = True
        start_time = time.monotonic()
        try:
            result = subprocess.run(
                [self.shell, "-c", prompt],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.workdir,
            )
            elapsed = time.monotonic() - start_time
            output = result.stdout
            if result.stderr:
                output += result.stderr

            return AgentResult(
                success=result.returncode == 0,
                output=output.strip(),
                agent_name=self.name,
                model="system",
                duration_seconds=elapsed,
                tool_calls=1,
                metadata={"exit_code": result.returncode},
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start_time
            return AgentResult(
                success=False,
                output="",
                agent_name=self.name,
                model="system",
                duration_seconds=elapsed,
                error=f"Command timed out after {self.timeout}s",
            )
        except Exception as exc:
            elapsed = time.monotonic() - start_time
            return AgentResult(
                success=False,
                output="",
                agent_name=self.name,
                model="system",
                duration_seconds=elapsed,
                error=str(exc),
            )
        finally:
            self._running = False
