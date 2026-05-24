# Hermes Agent — Coding Agent Guide

**For AI coding assistants** (Cline, Claude Code, Codex, Cursor) and human developers working on this codebase.

> **Read this first.** It covers architecture, workflows, standards, testing rules, and known pitfalls.
> If you skip this, you will break prompt caching, profiles, or tests.

---

## Quick Reference for AI Agents

| You want to… | Do this |
|--------------|---------|
| Add a tool | Create `tools/name.py`, register via `registry.register()`, import in `model_tools.py`, add to `toolsets.py` |
| Add a slash command | Add `CommandDef` to `COMMAND_REGISTRY` in `hermes_cli/commands.py`, add handler in `cli.py` + `gateway/run.py` |
| Add a config key | Add to `DEFAULT_CONFIG` or `OPTIONAL_ENV_VARS` in `hermes_cli/config.py` |
| Add a skin | Add entry to `_BUILTIN_SKINS` in `hermes_cli/skin_engine.py` |
| Write a test | Use `tests/conftest.py` fixtures — NEVER hit real APIs, NEVER write to `~/.hermes/` |
| Use a path | `get_hermes_home()` for code, `display_hermes_home()` for user messages — NEVER hardcode `~/.hermes` |

---

## Project Architecture

### Portal–Daemon–CLI Pattern

Hermes Agent operates as the **Portal** — the central orchestrator that manages conversations, memory, tools, and skills. External agents and interfaces connect to it:

| Component | Role | Examples |
|-----------|------|----------|
| **Portal** (this repo) | Core agent loop, tool dispatch, session management, memory, skills | `run_agent.py`, `cli.py`, `gateway/run.py` |
| **Daemon** | Long-running background processes with persistent state | Messaging gateway (`gateway/`), cron scheduler (`cron/`), ACP server (`acp_adapter/`) |
| **CLI** | User-facing command interface | `hermes_cli/` subcommands (`hermes model`, `hermes setup`, `hermes tools`) |
| **External Agents** | Code execution agents that Hermes delegates to | Cline, Claude Code, Codex — connected via ACP or terminal tools |

### Core Conversation Loop

The agent loop lives in `AIAgent.run_conversation()` (`run_agent.py`) — entirely synchronous:

```python
while api_call_count < self.max_iterations and self.iteration_budget.remaining > 0:
    response = client.chat.completions.create(model=model, messages=messages, tools=tool_schemas)
    if response.tool_calls:
        for tool_call in response.tool_calls:
            result = handle_function_call(tool_call.name, tool_call.args, task_id)
            messages.append(tool_result_message(result))
        api_call_count += 1
    else:
        return response.content
```

Messages follow OpenAI format: `{"role": "system/user/assistant/tool", ...}`. Reasoning content is stored in `assistant_msg["reasoning"]`.

---

## File Structure & Responsibilities

```
hermes-agent/
├── run_agent.py            # AIAgent class — core conversation loop
├── model_tools.py          # Tool orchestration: _discover_tools(), handle_function_call()
├── toolsets.py             # Toolset definitions, _HERMES_CORE_TOOLS list
├── cli.py                  # HermesCLI — interactive CLI orchestrator
├── hermes_state.py         # SessionDB — SQLite session store (FTS5 search)
├── hermes_constants.py     # get_hermes_home(), display_hermes_home() — USE THESE
│
├── agent/                  # Agent internals
│   ├── prompt_builder.py       # System prompt assembly
│   ├── context_compressor.py   # Auto context compression
│   ├── prompt_caching.py       # Anthropic prompt caching
│   ├── memory_manager.py       # Memory operations
│   ├── skill_commands.py       # Skill slash commands (shared CLI/gateway)
│   ├── display.py              # KawaiiSpinner, tool preview formatting
│   └── trajectory.py           # Trajectory saving helpers
│
├── hermes_cli/             # CLI subcommands
│   ├── main.py                 # Entry point — all `hermes` subcommands
│   ├── config.py               # DEFAULT_CONFIG, OPTIONAL_ENV_VARS, migration
│   ├── commands.py             # Slash command registry (COMMAND_REGISTRY)
│   ├── setup.py                # Interactive setup wizard
│   ├── skin_engine.py          # Skin/theme engine
│   ├── skills_config.py        # hermes skills — enable/disable per platform
│   ├── tools_config.py         # hermes tools — enable/disable per platform
│   └── model_switch.py         # Shared /model switch pipeline
│
├── tools/                  # Tool implementations (one file per tool)
│   ├── registry.py             # Central tool registry (schemas, handlers, dispatch)
│   ├── terminal_tool.py        # Terminal orchestration
│   ├── file_tools.py           # File read/write/search/patch
│   ├── web_tools.py            # Web search/extract (Parallel + Firecrawl)
│   ├── browser_tool.py         # Browserbase browser automation
│   ├── mcp_tool.py             # MCP client
│   ├── delegate_tool.py        # Subagent delegation
│   └── environments/           # Terminal backends (local, docker, ssh, modal, daytona)
│
├── gateway/                # Messaging platform gateway
│   ├── run.py                  # Main loop, slash commands, message dispatch
│   ├── session.py              # SessionStore — conversation persistence
│   └── platforms/              # Adapters: telegram, discord, slack, whatsapp, signal
│
├── acp_adapter/            # ACP server (VS Code / Zed / JetBrains)
├── cron/                   # Scheduler (jobs.py, scheduler.py)
├── environments/           # RL training environments (Atropos)
├── skills/                 # Bundled skills (ship with every install)
├── optional-skills/        # Official skills (not auto-enabled)
└── tests/                  # Pytest suite (~3000 tests)
```

**User config:** `~/.hermes/config.yaml` (settings), `~/.hermes/.env` (API keys)

### File Dependency Chain

```
tools/registry.py  (no deps — imported by all tool files)
       ↑
tools/*.py  (each calls registry.register() at import time)
       ↑
model_tools.py  (imports tools/registry + triggers tool discovery)
       ↑
run_agent.py, cli.py, batch_runner.py, environments/
```

---

## Development Workflow

### Adding a Tool (3 files)

**1. Create `tools/your_tool.py`:**
```python
import json, os
from tools.registry import registry

def check_requirements() -> bool:
    return bool(os.getenv("EXAMPLE_API_KEY"))

def example_tool(param: str, task_id: str = None) -> str:
    return json.dumps({"success": True, "data": "..."})

registry.register(
    name="example_tool",
    toolset="example",
    schema={"name": "example_tool", "description": "...", "parameters": {...}},
    handler=lambda args, **kw: example_tool(param=args.get("param", ""), task_id=kw.get("task_id")),
    check_fn=check_requirements,
    requires_env=["EXAMPLE_API_KEY"],
)
```

**2.** Add import in `model_tools.py` `_discover_tools()` list.

**3.** Add to `toolsets.py` — either `_HERMES_CORE_TOOLS` or a new toolset.

> **Rules:** Handlers MUST return a JSON string. Use `get_hermes_home()` for state files. Use `display_hermes_home()` in schema descriptions for user-facing paths.

### Adding a Slash Command

1. Add `CommandDef` to `COMMAND_REGISTRY` in `hermes_cli/commands.py`:
   ```python
   CommandDef("mycommand", "Description", "Session", aliases=("mc",), args_hint="[arg]"),
   ```
2. Add handler in `HermesCLI.process_command()` in `cli.py`
3. If gateway-accessible, add handler in `gateway/run.py`

> **Tip:** Adding an alias only requires adding it to the `aliases` tuple — dispatch, help, menus, and autocomplete update automatically.

### Adding Configuration

| Type | Where | Notes |
|------|-------|-------|
| `config.yaml` option | `DEFAULT_CONFIG` in `hermes_cli/config.py` | Bump `_config_version` to trigger migration |
| `.env` variable | `OPTIONAL_ENV_VARS` in `hermes_cli/config.py` | Include metadata: description, prompt, url, category |

### Adding a Skin

Add to `_BUILTIN_SKINS` dict in `hermes_cli/skin_engine.py`:
```python
"mytheme": {
    "name": "mytheme",
    "description": "Short description",
    "colors": { ... },
    "spinner": { ... },
    "branding": { ... },
    "tool_prefix": "┊",
},
```

---

## Coding Standards

| Rule | Detail |
|------|--------|
| **Type hints** | Required on all new function signatures. Use `from typing import Optional, Any` for compatibility |
| **Pydantic** | Use for all config models, settings, and structured data. Version: `pydantic>=2.12` |
| **Docstrings** | Required on public functions and classes. Use Google-style docstrings |
| **Imports** | Group: stdlib → third-party → local. Sort alphabetically within groups |
| **Error handling** | Use `tenacity` for retries. Never swallow exceptions silently |
| **State paths** | ALWAYS use `get_hermes_home()` from `hermes_constants`. NEVER hardcode `~/.hermes` |
| **User-facing paths** | Use `display_hermes_home()` for print/log messages |
| **JSON returns** | All tool handlers MUST return a JSON string |
| **Commit messages** | Follow [Conventional Commits](https://www.conventionalcommits.org/): `fix(scope):`, `feat(scope):` |

### Style Enforcement

The project does not currently enforce a linter via CI, but follow these conventions:
- 4-space indentation (no tabs)
- Max line length: 120 characters (soft limit)
- Use `snake_case` for functions/variables, `PascalCase` for classes
- Use double quotes for strings unless single quotes avoid escaping

---

## Testing Rules

### No-LLM Regression

**NEVER write tests that hit real APIs.** The CI pipeline explicitly unsets all API keys:
```yaml
env:
  OPENROUTER_API_KEY: ""
  OPENAI_API_KEY: ""
  NOUS_API_KEY: ""
```

### Test Isolation

The `_isolate_hermes_home` fixture (in `tests/conftest.py`) redirects `HERMES_HOME` to a temp directory. It also:
- Unsets `OPENROUTER_API_KEY`
- Unsets gateway session env vars
- Resets the plugin singleton

**Never** hardcode `~/.hermes/` paths in tests.

### Profile Testing

When testing profile features, mock both `HERMES_HOME` and `Path.home()`:
```python
@pytest.fixture
def profile_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home
```

### Running Tests

```bash
source venv/bin/activate
python -m pytest tests/ -q                           # Full suite (~3000 tests)
python -m pytest tests/ -q --ignore=tests/integration --ignore=tests/e2e  # Unit only
python -m pytest tests/tools/ -q                      # Tool-level tests
python -m pytest tests/gateway/ -q                    # Gateway tests
python -m pytest tests/test_model_tools.py -q         # Toolset resolution
python -m pytest tests/test_cli_init.py -q            # CLI config loading
```

**Always run the full unit suite before pushing.** Integration and E2E tests are skipped by default.

### Test Timeout

Every test has a 30-second hard timeout (set in `tests/conftest.py`). If your test exceeds this, it will be killed.

---

## CI/CD Pipeline

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| `tests.yml` | Push/PR to `main` | Runs full pytest suite on Python 3.11 (unit + e2e, separate jobs) |
| `docker-publish.yml` | Push to `main`, tags | Builds and publishes Docker image |
| `deploy-site.yml` | Push to `main` | Deploys documentation site |
| `docs-site-checks.yml` | PR to `main` | Validates documentation build |
| `supply-chain-audit.yml` | Push to `main` | Audits dependency supply chain |
| `nix.yml` | Push to `main` | Validates Nix flake build |

**All PRs must pass the `tests` workflow.** The test job runs on `ubuntu-latest` with a 10-minute timeout.

---

## Important Policies

### Prompt Caching Must Not Break

Hermes ensures caching remains valid throughout a conversation. **Do NOT implement changes that would:**
- Alter past context mid-conversation
- Change toolsets mid-conversation
- Reload memories or rebuild system prompts mid-conversation

Cache-breaking dramatically increases costs. The ONLY time we alter context is during context compression.

### Working Directory Behavior

| Mode | Working directory |
|------|------------------|
| CLI | Current directory (`os.getcwd()`) |
| Messaging | `MESSAGING_CWD` env var (default: home directory) |

### Background Process Notifications (Gateway)

When `terminal(background=true, notify_on_complete=true)` is used, the gateway runs a watcher. Control verbosity with `display.background_process_notifications`:
- `all` — running-output updates + final message (default)
- `result` — only the final completion message
- `error` — only the final message when exit code != 0
- `off` — no watcher messages

---

## Profiles: Multi-Instance Support

Hermes supports **profiles** — multiple fully isolated instances, each with its own `HERMES_HOME`.

### Rules for profile-safe code

1. **Use `get_hermes_home()` for all HERMES_HOME paths.** Import from `hermes_constants`.
2. **Use `display_hermes_home()` for user-facing messages.** Import from `hermes_constants`.
3. **Module-level constants are fine** — they cache `get_hermes_home()` at import time, after `_apply_profile_override()` runs.
4. **Tests that mock `Path.home()` must also set `HERMES_HOME`.**
5. **Gateway platform adapters should use token locks** — call `acquire_scoped_lock()` in `connect()` and `release_scoped_lock()` in `disconnect()`.
6. **Profile operations are HOME-anchored, not HERMES_HOME-anchored** — `_get_profiles_root()` returns `Path.home() / ".hermes" / "profiles"`.

---

## Known Pitfalls

| Pitfall | Consequence | Fix |
|---------|------------|-----|
| Hardcoding `~/.hermes` | Breaks all profiles | Use `get_hermes_home()` / `display_hermes_home()` |
| Using `simple_term_menu` | Rendering bugs in tmux/iTerm2 | Use `curses` (stdlib) — see `hermes_cli/tools_config.py` |
| Using `\033[K` in spinner code | Leaks as `?[K` under prompt_toolkit | Use space-padding: `f"\r{line}{' ' * pad}"` |
| Hardcoded cross-tool schema refs | Model hallucinates unavailable tools | Add cross-refs dynamically in `get_tool_definitions()` |
| Writing to `~/.hermes/` in tests | Pollutes real user data | Use `_isolate_hermes_home` fixture |
| Reading `_last_resolved_tool_names` during subagent runs | Stale tool names | Save/restore around child agent runs (see `delegate_tool.py`) |

---

## CommandDef Fields Reference

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Canonical name without slash (e.g. `"background"`) |
| `description` | `str` | Human-readable description |
| `category` | `str` | `"Session"`, `"Configuration"`, `"Tools & Skills"`, `"Info"`, `"Exit"` |
| `aliases` | `tuple` | Alternative names (e.g. `("bg",)`) |
| `args_hint` | `str` | Argument placeholder in help (e.g. `"<prompt>"`) |
| `cli_only` | `bool` | Only available in interactive CLI |
| `gateway_only` | `bool` | Only available in messaging platforms |
| `gateway_config_gate` | `str` | Config dotpath that gates gateway availability |
