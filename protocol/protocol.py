"""
Gateway Event Protocol

Defines the structured event types exchanged between agents and the gateway,
including support for multi-agent dispatch mode where a single task is split
into multiple sub-agents.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Sub-agent information for dispatch mode
# ---------------------------------------------------------------------------

# Canonical agent-role emoji mapping
AGENT_ROLE_EMOJIS: Dict[str, str] = {
    "db": "🤖",
    "database": "🤖",
    "tests": "🧪",
    "testing": "🧪",
    "docker": "🐳",
    "container": "🐳",
    "docs": "📝",
    "documentation": "📝",
    "search": "🔍",
    "research": "🔍",
    "review": "🔍",
    "default": "🤖",
}


def get_agent_emoji(role: str) -> str:
    """Return the emoji icon for a given agent role."""
    return AGENT_ROLE_EMOJIS.get(role.lower(), AGENT_ROLE_EMOJIS["default"])


@dataclass
class SubAgentInfo:
    """State of a single sub-agent in a dispatch task."""
    agent_id: str = ""
    role: str = "default"
    task: str = ""
    progress: float = 0.0
    status: str = "running"  # "running" | "done" | "error"
    current_action: str = ""

    @property
    def emoji(self) -> str:
        return get_agent_emoji(self.role)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "task": self.task,
            "progress": self.progress,
            "status": self.status,
            "current_action": self.current_action,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubAgentInfo":
        return cls(
            agent_id=data.get("agent_id", ""),
            role=data.get("role", "default"),
            task=data.get("task", ""),
            progress=float(data.get("progress", 0.0)),
            status=data.get("status", "running"),
            current_action=data.get("current_action", ""),
        )


# ---------------------------------------------------------------------------
# Progress bar helpers
# ---------------------------------------------------------------------------

def build_progress_bar(pct: float, width: int = 10) -> str:
    """Build a text progress bar like [████░░░░░░] for the given percentage."""
    pct = max(0.0, min(100.0, pct))
    filled = int(width * pct / 100)
    empty = width - filled
    return "[" + "█" * filled + "░" * empty + "]"


# ---------------------------------------------------------------------------
# Event payload
# ---------------------------------------------------------------------------

@dataclass
class EventPayload:
    """
    Unified event payload for agent ↔ gateway communication.

    Supports both single-agent and dispatch (multi-agent) modes.

    Fields:
        event_type:   "start" | "progress" | "subtask_done" | "complete" | "error"
        task_id:      Unique identifier for the overall task
        task_type:    "single" | "dispatch"
        task:         Human-readable task description
        total_agents: Number of sub-agents (dispatch mode only)
        agents:       List of sub-agent states (dispatch mode only)
        subtask_id:   Identifier for a specific sub-agent's progress update
        agent_id:     ID of the agent that produced this event
        role:         Role of the agent (e.g., "db", "tests", "docker")
        progress:     Overall or per-agent progress (0-100)
        status:       "running" | "done" | "error"
        current_action: What the agent is currently doing
        tool_name:    Name of the tool being called (optional)
        tool_args:    Arguments passed to the tool (optional)
        result:       Result or error message
        timestamp:    Unix timestamp of the event
        metadata:     Arbitrary additional data
    """
    event_type: str = ""
    task_id: str = ""
    task_type: str = "single"  # "single" | "dispatch"
    task: str = ""
    total_agents: int = 0
    agents: List[SubAgentInfo] = field(default_factory=list)
    subtask_id: str = ""
    agent_id: str = ""
    role: str = ""
    progress: float = 0.0
    status: str = "running"
    current_action: str = ""
    tool_name: str = ""
    tool_args: Optional[Dict[str, Any]] = None
    result: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "event_type": self.event_type,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "task": self.task,
            "total_agents": self.total_agents,
            "agents": [a.to_dict() for a in self.agents],
            "subtask_id": self.subtask_id,
            "agent_id": self.agent_id,
            "role": self.role,
            "progress": self.progress,
            "status": self.status,
            "current_action": self.current_action,
            "tool_name": self.tool_name,
            "progress_bar": build_progress_bar(self.progress),
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
        if self.tool_args:
            d["tool_args"] = self.tool_args
        if self.result:
            d["result"] = self.result
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventPayload":
        agents_raw = data.get("agents", [])
        agents = [SubAgentInfo.from_dict(a) for a in agents_raw] if agents_raw else []
        return cls(
            event_type=data.get("event_type", ""),
            task_id=data.get("task_id", ""),
            task_type=data.get("task_type", "single"),
            task=data.get("task", ""),
            total_agents=int(data.get("total_agents", 0)),
            agents=agents,
            subtask_id=data.get("subtask_id", ""),
            agent_id=data.get("agent_id", ""),
            role=data.get("role", ""),
            progress=float(data.get("progress", 0.0)),
            status=data.get("status", "running"),
            current_action=data.get("current_action", ""),
            tool_name=data.get("tool_name", ""),
            tool_args=data.get("tool_args"),
            result=data.get("result", ""),
            timestamp=float(data.get("timestamp", time.time())),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, raw: str) -> "EventPayload":
        return cls.from_dict(json.loads(raw))


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def make_dispatch_start(
    task_id: Optional[str] = None,
    task: str = "",
    agents: Optional[List[SubAgentInfo]] = None,
) -> EventPayload:
    """Create a dispatch-start event."""
    tid = task_id or str(uuid.uuid4())[:8]
    agent_list = agents or []
    return EventPayload(
        event_type="start",
        task_id=tid,
        task_type="dispatch",
        task=task,
        total_agents=len(agent_list),
        agents=agent_list,
        status="running",
    )


def make_subtask_progress(
    task_id: str,
    subtask_id: str,
    agent_id: str = "",
    role: str = "",
    progress: float = 0.0,
    current_action: str = "",
    tool_name: str = "",
    tool_args: Optional[Dict[str, Any]] = None,
) -> EventPayload:
    """Create a progress event for a specific subtask/agent."""
    return EventPayload(
        event_type="progress",
        task_id=task_id,
        task_type="dispatch",
        subtask_id=subtask_id,
        agent_id=agent_id,
        role=role,
        progress=progress,
        status="running",
        current_action=current_action,
        tool_name=tool_name,
        tool_args=tool_args,
    )


def make_subtask_done(
    task_id: str,
    subtask_id: str,
    agent_id: str = "",
    result: str = "",
) -> EventPayload:
    """Create a subtask-completed event."""
    return EventPayload(
        event_type="subtask_done",
        task_id=task_id,
        task_type="dispatch",
        subtask_id=subtask_id,
        agent_id=agent_id,
        status="done",
        progress=100.0,
        result=result,
    )


def make_complete(
    task_id: str,
    task_type: str = "single",
    result: str = "",
) -> EventPayload:
    """Create a task-completed event."""
    return EventPayload(
        event_type="complete",
        task_id=task_id,
        task_type=task_type,
        status="done",
        progress=100.0,
        result=result,
    )
