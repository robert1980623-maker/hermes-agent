"""CLI commands for agent management."""
from __future__ import annotations

import click

from hermes_cli.agent_runner import list_agents, get_agent_config, run_agent
from agent.base import BaseAgent, AgentResult


@click.group()
def agent() -> None:
    """Manage and run AI agents."""


@agent.command("list")
def agent_list() -> None:
    """List all configured agents."""
    agents = list_agents()
    if not agents:
        click.echo("No agents configured. Add agents to config.yaml under 'agents:' section.")
        return

    click.echo(f"{'Name':<20} {'Model':<45} {'Toolset':<15} {'Max Iter':<10}")
    click.echo("-" * 90)
    for a in agents:
        click.echo(
            f"{a['name']:<20} {a['model']:<45} "
            f"{a.get('toolset') or '-':<15} {a.get('max_iterations', 30):<10}"
        )


@agent.command()
@click.argument("name")
def info(name: str) -> None:
    """Show details for a specific agent."""
    try:
        config = get_agent_config(name)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)

    click.echo(f"Agent: {name}")
    click.echo(f"  Model:          {config.model}")
    click.echo(f"  Toolset:        {config.toolset or '(core tools)'}")
    click.echo(f"  Allowed Tools:  {', '.join(config.allowed_tools) if config.allowed_tools else '(all from toolset)'}")
    click.echo(f"  Max Iterations: {config.max_iterations}")
    if config.system_prompt:
        click.echo(f"  System Prompt:  {config.system_prompt[:60]}...")
    if config.env_overrides:
        click.echo(f"  Env Overrides:  {config.env_overrides}")
    if config.metadata:
        click.echo(f"  Metadata:       {config.metadata}")


@agent.command()
@click.argument("name")
@click.argument("prompt")
@click.option("--worker-type", "-w", default="deep", type=click.Choice(["deep", "system", "cli"]),
              help="Worker type to use (default: deep)")
@click.option("--output", "-o", type=click.Choice(["text", "json"]), default="text",
              help="Output format (default: text)")
def run(name: str, prompt: str, worker_type: str, output: str) -> None:
    """Run an agent with a prompt."""
    import json

    try:
        result = run_agent(name, prompt, worker_type=worker_type)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)

    if output == "json":
        click.echo(json.dumps({
            "success": result.success,
            "output": result.output,
            "agent_name": result.agent_name,
            "model": result.model,
            "duration_seconds": result.duration_seconds,
            "tool_calls": result.tool_calls,
            "error": result.error,
        }, indent=2))
    else:
        if result.success:
            click.echo(f"[{result.agent_name}] ({result.model}) — {result.duration_seconds:.1f}s")
            click.echo(result.output)
        else:
            click.echo(f"[{result.agent_name}] FAILED ({result.model}) — {result.duration_seconds:.1f}s", err=True)
            if result.error:
                click.echo(f"Error: {result.error}", err=True)
            if result.output:
                click.echo(result.output, err=True)
            raise SystemExit(1)
