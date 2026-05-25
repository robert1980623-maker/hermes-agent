"""Agent framework — BaseAgent and concrete worker implementations."""
from __future__ import annotations

from .base import BaseAgent, AgentResult
from .deep_agent_worker import DeepAgentWorker
from .system_worker import SystemWorker

__all__ = ["BaseAgent", "AgentResult", "DeepAgentWorker", "SystemWorker"]
