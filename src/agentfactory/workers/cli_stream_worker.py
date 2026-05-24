"""CLI Stream Worker — Role-based Cline execution with output streaming.

Spawns ``cline`` subprocesses with role-specific system prompts and
streams stdout/stderr in real-time. Designed to integrate with the
StreamAdapter pattern for event-driven orchestration.

Role Injection Strategy
-----------------------
System prompts are injected via a temporary ``.clinerules`` file in the
working directory. This is the mechanism Cline natively reads for
per-project behavioural rules. The file is created before execution
and cleaned up afterward (unless ``keep_rules=True``).

Usage
-----
    worker = CliStreamWorker(workdir="/path/to/project")

    # Execute a role with its system prompt
    result = worker.execute_role(
        role_config={
            "name": "code-reviewer",
            "system_prompt": "You are a senior code reviewer. ...",
            "model": "claude-sonnet-4-20250514",
        },
        context="Review the changes in src/agentfactory/workers/",
    )
    print(result)  # Full captured output

    # Async variant for integration with StreamAdapter
    async for chunk in worker.execute_role_stream(role_config, context):
        dispatch_event({"type": "chunk", "data": chunk})
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────

CLINE_BIN = "cline"
CLINERULES_FILE = ".clinerules"

DEFAULT_TIMEOUT = 300  # 5 minutes
DEFAULT_MODEL = "gpt-4o"

# ── Data Classes ────────────────────────────────────────────────────


@dataclass
class RoleConfig:
    """Describes a worker role's execution parameters."""

    name: str
    """Human-readable role identifier (e.g. 'code-reviewer')."""

    system_prompt: str = ""
    """The system prompt / instructions injected as .clinerules."""

    model: str = DEFAULT_MODEL
    """Cline model to use (passed via --model)."""

    plan_mode: bool = False
    """If True, run Cline in plan mode (no file writes)."""

    extra_args: list[str] = field(default_factory=list)
    """Additional CLI flags appended verbatim."""


@dataclass
class ExecutionResult:
    """Captured outcome of a role execution."""

    role_name: str
    success: bool
    output: str
    exit_code: int
    elapsed_ms: int = 0
    error: Optional[str] = None


# ── Worker ──────────────────────────────────────────────────────────


class CliStreamWorker:
    """Execute Cline roles with system-prompt injection and output streaming.

    Args:
        workdir: Base directory for execution. ``.clinerules`` is
            written here during role execution.
        timeout: Per-execution timeout in seconds.
        keep_rules: If True, leave ``.clinerules`` on disk after
            execution (useful for debugging).
    """

    def __init__(
        self,
        workdir: str | Path = ".",
        timeout: int = DEFAULT_TIMEOUT,
        keep_rules: bool = False,
    ) -> None:
        self.workdir = Path(workdir).resolve()
        self.timeout = timeout
        self.keep_rules = keep_rules
        self._rules_path = self.workdir / CLINERULES_FILE

    # ── Public API ──────────────────────────────────────────────────

    def execute_role(self, role_config: dict, context: str) -> str:
        """Execute a role synchronously and return the full output.

        This is the convenience wrapper around ``execute_role_sync``
        that accepts a plain dict (for JSON/deserialized configs).

        Args:
            role_config: Dict with keys matching :class:`RoleConfig`
                fields (``name``, ``system_prompt``, ``model``,
                ``plan_mode``, ``extra_args``).
            context: The task prompt / context to pass to Cline.

        Returns:
            The complete stdout+stderr captured during execution.
        """
        rc = self._dict_to_role_config(role_config)
        result = self.execute_role_sync(rc, context)
        if not result.success and result.error:
            logger.warning(
                "[cli_stream_worker] Role '%s' failed: %s",
                result.role_name,
                result.error,
            )
        return result.output

    def execute_role_sync(
        self, role_config: RoleConfig, context: str
    ) -> ExecutionResult:
        """Execute a role synchronously with full result object.

        Args:
            role_config: Parsed role configuration.
            context: The task prompt to send to Cline.

        Returns:
            An :class:`ExecutionResult` with status, output, and timing.
        """
        import time

        self._inject_rules(role_config.system_prompt)
        start = time.monotonic()

        try:
            cmd = self._build_command(role_config, context)
            logger.info(
                "[cli_stream_worker] Executing role '%s': %s",
                role_config.name,
                " ".join(cmd),
            )

            proc = self._spawn(cmd)
            output = self._stream_stdout(proc)
            exit_code = proc.wait(timeout=self.timeout)

            elapsed_ms = int((time.monotonic() - start) * 1000)

            return ExecutionResult(
                role_name=role_config.name,
                success=exit_code == 0,
                output=output,
                exit_code=exit_code,
                elapsed_ms=elapsed_ms,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                role_name=role_config.name,
                success=False,
                output="",
                exit_code=-1,
                elapsed_ms=elapsed_ms,
                error=f"Execution timed out after {self.timeout}s",
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                role_name=role_config.name,
                success=False,
                output="",
                exit_code=-1,
                elapsed_ms=elapsed_ms,
                error=str(exc),
            )
        finally:
            self._cleanup_rules()

    async def execute_role_async(
        self, role_config: RoleConfig, context: str
    ) -> ExecutionResult:
        """Execute a role asynchronously.

        Args:
            role_config: Parsed role configuration.
            context: The task prompt to send to Cline.

        Returns:
            An :class:`ExecutionResult` with status, output, and timing.
        """
        import time

        self._inject_rules(role_config.system_prompt)
        start = time.monotonic()

        try:
            cmd = self._build_command(role_config, context)
            logger.info(
                "[cli_stream_worker] Executing role '%s' (async): %s",
                role_config.name,
                " ".join(cmd),
            )

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workdir),
            )

            output_chunks: list[str] = []

            async def _read_stream(
                stream: asyncio.StreamReader, label: str
            ) -> None:
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    text = line.decode(errors="replace")
                    output_chunks.append(text)
                    logger.debug("[%s] %s: %s", role_config.name, label, text.rstrip())

            await asyncio.gather(
                _read_stream(proc.stdout, "stdout"),  # type: ignore[arg-type]
                _read_stream(proc.stderr, "stderr"),  # type: ignore[arg-type]
            )

            exit_code = await asyncio.wait_for(
                proc.wait(), timeout=self.timeout
            )
            output = "".join(output_chunks)
            elapsed_ms = int((time.monotonic() - start) * 1000)

            return ExecutionResult(
                role_name=role_config.name,
                success=exit_code == 0,
                output=output,
                exit_code=exit_code,
                elapsed_ms=elapsed_ms,
            )
        except asyncio.TimeoutError:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                role_name=role_config.name,
                success=False,
                output="",
                exit_code=-1,
                elapsed_ms=elapsed_ms,
                error=f"Execution timed out after {self.timeout}s",
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return ExecutionResult(
                role_name=role_config.name,
                success=False,
                output="",
                exit_code=-1,
                elapsed_ms=elapsed_ms,
                error=str(exc),
            )
        finally:
            self._cleanup_rules()

    async def execute_role_stream(
        self, role_config: RoleConfig, context: str
    ) -> AsyncIterator[str]:
        """Execute a role and yield output chunks as they arrive.

        This is the primary integration point for StreamAdapter
        patterns — consumers can dispatch events per chunk:

            async for chunk in worker.execute_role_stream(role, ctx):
                adapter.dispatch({"type": "output", "chunk": chunk})

        Args:
            role_config: Parsed role configuration.
            context: The task prompt to send to Cline.

        Yields:
            stdout/stderr text chunks as they become available.
        """
        import time

        self._inject_rules(role_config.system_prompt)
        start = time.monotonic()

        try:
            cmd = self._build_command(role_config, context)
            logger.info(
                "[cli_stream_worker] Streaming role '%s': %s",
                role_config.name,
                " ".join(cmd),
            )

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workdir),
            )

            async def _yield_stream(
                stream: asyncio.StreamReader,
            ) -> AsyncIterator[str]:
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    text = line.decode(errors="replace")
                    yield text

            # Merge stdout and stderr, yielding as they arrive
            async for text in self._merge_streams(
                _yield_stream(proc.stdout),  # type: ignore[arg-type]
                _yield_stream(proc.stderr),  # type: ignore[arg-type]
            ):
                yield text

            exit_code = await asyncio.wait_for(
                proc.wait(), timeout=self.timeout
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)

            if exit_code != 0:
                logger.warning(
                    "[cli_stream_worker] Role '%s' exited with code %d (%dms)",
                    role_config.name,
                    exit_code,
                    elapsed_ms,
                )
            else:
                logger.info(
                    "[cli_stream_worker] Role '%s' completed (%dms)",
                    role_config.name,
                    elapsed_ms,
                )

        except asyncio.TimeoutError:
            logger.error(
                "[cli_stream_worker] Role '%s' timed out after %ds",
                role_config.name,
                self.timeout,
            )
        except Exception as exc:
            logger.error(
                "[cli_stream_worker] Role '%s' execution error: %s",
                role_config.name,
                exc,
            )
        finally:
            self._cleanup_rules()

    # ── Internal ────────────────────────────────────────────────────

    def _inject_rules(self, system_prompt: str) -> None:
        """Write the system prompt to .clinerules in the workdir."""
        if not system_prompt:
            return
        self._rules_path.write_text(system_prompt, encoding="utf-8")
        logger.debug(
            "[cli_stream_worker] Injected .clinerules at %s (%d bytes)",
            self._rules_path,
            len(system_prompt),
        )

    def _cleanup_rules(self) -> None:
        """Remove the temporary .clinerules file."""
        if self.keep_rules:
            return
        if self._rules_path.exists():
            try:
                self._rules_path.unlink()
                logger.debug("[cli_stream_worker] Cleaned up .clinerules")
            except OSError as exc:
                logger.warning(
                    "[cli_stream_worker] Failed to remove .clinerules: %s", exc
                )

    def _build_command(
        self, role_config: RoleConfig, context: str
    ) -> list[str]:
        """Construct the full ``cline`` command list.

        The command always includes ``--auto-approve true --thinking none``
        so the worker runs unattended. The system prompt is injected
        via .clinerules, so the prompt argument is purely the task context.
        """
        cmd: list[str] = [CLINE_BIN]

        # Unattended execution flags
        cmd.extend(["--auto-approve", "true"])
        cmd.extend(["--thinking", "none"])

        # Model override (if not default)
        if role_config.model != DEFAULT_MODEL:
            cmd.extend(["--model", role_config.model])

        # Plan mode
        if role_config.plan_mode:
            cmd.append("-p")

        # Extra args from config
        cmd.extend(role_config.extra_args)

        # The task context / prompt
        cmd.append(context)

        return cmd

    def _spawn(self, cmd: list[str]) -> subprocess.Popen:
        """Spawn a subprocess for synchronous execution."""
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(self.workdir),
            text=True,
            bufsize=1,  # Line-buffered
        )

    def _stream_stdout(self, proc: Any) -> str:
        """Read and accumulate stdout from a subprocess in real-time."""
        output_parts: list[str] = []
        assert proc.stdout is not None
        for line in iter(proc.stdout.readline, ""):
            output_parts.append(line)
            logger.debug("[cli_stream_worker] stdout: %s", line.rstrip())
        return "".join(output_parts)

    @staticmethod
    async def _merge_streams(
        *iterators: AsyncIterator[str],
    ) -> AsyncIterator[str]:
        """Merge multiple async iterators, yielding as each produces data."""
        tasks = {
            asyncio.ensure_future(anext(it)): it for it in iterators
        }
        while tasks:
            done, _ = await asyncio.wait(
                tasks.keys(), return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                it = tasks.pop(task)
                try:
                    value = task.result()
                    yield value
                    tasks[asyncio.ensure_future(anext(it))] = it
                except StopAsyncIteration:
                    pass

    @staticmethod
    def _dict_to_role_config(data: dict) -> RoleConfig:
        """Convert a plain dict to a RoleConfig instance."""
        return RoleConfig(
            name=data.get("name", "unnamed"),
            system_prompt=data.get("system_prompt", ""),
            model=data.get("model", DEFAULT_MODEL),
            plan_mode=data.get("plan_mode", False),
            extra_args=data.get("extra_args", []),
        )
