"""Tests for BaseAgent and AgentResult."""
from __future__ import annotations

import pytest

from agent.base import BaseAgent, AgentResult
from tests.agent.conftest import DummyAgent


class TestAgentResult:
    """Test AgentResult dataclass."""

    def test_success_result(self):
        result = AgentResult(success=True, output="done")
        assert result.success is True
        assert result.output == "done"
        assert result.error is None
        assert result.tool_calls == 0

    def test_error_result(self):
        result = AgentResult(
            success=False,
            output="",
            error="Something went wrong",
        )
        assert result.success is False
        assert result.error == "Something went wrong"

    def test_full_result(self):
        result = AgentResult(
            success=True,
            output="hello",
            agent_name="worker",
            model="test/model",
            duration_seconds=1.5,
            tool_calls=10,
            metadata={"key": "value"},
        )
        assert result.agent_name == "worker"
        assert result.model == "test/model"
        assert result.duration_seconds == 1.5
        assert result.tool_calls == 10
        assert result.metadata == {"key": "value"}


class TestBaseAgent:
    """Test BaseAgent abstract class."""

    def test_cannot_instantiate_base_directly(self):
        with pytest.raises(TypeError):
            BaseAgent.__init__(object())  # Abstract prevents instantiation

    def test_dummy_agent_run(self, dummy_agent):
        result = dummy_agent.run("test prompt")
        assert result.success is True
        assert "Processed: test prompt" in result.output
        assert result.agent_name == "test-dummy"

    def test_dummy_agent_stop(self, dummy_agent):
        dummy_agent._running = True
        dummy_agent.stop()
        assert dummy_agent.is_running is False

    def test_is_running_initially_false(self, dummy_agent):
        assert dummy_agent.is_running is False
