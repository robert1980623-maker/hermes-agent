"""Tests for AgentConfig model."""
from __future__ import annotations

from hermes_cli.agent_config import AgentConfig


class TestAgentConfigDefaults:
    """Test default values for AgentConfig fields."""

    def test_minimal_config(self):
        config = AgentConfig(model="test/model")
        assert config.model == "test/model"
        assert config.toolset is None
        assert config.allowed_tools == []
        assert config.max_iterations == 30
        assert config.system_prompt is None
        assert config.env_overrides == {}
        assert config.metadata == {}

    def test_full_config(self):
        config = AgentConfig(
            model="anthropic/claude-sonnet-4",
            toolset="web",
            allowed_tools=["web_search"],
            max_iterations=50,
            system_prompt="You are helpful.",
            env_overrides={"KEY": "value"},
            metadata={"owner": "admin"},
        )
        assert config.model == "anthropic/claude-sonnet-4"
        assert config.toolset == "web"
        assert config.allowed_tools == ["web_search"]
        assert config.max_iterations == 50
        assert config.system_prompt == "You are helpful."
        assert config.env_overrides == {"KEY": "value"}
        assert config.metadata == {"owner": "admin"}


class TestAgentConfigResolveTools:
    """Test resolve_tools() method."""

    def test_no_toolset_returns_none(self):
        config = AgentConfig(model="test/model")
        assert config.resolve_tools() is None

    def test_allowed_tools_takes_precedence(self):
        config = AgentConfig(
            model="test/model",
            toolset="web",
            allowed_tools=["custom_tool"],
        )
        assert config.resolve_tools() == ["custom_tool"]

    def test_toolset_without_get_toolset_tools_returns_none(self):
        # get_toolset_tools doesn't exist yet, so this returns None
        config = AgentConfig(model="test/model", toolset="web")
        # The current implementation has a TODO and returns None
        assert config.resolve_tools() is None
