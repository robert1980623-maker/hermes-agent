"""Tests for CliStreamWorker — role injection and execution.

Covers:
  - RoleConfig / ExecutionResult data classes
  - .clinerules injection and cleanup
  - Command building with various flag combinations
  - Dict-to-RoleConfig conversion
  - execute_role (dict interface) returns string
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from agentfactory.workers.cli_stream_worker import (
    CliStreamWorker,
    RoleConfig,
    ExecutionResult,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
)


# ===================================================================
# Data class tests
# ===================================================================


class TestRoleConfig:
    def test_defaults(self):
        rc = RoleConfig(name="test-role")
        assert rc.name == "test-role"
        assert rc.system_prompt == ""
        assert rc.model == DEFAULT_MODEL
        assert rc.plan_mode is False
        assert rc.extra_args == []

    def test_full_config(self):
        rc = RoleConfig(
            name="reviewer",
            system_prompt="You are a code reviewer.",
            model="claude-sonnet-4-20250514",
            plan_mode=True,
            extra_args=["--verbose"],
        )
        assert rc.name == "reviewer"
        assert rc.system_prompt == "You are a code reviewer."
        assert rc.model == "claude-sonnet-4-20250514"
        assert rc.plan_mode is True
        assert rc.extra_args == ["--verbose"]


class TestExecutionResult:
    def test_success(self):
        r = ExecutionResult(
            role_name="test", success=True, output="hello", exit_code=0, elapsed_ms=500
        )
        assert r.success
        assert r.error is None

    def test_failure(self):
        r = ExecutionResult(
            role_name="test",
            success=False,
            output="",
            exit_code=1,
            elapsed_ms=100,
            error="Something went wrong",
        )
        assert not r.success
        assert r.error == "Something went wrong"


# ===================================================================
# Worker tests
# ===================================================================


class TestCliStreamWorker:
    def test_init_defaults(self, tmp_path):
        w = CliStreamWorker(workdir=tmp_path)
        assert w.workdir == tmp_path.resolve()
        assert w.timeout == DEFAULT_TIMEOUT
        assert w.keep_rules is False

    def test_init_custom(self, tmp_path):
        w = CliStreamWorker(workdir=tmp_path, timeout=60, keep_rules=True)
        assert w.timeout == 60
        assert w.keep_rules is True


class TestInjectRules:
    def test_inject_and_cleanup(self, tmp_path):
        w = CliStreamWorker(workdir=tmp_path, keep_rules=False)
        rules_file = tmp_path / ".clinerules"

        w._inject_rules("You are helpful.")
        assert rules_file.exists()
        assert rules_file.read_text() == "You are helpful."

        w._cleanup_rules()
        assert not rules_file.exists()

    def test_keep_rules(self, tmp_path):
        w = CliStreamWorker(workdir=tmp_path, keep_rules=True)
        rules_file = tmp_path / ".clinerules"

        w._inject_rules("Keep me.")
        w._cleanup_rules()
        assert rules_file.exists()
        assert rules_file.read_text() == "Keep me."

    def test_empty_prompt_no_file(self, tmp_path):
        w = CliStreamWorker(workdir=tmp_path)
        rules_file = tmp_path / ".clinerules"

        w._inject_rules("")
        assert not rules_file.exists()


class TestBuildCommand:
    def test_minimal(self, tmp_path):
        w = CliStreamWorker(workdir=tmp_path)
        rc = RoleConfig(name="test")
        cmd = w._build_command(rc, "Do something")
        assert cmd == [
            "cline",
            "--auto-approve", "true",
            "--thinking", "none",
            "Do something",
        ]

    def test_custom_model(self, tmp_path):
        w = CliStreamWorker(workdir=tmp_path)
        rc = RoleConfig(name="test", model="claude-sonnet-4-20250514")
        cmd = w._build_command(rc, "Do something")
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "claude-sonnet-4-20250514"

    def test_plan_mode(self, tmp_path):
        w = CliStreamWorker(workdir=tmp_path)
        rc = RoleConfig(name="test", plan_mode=True)
        cmd = w._build_command(rc, "Do something")
        assert "-p" in cmd

    def test_extra_args(self, tmp_path):
        w = CliStreamWorker(workdir=tmp_path)
        rc = RoleConfig(name="test", extra_args=["--verbose", "--debug"])
        cmd = w._build_command(rc, "Do something")
        assert "--verbose" in cmd
        assert "--debug" in cmd

    def test_all_flags(self, tmp_path):
        w = CliStreamWorker(workdir=tmp_path)
        rc = RoleConfig(
            name="full",
            model="claude-opus-4-20250514",
            plan_mode=True,
            extra_args=["--verbose"],
        )
        cmd = w._build_command(rc, "Full test")
        assert "cline" == cmd[0]
        assert "--auto-approve" in cmd
        assert "--thinking" in cmd
        assert "--model" in cmd
        assert "-p" in cmd
        assert "--verbose" in cmd
        assert "Full test" in cmd


class TestDictToRoleConfig:
    def test_minimal_dict(self, tmp_path):
        w = CliStreamWorker(workdir=tmp_path)
        rc = w._dict_to_role_config({"name": "test"})
        assert rc.name == "test"
        assert rc.model == DEFAULT_MODEL

    def test_full_dict(self, tmp_path):
        w = CliStreamWorker(workdir=tmp_path)
        rc = w._dict_to_role_config({
            "name": "reviewer",
            "system_prompt": "Review code",
            "model": "claude-sonnet",
            "plan_mode": True,
            "extra_args": ["--verbose"],
        })
        assert rc.name == "reviewer"
        assert rc.system_prompt == "Review code"
        assert rc.model == "claude-sonnet"
        assert rc.plan_mode is True
        assert rc.extra_args == ["--verbose"]

    def test_empty_dict(self, tmp_path):
        w = CliStreamWorker(workdir=tmp_path)
        rc = w._dict_to_role_config({})
        assert rc.name == "unnamed"


class TestExecuteRole:
    def test_execute_role_returns_string(self, tmp_path):
        """Test execute_role with a mocked subprocess."""
        w = CliStreamWorker(workdir=tmp_path)

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.readline = MagicMock(side_effect=["hello\n", "world\n", ""])
        mock_proc.wait = MagicMock(return_value=0)

        with patch.object(w, "_spawn", return_value=mock_proc):
            result = w.execute_role(
                {"name": "test", "system_prompt": "Be helpful"},
                "Say hello",
            )
            assert result == "hello\nworld\n"

    def test_execute_role_failure(self, tmp_path):
        w = CliStreamWorker(workdir=tmp_path)

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.readline = MagicMock(side_effect=["error\n", ""])
        mock_proc.wait = MagicMock(return_value=1)

        with patch.object(w, "_spawn", return_value=mock_proc):
            result = w.execute_role(
                {"name": "failing-role"},
                "This will fail",
            )
            assert result == "error\n"
