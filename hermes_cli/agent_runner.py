"""Agent runner — creates workers from config and dispatches them."""
from __future__ import annotations

from typing import Any

from hermes_cli.agent_config import AgentConfig
from hermes_cli.config import load_config
from agent.base import BaseAgent, AgentResult


# Worker type mapping
WORKER_REGISTRY: dict[str, type[BaseAgent]] = {}


def register_worker(name: str, worker_cls: type[BaseAgent]) -> None:
    """Register a worker class by name."""
    WORKER_REGISTRY[name] = worker_cls


# Auto-register built-in workers
def _register_builtin_workers():
    from agent.deep_agent_worker import DeepAgentWorker
    from agent.system_worker import SystemWorker
    from agent.cli_agent_worker import CLIAgentWorker

    register_worker("deep", DeepAgentWorker)
    register_worker("system", SystemWorker)
    register_worker("cli", CLIAgentWorker)


_register_builtin_workers()


def get_agent_config(name: str) -> AgentConfig:
    """Load an agent's config by name from config.yaml.

    Args:
        name: Agent name from config.yaml agents: section.

    Returns:
        AgentConfig for the named agent.

    Raises:
        ValueError: If agent name not found in config.
    """
    config = load_config()
    agents = config.get("agents", {})
    if name not in agents:
        available = ", ".join(agents.keys()) if agents else "(none defined)"
        raise ValueError(f"Agent '{name}' not found. Available: {available}")
    agent_data = agents[name]
    # Ensure 'name' is included for metadata
    if isinstance(agent_data, dict):
        return AgentConfig(**agent_data)
    raise ValueError(f"Invalid config for agent '{name}'")


def list_agents() -> list[dict]:
    """List all configured agents.

    Returns:
        List of dicts with agent name, model, and worker type.
    """
    config = load_config()
    agents = config.get("agents", {})
    result = []
    for name, data in agents.items():
        if isinstance(data, dict):
            result.append({
                "name": name,
                "model": data.get("model", "unknown"),
                "toolset": data.get("toolset"),
                "max_iterations": data.get("max_iterations", 30),
            })
    return result


def create_worker(name: str, worker_type: str = "deep", **kwargs: Any) -> BaseAgent:
    """Create an agent worker by name and type.

    Args:
        name: Agent name (used for display and config lookup).
        worker_type: One of "deep", "system", "cli".
        **kwargs: Additional args passed to the worker constructor.

    Returns:
        A configured BaseAgent instance.
    """
    if worker_type not in WORKER_REGISTRY:
        raise ValueError(
            f"Unknown worker type: {worker_type}. "
            f"Available: {list(WORKER_REGISTRY.keys())}"
        )
    agent_config = get_agent_config(name)
    worker_cls = WORKER_REGISTRY[worker_type]
    return worker_cls(config=agent_config, name=name, **kwargs)


def run_agent(name: str, prompt: str, worker_type: str = "deep", **kwargs: Any) -> AgentResult:
    """Create and run an agent worker.

    Args:
        name: Agent name.
        prompt: Task prompt.
        worker_type: Worker type.
        **kwargs: Additional args for the worker.

    Returns:
        AgentResult from the worker.
    """
    worker = create_worker(name, worker_type, **kwargs)
    return worker.run(prompt)
