"""
Tests for dispatch-mode task card rendering.

Covers:
  - Dispatch start event → header + agent rows + footer
  - Multi-agent progress updates
  - Subtask completion
  - Slack block count limits
"""

import pytest
import json
import sys
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from protocol.protocol import (
    EventPayload,
    SubAgentInfo,
    build_progress_bar,
    get_agent_emoji,
    make_dispatch_start,
    make_subtask_progress,
    make_subtask_done,
    make_complete,
)
from gateway.renderer import (
    build_task_card,
    build_dispatch_header,
    build_dispatch_agents,
    build_footer,
    build_progress_blocks,
    MAX_SLACK_BLOCKS,
    COMPACT_FULL,
    COMPACT_GRID,
)
from gateway.slack_dispatch import DispatchProcessor, DispatchTaskState


# ===================================================================
# Protocol tests
# ===================================================================


class TestSubAgentInfo:
    def test_emoji_mapping(self):
        assert SubAgentInfo(role="db").emoji == "🤖"
        assert SubAgentInfo(role="tests").emoji == "🧪"
        assert SubAgentInfo(role="docker").emoji == "🐳"
        assert SubAgentInfo(role="docs").emoji == "📝"
        assert SubAgentInfo(role="search").emoji == "🔍"
        assert SubAgentInfo(role="unknown_role").emoji == "🤖"

    def test_serialization_roundtrip(self):
        agent = SubAgentInfo(
            agent_id="agent_0",
            role="tests",
            task="Run unit tests",
            progress=45.0,
            status="running",
            current_action="pytest -x",
        )
        d = agent.to_dict()
        restored = SubAgentInfo.from_dict(d)
        assert restored.agent_id == agent.agent_id
        assert restored.role == agent.role
        assert restored.progress == agent.progress


class TestEventPayload:
    def test_dispatch_start_payload(self):
        agents = [
            SubAgentInfo(agent_id="db_0", role="db", task="Schema migration"),
            SubAgentInfo(agent_id="test_0", role="tests", task="Run tests"),
        ]
        payload = make_dispatch_start(task="Refactor + Test", agents=agents)
        assert payload.task_type == "dispatch"
        assert payload.event_type == "start"
        assert payload.total_agents == 2
        assert len(payload.agents) == 2

    def test_json_roundtrip(self):
        payload = make_subtask_progress(
            task_id="task_1",
            subtask_id="db_0",
            agent_id="db_0",
            role="db",
            progress=60.0,
            current_action="Running migration",
            tool_name="execute_sql",
            tool_args={"query": "ALTER TABLE..."},
        )
        raw = payload.to_json()
        restored = EventPayload.from_json(raw)
        assert restored.task_id == "task_1"
        assert restored.subtask_id == "db_0"
        assert restored.progress == 60.0
        assert restored.tool_name == "execute_sql"


class TestProgressBar:
    def test_full_bar(self):
        assert build_progress_bar(100.0, 10) == "[██████████]"

    def test_empty_bar(self):
        assert build_progress_bar(0.0, 10) == "[░░░░░░░░░░]"

    def test_half_bar(self):
        assert build_progress_bar(50.0, 10) == "[█████░░░░░]"

    def test_clamped(self):
        assert build_progress_bar(150.0, 5) == "[█████]"
        assert build_progress_bar(-10.0, 5) == "[░░░░░]"


# ===================================================================
# Renderer tests
# ===================================================================


class TestBuildTaskCard_DispatchStart:
    """Test rendering of a dispatch-start event card."""

    def _make_start_event(self) -> EventPayload:
        return make_dispatch_start(
            task_id="task_dispatch_1",
            task="Full pipeline: DB → Tests → Docker",
            agents=[
                SubAgentInfo(agent_id="db_0", role="db", task="Run migrations", progress=0.0, status="running"),
                SubAgentInfo(agent_id="test_0", role="tests", task="Run test suite", progress=0.0, status="running"),
                SubAgentInfo(agent_id="docker_0", role="docker", task="Build image", progress=0.0, status="running"),
            ],
        )

    def test_has_header(self):
        event = self._make_start_event()
        card = build_task_card(event)
        blocks = card["blocks"]
        # First block should be a header
        assert blocks[0]["type"] == "header"
        assert "Full pipeline" in blocks[0]["text"]["text"]

    def test_has_progress_bar_in_header(self):
        event = self._make_start_event()
        card = build_task_card(event)
        # Second block should show progress
        section_texts = [
            b["text"]["text"] for b in card["blocks"] if b["type"] == "section"
        ]
        assert any("0%" in t for t in section_texts)

    def test_has_agent_rows(self):
        event = self._make_start_event()
        card = build_task_card(event)
        # Should have 3 agent rows
        agent_blocks = build_dispatch_agents(event)
        assert len(agent_blocks) == 3

    def test_agent_emojis_correct(self):
        event = self._make_start_event()
        agent_blocks = build_dispatch_agents(event)
        texts = [b["text"]["text"] for b in agent_blocks]
        assert any("🤖" in t for t in texts)  # db agent
        assert any("🧪" in t for t in texts)  # tests agent
        assert any("🐳" in t for t in texts)  # docker agent

    def test_footer_shows_agent_count(self):
        event = self._make_start_event()
        card = build_task_card(event)
        footer_blocks = build_footer(event)
        footer_text = footer_blocks[-1]["elements"][0]["text"]
        assert "3 agents active" in footer_text

    def test_block_count_under_limit(self):
        event = self._make_start_event()
        card = build_task_card(event)
        assert len(card["blocks"]) <= MAX_SLACK_BLOCKS

    def test_has_plain_text_fallback(self):
        event = self._make_start_event()
        card = build_task_card(event)
        assert "text" in card
        assert isinstance(card["text"], str)
        assert len(card["text"]) > 0


class TestBuildTaskCard_MultiAgentProgress:
    """Test rendering when agents have varying progress."""

    def _make_progress_event(self) -> EventPayload:
        return EventPayload(
            event_type="progress",
            task_id="task_dispatch_1",
            task_type="dispatch",
            task="Full pipeline: DB → Tests → Docker",
            total_agents=3,
            agents=[
                SubAgentInfo(agent_id="db_0", role="db", task="Run migrations", progress=100.0, status="done", current_action="completed"),
                SubAgentInfo(agent_id="test_0", role="tests", task="Run test suite", progress=40.0, status="running", current_action="pytest -x"),
                SubAgentInfo(agent_id="docker_0", role="docker", task="Build image", progress=10.0, status="running", current_action="docker build"),
            ],
            subtask_id="test_0",
            progress=50.0,
        )

    def test_progress_bars_reflect_state(self):
        event = self._make_progress_event()
        agent_blocks = build_dispatch_agents(event)
        texts = [b["text"]["text"] for b in agent_blocks]
        # DB agent should show 100%
        assert any("100%" in t for t in texts)
        # Tests agent should show 40%
        assert any("40%" in t for t in texts)
        # Docker agent should show 10%
        assert any("10%" in t for t in texts)

    def test_shows_current_actions(self):
        event = self._make_progress_event()
        card = build_task_card(event)
        all_text = " ".join(b.get("text", {}).get("text", "") for b in card["blocks"])
        assert "pytest -x" in all_text
        assert "docker build" in all_text

    def test_footer_shows_mixed_status(self):
        event = self._make_progress_event()
        footer_blocks = build_footer(event)
        footer_text = footer_blocks[-1]["elements"][0]["text"]
        assert "1 done" in footer_text
        assert "2 agents active" in footer_text

    def test_tool_call_shown_for_subtask(self):
        event = self._make_progress_event()
        event.tool_name = "run_tests"
        event.tool_args = {"suite": "unit"}
        event.subtask_id = "test_0"
        card = build_task_card(event)
        # Find context blocks
        context_blocks = [b for b in card["blocks"] if b["type"] == "context"]
        assert len(context_blocks) > 0
        # Tool name should appear somewhere
        all_text = " ".join(
            e.get("text", "") for b in context_blocks for e in b.get("elements", [])
        )
        assert "run_tests" in all_text


class TestBuildTaskCard_SubtaskDone:
    """Test rendering when a subtask is marked done."""

    def _make_done_event(self) -> EventPayload:
        return EventPayload(
            event_type="progress",
            task_id="task_dispatch_1",
            task_type="dispatch",
            task="Full pipeline: DB → Tests → Docker",
            total_agents=3,
            agents=[
                SubAgentInfo(agent_id="db_0", role="db", task="Run migrations", progress=100.0, status="done"),
                SubAgentInfo(agent_id="test_0", role="tests", task="Run test suite", progress=100.0, status="done"),
                SubAgentInfo(agent_id="docker_0", role="docker", task="Build image", progress=75.0, status="running", current_action="pushing"),
            ],
        )

    def test_done_agents_show_checkmark(self):
        event = self._make_done_event()
        agent_blocks = build_dispatch_agents(event)
        texts = [b["text"]["text"] for b in agent_blocks]
        # Done agents should have ✅
        done_texts = [t for t in texts if "100%" in t]
        assert all("✅" in t for t in done_texts)

    def test_footer_shows_done_count(self):
        event = self._make_done_event()
        footer_blocks = build_footer(event)
        footer_text = footer_blocks[-1]["elements"][0]["text"]
        assert "2 done" in footer_text
        assert "1 agent active" in footer_text


# ===================================================================
# Slack dispatch processor tests
# ===================================================================


class TestDispatchProcessor:
    def test_start_creates_state(self):
        proc = DispatchProcessor()
        event = make_dispatch_start(
            task_id="t1",
            task="Test task",
            agents=[SubAgentInfo(agent_id="a1", role="db", progress=0.0)],
        )
        result = proc.handle_event(event)
        assert result["action"] == "send"
        assert "blocks" in result
        state = proc.get_state("t1")
        assert state is not None
        assert len(state.agents) == 1

    def test_progress_updates_agent(self):
        proc = DispatchProcessor()
        start_event = make_dispatch_start(
            task_id="t1",
            task="Test task",
            agents=[SubAgentInfo(agent_id="a1", role="db", progress=0.0, status="running")],
        )
        proc.handle_event(start_event)

        progress_event = make_subtask_progress(
            task_id="t1",
            subtask_id="a1",
            agent_id="a1",
            role="db",
            progress=50.0,
            current_action="Working...",
        )
        result = proc.handle_event(progress_event)
        assert result["action"] == "edit"

        state = proc.get_state("t1")
        assert state.agents["a1"].progress == 50.0
        assert state.agents["a1"].current_action == "Working..."

    def test_subtask_done_marks_agent(self):
        proc = DispatchProcessor()
        start_event = make_dispatch_start(
            task_id="t1",
            task="Test task",
            agents=[SubAgentInfo(agent_id="a1", role="tests", progress=0.0)],
        )
        proc.handle_event(start_event)

        done_event = make_subtask_done(
            task_id="t1",
            subtask_id="a1",
            agent_id="a1",
            result="All tests passed",
        )
        result = proc.handle_event(done_event)
        assert result["action"] == "edit"

        state = proc.get_state("t1")
        assert state.agents["a1"].status == "done"
        assert state.agents["a1"].progress == 100.0

    def test_complete_finalizes_all(self):
        proc = DispatchProcessor()
        start_event = make_dispatch_start(
            task_id="t1",
            task="Test task",
            agents=[
                SubAgentInfo(agent_id="a1", role="db", progress=80.0, status="running"),
                SubAgentInfo(agent_id="a2", role="tests", progress=0.0, status="running"),
            ],
        )
        proc.handle_event(start_event)

        complete_event = make_complete(task_id="t1", task_type="dispatch", result="All done")
        result = proc.handle_event(complete_event)
        assert result["action"] == "edit"

        # State should be removed after completion
        assert proc.get_state("t1") is None

    def test_register_message_ts(self):
        proc = DispatchProcessor()
        start_event = make_dispatch_start(
            task_id="t1",
            task="Test task",
            agents=[SubAgentInfo(agent_id="a1", role="db")],
        )
        proc.handle_event(start_event)
        proc.register_message_ts("t1", "1234567890.123456", "C123456")
        state = proc.get_state("t1")
        assert state.message_ts == "1234567890.123456"
        assert state.channel_id == "C123456"

    def test_unknown_task_returns_noop(self):
        proc = DispatchProcessor()
        event = make_subtask_progress(task_id="nonexistent", subtask_id="a1")
        result = proc.handle_event(event)
        assert result["action"] == "noop"

    def test_non_dispatch_returns_noop(self):
        proc = DispatchProcessor()
        event = EventPayload(event_type="progress", task_type="single", task_id="x")
        result = proc.handle_event(event)
        assert result["action"] == "noop"


# ===================================================================
# Block limit tests
# ===================================================================


class TestBlockLimits:
    def test_many_agents_truncated(self):
        """With 60 agents, the card should stay under 50 blocks."""
        agents = [
            SubAgentInfo(
                agent_id=f"agent_{i}",
                role="default",
                task=f"Task {i}",
                progress=float(i),
            )
            for i in range(60)
        ]
        event = make_dispatch_start(task="Huge dispatch", agents=agents)
        card = build_task_card(event)
        assert len(card["blocks"]) <= MAX_SLACK_BLOCKS


# ===================================================================
# Compact mode tests
# ===================================================================


class TestBuildTaskCard_CompactGrid:
    """Test rendering with 8 agents (Level 2: grid format, 6-15 agents)."""

    def _make_grid_event(self) -> EventPayload:
        roles = ["db", "tests", "docker", "docs", "search", "db", "tests", "docker"]
        agents = [
            SubAgentInfo(
                agent_id=f"agent_{i}",
                role=roles[i],
                task=f"Task {i}",
                progress=float((i + 1) * 10),
                status="running",
                current_action=f"Working on {i}",
            )
            for i in range(8)
        ]
        return make_dispatch_start(task="Grid mode dispatch", agents=agents)

    def test_uses_grid_format(self):
        """8 agents should produce grid-style blocks (not one per agent)."""
        event = self._make_grid_event()
        agent_blocks = build_dispatch_agents(event)
        # With 8 agents in grid (3 per line), we get 3 lines: 3+3+2
        assert len(agent_blocks) == 3

    def test_grid_contains_agent_labels(self):
        """Grid blocks should contain compact agent labels with percentages."""
        event = self._make_grid_event()
        agent_blocks = build_dispatch_agents(event)
        all_text = " ".join(b["text"]["text"] for b in agent_blocks)
        # Should contain compact labels like "A [10%]", "B [20%]", etc.
        assert "[10%]" in all_text
        assert "[80%]" in all_text
        # Should have pipe separators between columns
        assert " | " in all_text

    def test_grid_has_status_icons(self):
        """Grid entries should include status icons."""
        event = self._make_grid_event()
        agent_blocks = build_dispatch_agents(event)
        all_text = " ".join(b["text"]["text"] for b in agent_blocks)
        assert "⏳" in all_text

    def test_grid_block_count_under_limit(self):
        """Grid mode should produce far fewer blocks than agent count."""
        event = self._make_grid_event()
        card = build_task_card(event)
        assert len(card["blocks"]) <= MAX_SLACK_BLOCKS
        # Grid with 8 agents: header(3) + grid(3) + footer(2) = ~8 blocks
        assert len(card["blocks"]) < 50

    def test_mixed_status_in_grid(self):
        """Grid should render agents with different statuses."""
        agents = [
            SubAgentInfo(agent_id=f"a{i}", role="db", progress=float(i * 20),
                         status="done" if i < 2 else "running")
            for i in range(6)
        ]
        event = make_dispatch_start(task="Mixed grid", agents=agents)
        agent_blocks = build_dispatch_agents(event)
        all_text = " ".join(b["text"]["text"] for b in agent_blocks)
        assert "✅" in all_text  # done agents
        assert "⏳" in all_text  # running agents


class TestBuildTaskCard_CompactSummary:
    """Test rendering with 20 agents (Level 3: summary only, >15 agents)."""

    def _make_summary_event(self) -> EventPayload:
        agents = []
        for i in range(20):
            if i < 5:
                status = "done"
                progress = 100.0
            elif i < 17:
                status = "running"
                progress = float(i * 5)
            else:
                status = "error"
                progress = float(i * 3)
            agents.append(
                SubAgentInfo(
                    agent_id=f"agent_{i}",
                    role="default",
                    task=f"Task {i}",
                    progress=progress,
                    status=status,
                )
            )
        return make_dispatch_start(task="Summary mode dispatch", agents=agents)

    def test_uses_summary_format(self):
        """20 agents should produce only summary blocks, not per-agent rows."""
        event = self._make_summary_event()
        agent_blocks = build_dispatch_agents(event)
        # Summary mode: 1 section block + 1 context block = 2 blocks
        assert len(agent_blocks) == 2

    def test_summary_shows_counts(self):
        """Summary should display done/running/error counts."""
        event = self._make_summary_event()
        agent_blocks = build_dispatch_agents(event)
        summary_text = agent_blocks[0]["text"]["text"]
        assert "✅ 5 done" in summary_text
        assert "⏳ 12 running" in summary_text
        assert "❌ 3 error" in summary_text

    def test_summary_shows_view_details_link(self):
        """Summary should include a 'View details in thread' link."""
        event = self._make_summary_event()
        agent_blocks = build_dispatch_agents(event)
        context_blocks = [b for b in agent_blocks if b["type"] == "context"]
        assert len(context_blocks) == 1
        link_text = context_blocks[0]["elements"][0]["text"]
        assert "View details in thread" in link_text

    def test_summary_block_count_under_limit(self):
        """Summary mode should produce very few blocks regardless of agent count."""
        event = self._make_summary_event()
        card = build_task_card(event)
        assert len(card["blocks"]) <= MAX_SLACK_BLOCKS
        # Summary with 20 agents: header(3) + summary(2) + footer(2) = ~7 blocks
        assert len(card["blocks"]) < 50

    def test_very_large_agent_count(self):
        """Even with 100 agents, summary mode should stay well under 50 blocks."""
        agents = [
            SubAgentInfo(
                agent_id=f"agent_{i}",
                role="default",
                task=f"Task {i}",
                progress=float(i),
                status="running",
            )
            for i in range(100)
        ]
        event = make_dispatch_start(task="Massive dispatch", agents=agents)
        card = build_task_card(event)
        assert len(card["blocks"]) <= MAX_SLACK_BLOCKS
        assert len(card["blocks"]) < 50
