"""
Slack Dispatch Handler

Manages multi-agent dispatch event flow for Slack:
  - `start` with `task_type: "dispatch"` → creates a new task card
  - `progress` with `subtask_id` → updates specific agent's state
  - `subtask_done` → marks agent done
  - `complete` → finalizes the task

Maintains in-memory task state to track individual agent progress
across events, merging updates into the full agent list.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from protocol.protocol import EventPayload, SubAgentInfo
from gateway.renderer import build_task_card

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory task state
# ---------------------------------------------------------------------------


@dataclass
class DispatchTaskState:
    """Tracks the state of a dispatch-mode task across multiple events."""
    task_id: str = ""
    task: str = ""
    total_agents: int = 0
    agents: Dict[str, SubAgentInfo] = field(default_factory=dict)  # agent_id → info
    message_ts: str = ""  # Slack message ts for edits
    channel_id: str = ""
    created_at: float = field(default_factory=time.time)
    completed: bool = False

    @property
    def agent_list(self) -> List[SubAgentInfo]:
        """Return agents in insertion order."""
        return list(self.agents.values())

    def overall_progress(self) -> float:
        """Calculate overall progress as the mean of all agents."""
        if not self.agents:
            return 0.0
        return sum(a.progress for a in self.agents.values()) / len(self.agents)

    def to_event(self) -> EventPayload:
        """Convert current state back to an EventPayload for rendering."""
        return EventPayload(
            event_type="progress",
            task_id=self.task_id,
            task_type="dispatch",
            task=self.task,
            total_agents=self.total_agents,
            agents=self.agent_list,
            progress=self.overall_progress(),
            status="running" if not self.completed else "done",
        )


# ---------------------------------------------------------------------------
# Dispatch event processor
# ---------------------------------------------------------------------------


class DispatchProcessor:
    """
    Processes dispatch-mode events and manages task state.

    Usage:
        processor = DispatchProcessor()
        card = processor.handle_event(event)
        # card contains the Slack Block Kit payload to send/edit
    """

    def __init__(self):
        # task_id → DispatchTaskState
        self._tasks: Dict[str, DispatchTaskState] = {}

    @property
    def active_tasks(self) -> Dict[str, DispatchTaskState]:
        return {k: v for k, v in self._tasks.items() if not v.completed}

    def handle_event(self, event: EventPayload) -> Dict[str, Any]:
        """
        Process a dispatch event and return a Slack Block Kit payload.

        Returns a dict with:
          - "blocks": Slack Block Kit blocks
          - "text": Plain-text fallback
          - "action": "send" | "edit" | "noop"
          - "message_ts": Slack message ts (for edits)
        """
        if event.task_type != "dispatch":
            return {"action": "noop", "message_ts": ""}

        task_id = event.task_id
        if not task_id:
            logger.warning("[dispatch] Event missing task_id")
            return {"action": "noop", "message_ts": ""}

        if event.event_type == "start":
            return self._handle_start(event)
        elif event.event_type == "progress":
            return self._handle_progress(event)
        elif event.event_type == "subtask_done":
            return self._handle_subtask_done(event)
        elif event.event_type == "complete":
            return self._handle_complete(event)
        else:
            logger.warning("[dispatch] Unknown event type: %s", event.event_type)
            return {"action": "noop", "message_ts": ""}

    def _handle_start(self, event: EventPayload) -> Dict[str, Any]:
        """Handle dispatch start: create task state and initial card."""
        task_id = event.task_id

        state = DispatchTaskState(
            task_id=task_id,
            task=event.task,
            total_agents=event.total_agents or len(event.agents),
        )

        # Register agents from the event
        for agent in event.agents:
            if not agent.agent_id:
                # Generate an ID from role + index
                idx = len(state.agents)
                agent.agent_id = f"{agent.role}_{idx}"
            state.agents[agent.agent_id] = agent

        self._tasks[task_id] = state

        card = build_task_card(event)
        return {
            "action": "send",
            "message_ts": "",
            "blocks": card["blocks"],
            "text": card["text"],
        }

    def _handle_progress(self, event: EventPayload) -> Dict[str, Any]:
        """Handle subtask progress: update specific agent, render card."""
        task_id = event.task_id
        state = self._tasks.get(task_id)
        if not state:
            logger.warning(
                "[dispatch] Progress event for unknown task: %s", task_id
            )
            return {"action": "noop", "message_ts": ""}

        # Identify which agent to update
        agent_id = event.subtask_id or event.agent_id
        if agent_id and agent_id in state.agents:
            agent = state.agents[agent_id]
            if event.progress > 0:
                agent.progress = event.progress
            if event.current_action:
                agent.current_action = event.current_action
            if event.role:
                agent.role = event.role
        elif agent_id:
            # New agent not in the initial list — add it
            agent = SubAgentInfo(
                agent_id=agent_id,
                role=event.role or "default",
                progress=event.progress,
                current_action=event.current_action,
                status="running",
            )
            state.agents[agent_id] = agent

        # Build updated card from current state
        render_event = state.to_event()
        # Propagate tool info to the specific agent for rendering
        render_event.tool_name = event.tool_name
        render_event.tool_args = event.tool_args
        render_event.subtask_id = agent_id

        card = build_task_card(render_event)
        return {
            "action": "edit",
            "message_ts": state.message_ts,
            "blocks": card["blocks"],
            "text": card["text"],
        }

    def _handle_subtask_done(self, event: EventPayload) -> Dict[str, Any]:
        """Handle subtask completion: mark agent done, render card."""
        task_id = event.task_id
        state = self._tasks.get(task_id)
        if not state:
            logger.warning(
                "[dispatch] Subtask_done event for unknown task: %s", task_id
            )
            return {"action": "noop", "message_ts": ""}

        agent_id = event.subtask_id or event.agent_id
        if agent_id and agent_id in state.agents:
            agent = state.agents[agent_id]
            agent.status = "done"
            agent.progress = 100.0
            if event.result:
                agent.current_action = "completed"

        render_event = state.to_event()
        card = build_task_card(render_event)
        return {
            "action": "edit",
            "message_ts": state.message_ts,
            "blocks": card["blocks"],
            "text": card["text"],
        }

    def _handle_complete(self, event: EventPayload) -> Dict[str, Any]:
        """Handle task completion: finalize and render final card."""
        task_id = event.task_id
        state = self._tasks.get(task_id)
        if not state:
            logger.warning(
                "[dispatch] Complete event for unknown task: %s", task_id
            )
            return {"action": "noop", "message_ts": ""}

        state.completed = True
        # Mark all remaining running agents as done
        for agent in state.agents.values():
            if agent.status == "running":
                agent.status = "done"
                agent.progress = 100.0

        render_event = state.to_event()
        render_event.result = event.result
        card = build_task_card(render_event)

        # Clean up
        del self._tasks[task_id]

        return {
            "action": "edit",
            "message_ts": state.message_ts,
            "blocks": card["blocks"],
            "text": card["text"],
        }

    def register_message_ts(self, task_id: str, message_ts: str, channel_id: str = "") -> None:
        """
        Register the Slack message ts after sending a dispatch card.

        Must be called after the initial `send` action so that subsequent
        `edit` actions target the correct message.
        """
        state = self._tasks.get(task_id)
        if state:
            state.message_ts = message_ts
            state.channel_id = channel_id

    def get_state(self, task_id: str) -> Optional[DispatchTaskState]:
        """Get the current state for a task."""
        return self._tasks.get(task_id)
