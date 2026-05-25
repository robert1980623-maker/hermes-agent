"""Tests for DeepAgentWorker."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent.base import AgentResult
from agent.deep_agent_worker import DeepAgentWorker
from hermes_cli.agent_config import AgentConfig


@pytest.fixture
def mock_aiclass():
    """Mock AIAgent class."""
    with patch("agent.deep_agent_worker.AIAgent") as mock:
        yield mock


class TestDeepAgentWorkerInit:
    """Test DeepAgentWorker initialization."""

    def test_create_worker(self, sample_agent_config):
        worker = DeepAgentWorker(config=sample_agent_config, name="deep-1")
        assert worker.name == "deep-1"
        assert worker.config == sample_agent_config
        assert worker._agent is None
        assert worker.is_running is False


class TestDeepAgentWorkerRun:
    """Test DeepAgentWorker.run() method."""

    def test_run_success(self, sample_agent_config, mock_aiclass):
        mock_instance = MagicMock()
        mock_instance.run_conversation.return_value = "Task completed successfully"
        mock_aiclass.return_value = mock_instance

        worker = DeepAgentWorker(config=sample_agent_config, name="deep-1")
        result = worker.run("Do something")

        assert result.success is True
        assert "Task completed successfully" in result.output
        assert result.agent_name == "deep-1"
        assert result.model == "test/model"
        assert result.error is None

    def test_run_with_system_prompt(self, sample_agent_config, mock_aiclass):
        sample_agent_config.system_prompt = "You are helpful"
        mock_instance = MagicMock()
        mock_instance.run_conversation.return_value = "done"
        mock_aiclass.return_value = mock_instance

        worker = DeepAgentWorker(config=sample_agent_config, name="deep-1")
        worker.run("task")

        mock_instance.run_conversation.assert_called_once_with(
            user_message="task",
            system_prompt="You are helpful",
        )

    def test_run_exception(self, sample_agent_config, mock_aiclass):
        mock_instance = MagicMock()
        mock_instance.run_conversation.side_effect = RuntimeError("API error")
        mock_aiclass.return_value = mock_instance

        worker = DeepAgentWorker(config=sample_agent_config, name="deep-1")
        result = worker.run("Do something")

        assert result.success is False
        assert result.error == "API error"
        assert result.output == ""

    def test_run_sets_running_flag(self, sample_agent_config, mock_aiclass):
        mock_instance = MagicMock()
        mock_instance.run_conversation.return_value = "done"
        mock_aiclass.return_value = mock_instance

        worker = DeepAgentWorker(config=sample_agent_config, name="deep-1")
        assert worker.is_running is False
        worker.run("task")
        assert worker.is_running is False  # Reset in finally block

    def test_lazy_agent_creation(self, sample_agent_config, mock_aiclass):
        mock_instance = MagicMock()
        mock_instance.run_conversation.return_value = "done"
        mock_aiclass.return_value = mock_instance

        worker = DeepAgentWorker(config=sample_agent_config, name="deep-1")
        assert worker._agent is None
        worker.run("task")
        assert worker._agent is not None

    def test_agent_reused_on_second_run(self, sample_agent_config, mock_aiclass):
        mock_instance = MagicMock()
        mock_instance.run_conversation.return_value = "done"
        mock_aiclass.return_value = mock_instance

        worker = DeepAgentWorker(config=sample_agent_config, name="deep-1")
        worker.run("first task")
        worker.run("second task")

        # AIAgent should only be constructed once (lazy)
        assert mock_aiclass.call_count == 1
