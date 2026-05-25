"""Tests for the hermes agent CLI commands."""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from hermes_cli.agent_cli import agent
from agent.base import AgentResult


@pytest.fixture
def cli_runner():
    return CliRunner()


class TestAgentList:
    """Test 'hermes agent list' command."""

    def test_list_no_agents(self, cli_runner):
        with patch("hermes_cli.agent_cli.list_agents", return_value=[]):
            result = cli_runner.invoke(agent, ["list"])
            assert result.exit_code == 0
            assert "No agents configured" in result.output

    def test_list_with_agents(self, cli_runner):
        agents = [
            {"name": "coder", "model": "anthropic/claude-sonnet-4", "toolset": "core", "max_iterations": 30},
            {"name": "researcher", "model": "openai/gpt-4o", "toolset": "web", "max_iterations": 50},
        ]
        with patch("hermes_cli.agent_cli.list_agents", return_value=agents):
            result = cli_runner.invoke(agent, ["list"])
            assert result.exit_code == 0
            assert "coder" in result.output
            assert "researcher" in result.output
            assert "claude-sonnet-4" in result.output
            assert "gpt-4o" in result.output


class TestAgentInfo:
    """Test 'hermes agent info' command."""

    def test_info_success(self, cli_runner):
        mock_config = MagicMock()
        mock_config.model = "anthropic/claude-sonnet-4"
        mock_config.toolset = "web"
        mock_config.allowed_tools = []
        mock_config.max_iterations = 50
        mock_config.system_prompt = None
        mock_config.env_overrides = {}
        mock_config.metadata = {}

        with patch("hermes_cli.agent_cli.get_agent_config", return_value=mock_config):
            result = cli_runner.invoke(agent, ["info", "my-agent"])
            assert result.exit_code == 0
            assert "my-agent" in result.output
            assert "anthropic/claude-sonnet-4" in result.output
            assert "50" in result.output

    def test_info_not_found(self, cli_runner):
        with patch("hermes_cli.agent_cli.get_agent_config", side_effect=ValueError("Agent 'missing' not found")):
            result = cli_runner.invoke(agent, ["info", "missing"])
            assert result.exit_code == 1
            assert "not found" in result.output


class TestAgentRun:
    """Test 'hermes agent run' command."""

    def test_run_success_text(self, cli_runner):
        mock_result = AgentResult(
            success=True, output="Task done", agent_name="coder",
            model="test/model", duration_seconds=2.5, tool_calls=5,
        )
        with patch("hermes_cli.agent_cli.run_agent", return_value=mock_result):
            result = cli_runner.invoke(agent, ["run", "coder", "Fix the bug"])
            assert result.exit_code == 0
            assert "coder" in result.output
            assert "Task done" in result.output

    def test_run_success_json(self, cli_runner):
        mock_result = AgentResult(
            success=True, output="done", agent_name="coder",
            model="test/model", duration_seconds=1.0, tool_calls=3,
        )
        with patch("hermes_cli.agent_cli.run_agent", return_value=mock_result):
            result = cli_runner.invoke(agent, ["run", "coder", "test", "-o", "json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert data["success"] is True
            assert data["output"] == "done"
            assert data["agent_name"] == "coder"

    def test_run_failure(self, cli_runner):
        mock_result = AgentResult(
            success=False, output="", agent_name="coder",
            model="test/model", duration_seconds=0.5, error="API timeout",
        )
        with patch("hermes_cli.agent_cli.run_agent", return_value=mock_result):
            result = cli_runner.invoke(agent, ["run", "coder", "test"])
            assert result.exit_code == 1
            assert "FAILED" in result.output
            assert "API timeout" in result.output

    def test_run_config_error(self, cli_runner):
        with patch("hermes_cli.agent_cli.run_agent", side_effect=ValueError("Agent 'x' not found")):
            result = cli_runner.invoke(agent, ["run", "x", "test"])
            assert result.exit_code == 1
            assert "not found" in result.output

    def test_run_with_worker_type(self, cli_runner):
        mock_result = AgentResult(
            success=True, output="system output", agent_name="sys",
            model="system", duration_seconds=0.1,
        )
        with patch("hermes_cli.agent_cli.run_agent", return_value=mock_result):
            result = cli_runner.invoke(agent, ["run", "sys", "echo hi", "-w", "system"])
            assert result.exit_code == 0
            assert "system output" in result.output
