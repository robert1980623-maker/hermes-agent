# Code Review Checklist

Use this checklist when reviewing PRs to Hermes Agent. Check all applicable boxes.

## Pre-Review

- [ ] PR has a clear description of **what** changed and **why**
- [ ] PR is linked to an issue (or explains why none exists)
- [ ] PR scope is focused — no unrelated changes bundled in
- [ ] Target branch is `main`

## Code Quality

- [ ] New code follows the project's coding standards (type hints, docstrings, naming conventions)
- [ ] No hardcoded `~/.hermes` paths — uses `get_hermes_home()` / `display_hermes_home()`
- [ ] No `simple_term_menu` usage (use `curses` instead)
- [ ] No `\033[K` ANSI escape sequences in display/spinner code
- [ ] Tool handlers return JSON strings
- [ ] Errors are handled gracefully — no silent exception swallowing
- [ ] Cross-tool schema references are added dynamically, not hardcoded
- [ ] Imports are grouped and sorted (stdlib → third-party → local)

## Architecture & Safety

- [ ] Prompt caching is not broken — no mid-conversation context/toolset changes
- [ ] Profile-safe — uses `get_hermes_home()` not `Path.home() / ".hermes"`
- [ ] Working directory behavior is correct for both CLI and messaging modes
- [ ] No new supply chain risk — dependencies are pinned to known-good ranges
- [ ] API keys and secrets are not committed or logged

## Testing

- [ ] Tests are included for bug fixes and new features
- [ ] Tests do NOT hit real APIs (all API keys are unset in CI)
- [ ] Tests do NOT write to `~/.hermes/` (use `_isolate_hermes_home` fixture)
- [ ] New tool tests cover the `check_requirements()` path
- [ ] Profile tests mock both `HERMES_HOME` and `Path.home()`
- [ ] All existing tests still pass: `python -m pytest tests/ -q --ignore=tests/integration --ignore=tests/e2e`

## Documentation

- [ ] Relevant documentation is updated (README, AGENTS.md, CONTRIBUTING.md, docstrings)
- [ ] `cli-config.yaml.example` is updated if config keys were added/changed
- [ ] Tool schemas/descriptions are updated if tool behavior changed
- [ ] `AGENTS.md` or `CONTRIBUTING.md` is updated if architecture or workflows changed
- [ ] New skills follow the SKILL.md standard format (frontmatter, triggers, steps, pitfalls)

## Slash Commands (if applicable)

- [ ] `CommandDef` added to `COMMAND_REGISTRY` in `hermes_cli/commands.py`
- [ ] Handler added in `cli.py` `process_command()`
- [ ] Handler added in `gateway/run.py` (if gateway-accessible)
- [ ] Category is correct (`Session`, `Configuration`, `Tools & Skills`, `Info`, `Exit`)

## Tools (if applicable)

- [ ] Tool file created in `tools/`
- [ ] Tool registered via `registry.register()` with proper schema
- [ ] Tool imported in `model_tools.py` `_discover_tools()`
- [ ] Tool added to appropriate toolset in `toolsets.py`
- [ ] `check_requirements()` implemented
- [ ] `requires_env` lists all required environment variables

## Platform Compatibility

- [ ] Change works on Linux and macOS
- [ ] Windows impact considered (or marked N/A)
- [ ] No platform-specific assumptions without guards

## Final

- [ ] CI checks pass (tests, docs, supply chain)
- [ ] Commit messages follow Conventional Commits format
- [ ] PR is ready to merge
