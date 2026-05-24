"""Fixtures for agent framework tests."""
from __future__ import annotations

import pytest

from hermes_cli.agent_config import AgentConfig
from agent.base import BaseAgent, AgentResult


@pytest.fixture
def sample_agent_config() -> AgentConfig:
    """A minimal AgentConfig for testing."""
    return AgentConfig(model="test/model")


@pytest.fixture
def full_agent_config() -> AgentConfig:
    """A fully populated AgentConfig for testing."""
    return AgentConfig(
        model="anthropic/claude-sonnet-4-20250514",
        toolset="web",
        allowed_tools=["web_search", "web_extract"],
        max_iterations=50,
        system_prompt="You are a test agent.",
        env_overrides={"TEST_VAR": "test_value"},
        metadata={"owner": "test", "description": "Test agent"},
    )


class DummyAgent(BaseAgent):
    """A concrete BaseAgent implementation for testing the abstract class."""

    def run(self, prompt: str) -> AgentResult:
        self._running = True
        return AgentResult(
            success=True,
            output=f"Processed: {prompt}",
            agent_name=self.name,
            model=self.config.model,
            duration_seconds=0.5,
            tool_calls=3,
        )


@pytest.fixture
def dummy_agent(sample_agent_config: AgentConfig) -> DummyAgent:
    """A DummyAgent instance for testing."""
    return DummyAgent(config=sample_agent_config, name="test-dummy")
