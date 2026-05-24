<p align="center">
  <img src="assets/banner.png" alt="Hermes Agent" width="100%">
</p>

# Hermes Agent ☤

<p align="center">
  <a href="https://hermes-agent.nousresearch.com/docs/"><img src="https://img.shields.io/badge/Docs-hermes--agent.nousresearch.com-FFD700?style=for-the-badge" alt="Documentation"></a>
  <a href="https://discord.gg/NousResearch"><img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://github.com/NousResearch/hermes-agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://nousresearch.com"><img src="https://img.shields.io/badge/Built%20by-Nous%20Research-blueviolet?style=for-the-badge" alt="Built by Nous Research"></a>
</p>

**The self-improving AI agent built by [Nous Research](https://nousresearch.com).** Hermes is the only agent with a built-in learning loop — it creates skills from experience, improves them during use, searches its own past conversations, and builds a deepening model of who you are across sessions. Run it on a $5 VPS, a GPU cluster, or serverless infrastructure that costs nearly nothing when idle.

Use any model — [Nous Portal](https://portal.nousresearch.com), [OpenRouter](https://openrouter.ai) (200+ models), OpenAI, Anthropic, or your own endpoint. Switch with `hermes model` — no code changes, no lock-in.

| Feature | Description |
|---------|-------------|
| **Real terminal interface** | Full TUI with multiline editing, slash-command autocomplete, conversation history, interrupt-and-redirect, and streaming tool output |
| **Lives where you do** | Telegram, Discord, Slack, WhatsApp, Signal, and CLI — all from a single gateway process |
| **Closed learning loop** | Agent-curated memory with periodic nudges. Autonomous skill creation after complex tasks. FTS5 session search with LLM summarization |
| **Scheduled automations** | Built-in cron scheduler with delivery to any platform |
| **Delegates and parallelizes** | Spawn isolated subagents for parallel workstreams. Python scripts via RPC |
| **Runs anywhere** | Six terminal backends — local, Docker, SSH, Daytona, Singularity, and Modal |
| **Research-ready** | Batch trajectory generation, Atropos RL environments, trajectory compression for training |
| **Skills system** | [agentskills.io](https://agentskills.io) compatible — browse, install, and create skills |

---

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

Works on Linux, macOS, WSL2, and Android via Termux.

```bash
source ~/.bashrc    # reload shell (or: source ~/.zshrc)
hermes              # start chatting!
```

## Getting Started

```bash
hermes              # Interactive CLI — start a conversation
hermes model        # Choose your LLM provider and model
hermes tools        # Configure which tools are enabled
hermes setup        # Run the full setup wizard
hermes gateway      # Start the messaging gateway (Telegram, Discord, etc.)
hermes skills       # Browse, enable, and install skills
hermes update       # Update to the latest version
hermes doctor       # Diagnose any issues
```

📖 **[Full documentation →](https://hermes-agent.nousresearch.com/docs/)**

---

## Project Structure

```
hermes-agent/
├── run_agent.py            # AIAgent — core conversation loop
├── model_tools.py          # Tool orchestration & dispatch
├── toolsets.py             # Toolset definitions
├── cli.py                  # HermesCLI — interactive CLI orchestrator
├── hermes_state.py         # SessionDB — SQLite session store (FTS5)
├── agent/                  # Agent internals (prompt builder, compression, memory, skills)
├── hermes_cli/             # CLI subcommands (config, setup, skills, tools, models)
├── tools/                  # Tool implementations (terminal, file, web, browser, MCP, etc.)
│   ├── registry.py         # Central tool registry
│   └── environments/       # Terminal backends (local, docker, ssh, modal, daytona, singularity)
├── gateway/                # Messaging platform gateway
│   └── platforms/          # Adapters: telegram, discord, slack, whatsapp, signal, homeassistant
├── acp_adapter/            # ACP server (VS Code / Zed / JetBrains integration)
├── cron/                   # Scheduler (jobs + croniter integration)
├── environments/           # RL training environments (Atropos)
├── skills/                 # Bundled skills (software-development, research, devops, etc.)
├── optional-skills/        # Official but not auto-enabled skills
├── tests/                  # Pytest suite (~3000 tests)
├── scripts/                # Install, packaging, and utility scripts
└── docs/                   # Migration guides, plans, specs, skins
```

**User config:** `~/.hermes/config.yaml` (settings), `~/.hermes/.env` (API keys)

---

## For Developers

| File | Purpose |
|------|---------|
| **[AGENTS.md](AGENTS.md)** | Coding agent guide — architecture, workflows, standards, pitfalls |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | Human contributor guide — setup, skill vs tool, PR process |
| **[.github/CODE_REVIEW.md](.github/CODE_REVIEW.md)** | PR review checklist |

```bash
# Clone & set up
git clone --recurse-submodules https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
uv venv venv --python 3.11 && source venv/bin/activate
uv pip install -e ".[all,dev]"

# Run tests (unit only, no API keys needed)
python -m pytest tests/ -q --ignore=tests/integration --ignore=tests/e2e
```

---

## CLI vs Messaging Quick Reference

Hermes has two entry points: the terminal UI (`hermes`) or the messaging gateway (Telegram, Discord, Slack, WhatsApp, Signal). Slash commands work in both.

| Action | CLI | Messaging |
|--------|-----|-----------|
| Start | `hermes` | `hermes gateway start` + message the bot |
| New conversation | `/new` or `/reset` | `/new` or `/reset` |
| Change model | `/model [provider:model]` | `/model [provider:model]` |
| Browse skills | `/skills` or `/<skill>` | `/skills` or `/<skill>` |
| Compress context | `/compress` | `/compress` |
| Interrupt | `Ctrl+C` or new message | `/stop` or new message |

📖 **[CLI Guide](https://hermes-agent.nousresearch.com/docs/user-guide/cli)** · **[Messaging Guide](https://hermes-agent.nousresearch.com/docs/user-guide/messaging)**

---

## Community

- 💬 [Discord](https://discord.gg/NousResearch)
- 📚 [Skills Hub](https://agentskills.io)
- 🐛 [Issues](https://github.com/NousResearch/hermes-agent/issues)
- 💡 [Discussions](https://github.com/NousResearch/hermes-agent/discussions)

---

## License

MIT — see [LICENSE](LICENSE).

Built by [Nous Research](https://nousresearch.com).
