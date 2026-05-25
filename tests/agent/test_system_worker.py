"""Tests for SystemWorker."""
from __future__ import annotations

import pytest

from agent.system_worker import SystemWorker
from hermes_cli.agent_config import AgentConfig


@pytest.fixture
def system_worker(sample_agent_config: AgentConfig) -> SystemWorker:
    return SystemWorker(config=sample_agent_config, name="sys-1")


class TestSystemWorkerRun:
    """Test SystemWorker.run() method."""

    def test_run_success(self, system_worker):
        result = system_worker.run("echo hello")
        assert result.success is True
        assert result.output == "hello"
        assert result.agent_name == "sys-1"
        assert result.model == "system"
        assert result.metadata["exit_code"] == 0

    def test_run_with_output(self, system_worker):
        result = system_worker.run("echo -n 'test output'")
        assert result.output == "test output"

    def test_run_failure(self, system_worker):
        result = system_worker.run("false")
        assert result.success is False
        assert result.metadata["exit_code"] == 1

    def test_run_with_stderr(self, system_worker):
        result = system_worker.run("echo error >&2")
        # stderr is captured and included in output
        assert "error" in result.output

    def test_run_timeout(self, sample_agent_config):
        worker = SystemWorker(config=sample_agent_config, name="sys-1", timeout=1)
        result = worker.run("sleep 10")
        assert result.success is False
        assert "timed out" in result.error

    def test_run_with_workdir(self, sample_agent_config, tmp_path):
        worker = SystemWorker(
            config=sample_agent_config, name="sys-1", workdir=str(tmp_path)
        )
        result = worker.run("pwd")
        assert result.output == str(tmp_path)

    def test_is_running_flag(self, system_worker):
        assert system_worker.is_running is False
