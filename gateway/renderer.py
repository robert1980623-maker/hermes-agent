"""
Task Card Renderer

Builds Slack Block Kit message cards from EventPayload objects.
Supports both single-agent and dispatch (multi-agent) modes.

Dispatch mode renders:
  - A compact header showing overall task progress
  - A per-agent row with emoji, progress bar, and current action
  - Tool call blocks for specific subtasks
  - A footer showing agent count and status

Slack Block Kit limit: max 50 blocks per message.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from protocol.protocol import (
    EventPayload,
    SubAgentInfo,
    build_progress_bar,
    get_agent_emoji,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SLACK_BLOCKS = 50
PROGRESS_BAR_WIDTH = 10

# Status icons
STATUS_ICONS = {
    "running": "⏳",
    "done": "✅",
    "error": "❌",
}

# ---------------------------------------------------------------------------
# Block builders
# ---------------------------------------------------------------------------


def _section_block(text: str) -> Dict[str, Any]:
    """Create a mrkdwn section block."""
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _divider_block() -> Dict[str, Any]:
    """Create a divider block."""
    return {"type": "divider"}


def _context_block(elements: List[Dict[str, str]]) -> Dict[str, Any]:
    """Create a context block."""
    return {"type": "context", "elements": elements}


def _text_element(text: str) -> Dict[str, str]:
    """Create a mrkdwn text element for context blocks."""
    return {"type": "mrkdwn", "text": text}


def _header_block(text: str) -> Dict[str, Any]:
    """Create a header block."""
    return {"type": "header", "text": {"type": "plain_text", "text": text, "emoji": True}}


# Compact mode thresholds
COMPACT_FULL = 5       # Level 1: full rows (≤5 agents)
COMPACT_GRID = 15      # Level 2: grid format (6-15 agents)
                       # Level 3: summary only (>15 agents)


def _build_agent_row(agent: SubAgentInfo, index: int) -> str:
    """Build a single-line representation of a sub-agent's state."""
    emoji = agent.emoji
    label = f"Agent {chr(65 + index)}" if index < 26 else f"Agent #{index + 1}"
    bar = build_progress_bar(agent.progress, PROGRESS_BAR_WIDTH)
    pct = int(agent.progress)
    status_icon = STATUS_ICONS.get(agent.status, "⏳")

    parts = [f"{emoji} *{label}* {bar} {pct}%"]
    if agent.current_action:
        parts.append(f"_{agent.current_action}_")
    if agent.status == "done":
        parts[-1] = parts[-1] + " ✅"
    elif agent.status == "error":
        parts[-1] = parts[-1] + " ❌"

    return " ".join(parts)


def _build_agent_compact_label(agent: SubAgentInfo, index: int) -> str:
    """Build a short label for grid/compact mode (single letter + percentage)."""
    emoji = agent.emoji
    short_label = chr(65 + index) if index < 26 else f"#{index + 1}"
    pct = int(agent.progress)
    return f"{emoji} {short_label} [{pct}%]"


# ---------------------------------------------------------------------------
# Dispatch mode blocks
# ---------------------------------------------------------------------------


def build_dispatch_header(event: EventPayload) -> List[Dict[str, Any]]:
    """
    Build the header block(s) for a dispatch-mode task card.

    Shows:
      - Task title
      - Overall progress (average of all agents)
      - Total agent count
    """
    blocks: List[Dict[str, Any]] = []

    # Compute overall progress from agents
    if event.agents:
        overall = sum(a.progress for a in event.agents) / len(event.agents)
    else:
        overall = event.progress

    pct = int(overall)
    bar = build_progress_bar(overall, PROGRESS_BAR_WIDTH)
    total = event.total_agents or len(event.agents)

    # Header with task name
    blocks.append(_header_block(f"📋 {event.task or 'Multi-Agent Task'}"))

    # Progress line
    blocks.append(
        _section_block(
            f"{bar} *{pct}%*  •  {total} agent{'s' if total != 1 else ''}"
        )
    )

    blocks.append(_divider_block())
    return blocks


def build_dispatch_agents(event: EventPayload) -> List[Dict[str, Any]]:
    """
    Build compact per-agent rows for a dispatch-mode task.

    Uses a 3-level compact strategy based on agent count:

      Level 1 (≤5 agents): Full rows with progress bars and actions.
          🤖 Agent A [████] 40% ⏳ Creating models

      Level 2 (6-15 agents): Grid format, 3 per line, condensed labels.
          🤖 A [40%] ⏳ | 🧪 B [20%] ⏳ | 🐳 C [10%] ⏳

      Level 3 (>15 agents): Summary only with done/running/error counts.
          ✅ 3 done | ⏳ 12 running | ❌ 2 error
          [View details in thread →]
    """
    blocks: List[Dict[str, Any]] = []
    agents = event.agents
    count = len(agents)

    if count <= COMPACT_FULL:
        # Level 1: full rows
        for i, agent in enumerate(agents):
            row = _build_agent_row(agent, i)
            blocks.append(_section_block(row))

            # If agent has a tool call, show it inline
            if event.tool_name and event.subtask_id == agent.agent_id:
                tool_text = f"🔧 *{event.tool_name}*"
                if event.tool_args:
                    first_key = next(iter(event.tool_args))
                    first_val = str(event.tool_args[first_key])[:60]
                    tool_text += f"\n  `{first_key}: {first_val}`"
                blocks.append(_context_block([_text_element(tool_text)]))

    elif count <= COMPACT_GRID:
        # Level 2: grid format, 3 per line
        grid_cols = 3
        lines: List[str] = []
        current_line: List[str] = []

        for i, agent in enumerate(agents):
            label = _build_agent_compact_label(agent, i)
            status_icon = STATUS_ICONS.get(agent.status, "⏳")
            entry = f"{label} {status_icon}"
            current_line.append(entry)

            if len(current_line) == grid_cols or i == count - 1:
                lines.append(" | ".join(current_line))
                current_line = []

        # Render each grid line as a section block
        for line in lines:
            blocks.append(_section_block(line))

    else:
        # Level 3: summary only
        done_count = sum(1 for a in agents if a.status == "done")
        error_count = sum(1 for a in agents if a.status == "error")
        running_count = count - done_count - error_count

        parts = []
        if done_count > 0:
            parts.append(f"✅ {done_count} done")
        if running_count > 0:
            parts.append(f"⏳ {running_count} running")
        if error_count > 0:
            parts.append(f"❌ {error_count} error")

        summary_text = " | ".join(parts) if parts else "initializing"
        blocks.append(_section_block(summary_text))
        blocks.append(
            _context_block([_text_element("[View details in thread →]")])
        )

    return blocks


# ---------------------------------------------------------------------------
# Single-agent mode blocks (legacy / fallback)
# ---------------------------------------------------------------------------


def build_progress_blocks(event: EventPayload) -> List[Dict[str, Any]]:
    """
    Build progress blocks for the event.

    For dispatch mode: delegates to build_dispatch_agents.
    For single-agent mode: shows a simple progress line + current action.
    """
    if event.task_type == "dispatch":
        return build_dispatch_agents(event)

    # Single-agent mode
    blocks: List[Dict[str, Any]] = []
    bar = build_progress_bar(event.progress, PROGRESS_BAR_WIDTH)
    pct = int(event.progress)

    line = f"{STATUS_ICONS.get(event.status, '⏳')} {bar} *{pct}%*"
    if event.current_action:
        line += f"  •  _{event.current_action}_"
    blocks.append(_section_block(line))

    # Tool call info
    if event.tool_name:
        tool_text = f"🔧 *{event.tool_name}*"
        if event.tool_args:
            first_key = next(iter(event.tool_args))
            first_val = str(event.tool_args[first_key])[:60]
            tool_text += f"\n  `{first_key}: {first_val}`"
        blocks.append(_context_block([_text_element(tool_text)]))

    return blocks


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------


def build_footer(event: EventPayload) -> List[Dict[str, Any]]:
    """Build the footer block(s) for a task card."""
    blocks: List[Dict[str, Any]] = []
    blocks.append(_divider_block())

    if event.task_type == "dispatch":
        total = event.total_agents or len(event.agents)
        done_count = sum(1 for a in event.agents if a.status == "done")
        error_count = sum(1 for a in event.agents if a.status == "error")
        active = total - done_count - error_count

        parts = []
        if active > 0:
            parts.append(f"{active} agent{'s' if active != 1 else ''} active")
        if done_count > 0:
            parts.append(f"{done_count} done")
        if error_count > 0:
            parts.append(f"{error_count} error{'s' if error_count != 1 else ''}")

        status_line = "  •  ".join(parts) if parts else "initializing"
        blocks.append(_context_block([_text_element(f"🤖 {status_line}")]))
    else:
        status_line = f"Status: {event.status}  •  Task ID: `{event.task_id}`"
        blocks.append(_context_block([_text_element(status_line)]))

    return blocks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_task_card(event: EventPayload) -> Dict[str, Any]:
    """
    Build a complete Slack Block Kit message from an EventPayload.

    Returns a dict suitable for slack_sdk's chat_postMessage(blocks=...).
    Respects the 50-block maximum.
    """
    blocks: List[Dict[str, Any]] = []

    if event.task_type == "dispatch":
        blocks.extend(build_dispatch_header(event))
        blocks.extend(build_dispatch_agents(event))
    else:
        # Simple header for single-agent
        if event.task:
            blocks.append(_header_block(f"📋 {event.task}"))
            blocks.append(_divider_block())
        blocks.extend(build_progress_blocks(event))

    blocks.extend(build_footer(event))

    # Enforce Slack's 50-block limit
    if len(blocks) > MAX_SLACK_BLOCKS:
        if event.task_type == "dispatch":
            header = build_dispatch_header(event)
            footer = build_footer(event)
            fixed = len(header) + len(footer)
            # Reserve 1 slot for the truncation note
            max_agents = MAX_SLACK_BLOCKS - fixed - 1
            agent_blocks = build_dispatch_agents(event)[:max_agents]
            # Add truncation note
            truncated_count = len(event.agents) - max_agents
            if truncated_count > 0:
                agent_blocks.append(
                    _context_block([
                        _text_element(f"… and {truncated_count} more agent(s)")
                    ])
                )
            blocks = header + agent_blocks + footer

    return {
        "blocks": blocks,
        "text": _fallback_text(event),  # plain-text fallback for notifications
    }


def _fallback_text(event: EventPayload) -> str:
    """Plain-text fallback for notifications/previews."""
    if event.task_type == "dispatch":
        agents_str = ", ".join(
            f"{a.emoji} {a.role} ({int(a.progress)}%)" for a in event.agents[:5]
        )
        return f"[Dispatch] {event.task or 'Task'} — {agents_str}"
    return f"[{event.status}] {event.task or 'Task'} — {int(event.progress)}%"
