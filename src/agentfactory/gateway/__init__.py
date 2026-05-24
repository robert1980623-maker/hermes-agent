"""AgentFactory Gateway Service.

A plugin-based messaging gateway that manages multiple platform adapters
(Slack, Feishu, etc.) and routes messages to a SupervisorAgent for processing.

Usage:
    from agentfactory.gateway import GatewayApp, ProviderConfig

    config = ProviderConfig(provider="openai", model="gpt-4o")
    gateway = GatewayApp(provider_config=config)
"""

from .core import GatewayApp, ProviderConfig, SupervisorAgent
from .session import SessionContext, SessionManager
from .adapters.base import BaseAdapter

__all__ = [
    "GatewayApp",
    "ProviderConfig",
    "SupervisorAgent",
    "SessionContext",
    "SessionManager",
    "BaseAdapter",
]
