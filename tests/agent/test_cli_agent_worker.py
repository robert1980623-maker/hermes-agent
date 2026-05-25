"""Tests for CLIAgentWorker."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent.cli_agent_worker import CLIAgentWorker
from hermes_cli.agent_config import AgentConfig


@pytest.fixture
def cli_worker(sample_agent_config: AgentConfig) -> CLIAgentWorker:
    return CLIAgentWorker(config=sample_agent_config, name="cli-1", agent_type="cline")


class TestCLIAgentWorkerInit:
    """Test CLIAgentWorker initialization."""

    def test_create_worker(self, sample_agent_config):
        worker = CLIAgentWorker(
            config=sample_agent_config, name="cli-1", agent_type="cline"
        )
        assert worker.name == "cli-1"
        assert worker.agent_type == "cline"
        assert worker.timeout == 600
        assert worker.extra_args == []

    def test_invalid_agent_type(self, sample_agent_config):
        with pytest.raises(ValueError, match="Unsupported agent type"):
            CLIAgentWorker(
                config=sample_agent_config, name="cli-1", agent_type="invalid"
            )

    def test_with_extra_args(self, sample_agent_config):
        worker = CLIAgentWorker(
            config=sample_agent_config, name="cli-1",
            agent_type="cline", extra_args=["--auto-approve", "true"],
        )
        assert worker.extra_args == ["--auto-approve", "true"]


class TestCLIAgentWorkerRun:
    """Test CLIAgentWorker.run() method."""

    def test_run_success(self, cli_worker):
        with patch("agent.cli_agent_worker.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="Task completed\n", stderr=""
            )
            result = cli_worker.run("Fix the bug")
            assert result.success is True
            assert "Task completed" in result.output
            assert result.metadata["agent_type"] == "cline"
            assert result.metadata["exit_code"] == 0

    def test_run_failure(self, cli_worker):
        with patch("agent.cli_agent_worker.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="Error occurred"
            )
            result = cli_worker.run("Do something")
            assert result.success is False
            assert "Error occurred" in result.output

    def test_run_timeout(self, sample_agent_config):
        worker = CLIAgentWorker(
            config=sample_agent_config, name="cli-1",
            agent_type="cline", timeout=1,
        )
        with patch("agent.cli_agent_worker.subprocess.run") as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="cline", timeout=1)
            result = worker.run("Long task")
            assert result.success is False
            assert "timed out" in result.error

    def test_run_command_not_found(self, cli_worker):
        with patch("agent.cli_agent_worker.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = cli_worker.run("task")
            assert result.success is False
            assert "not found" in result.error

    def test_build_command(self, sample_agent_config):
        worker = CLIAgentWorker(
            config=sample_agent_config, name="cli-1",
            agent_type="cline", extra_args=["--yolo"],
        )
        cmd = worker._build_command("hello")
        assert cmd == ["cline", "--yolo", "hello"]

    def test_build_command_codex(self, sample_agent_config):
        worker = CLIAgentWorker(
            config=sample_agent_config, name="cli-1", agent_type="codex"
        )
        cmd = worker._build_command("hello")
        assert cmd[0] == "openai-codex"
        assert "hello" in cmd
