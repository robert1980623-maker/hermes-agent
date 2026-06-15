# Memorix Memory Provider

Local-first persistent memory for Hermes Agent with semantic search, automatic turn extraction, and session handoff capabilities.

## Features

- **Local-first**: All data stored in a local SQLite database
- **Semantic search**: Find relevant memories using natural language queries
- **Automatic extraction**: Optionally use LLM to extract facts from conversations
- **Session handoff**: Automatically create and resume session handoffs
- **Token budgeting**: Control how much memory context is injected

## Installation

Memorix is included with Hermes Agent. No additional installation required.

If you want to use a custom version of memorix:

```bash
pip install memorix
```

## Configuration

Run the setup wizard:

```bash
hermes memory setup
```

Select `memorix` as your memory provider and configure:

- **db_path**: Path to the SQLite database (default: `~/.hermes/memorix.db`)
- **project**: Project name for memory isolation (default: `hermes`)
- **auto_save**: Automatically save turns to memory (default: `true`)
- **turn_extraction**: Use LLM to extract facts from turns (default: `false`)

### Environment Variables

You can also configure via environment variables:

- `MEMORIX_DB_PATH`: Override database path
- `MEMORIX_PROJECT`: Override project name

### Advanced Configuration

For advanced settings, edit `~/.hermes/memorix.json`:

```json
{
  "db_path": "~/.hermes/memorix.db",
  "project": "hermes",
  "auto_save": true,
  "turn_extraction": false,
  "turn_extraction_min_strength": 0.7,
  "auto_handoff": false,
  "auto_resume": false,
  "handoff_resume_max_age_hours": 24,
  "prefetch_top_k": 5,
  "prefetch_min_score": 0.0,
  "token_budget_prefetch": null,
  "token_budget_prompt": null
}
```

## Tools

Memorix provides three tools to the agent:

### `memorix_save`

Save an important fact, decision, or learning to long-term memory.

```json
{
  "title": "User prefers dark mode",
  "content": "User mentioned they prefer dark mode for all applications",
  "type": "preference",
  "tags": ["ui", "preference"]
}
```

Types: `fact`, `bugfix`, `learning`, `preference`, `decision`

### `memorix_search`

Search past observations by meaning (semantic search).

```json
{
  "query": "dark mode preferences",
  "top_k": 5,
  "min_score": 0.7
}
```

### `memorix_list`

List recent observations, optionally filtered by topic or type.

```json
{
  "limit": 10,
  "type": "preference"
}
```

## Hooks

Memorix implements these Hermes hooks:

- **on_turn_start**: Track turn count
- **on_session_end**: Final extraction
- **on_pre_compress**: Create handoff before context compression
- **on_memory_write**: Mirror built-in memory writes to memorix
- **on_delegation**: Save delegation task/result pairs

## Architecture

Memorix uses:

- **SQLite** for storage (via SQLModel)
- **Sentence transformers** for embeddings (default: `all-MiniLM-L6-v2`)
- **Cosine similarity** for semantic search
- **Optional LLM** for turn extraction (requires OpenAI API key)

## Troubleshooting

### "Memorix provider not initialized"

Make sure memorix is properly configured:

```bash
hermes memory status
```

### Database locked errors

Close other Hermes instances using the same database, or use a different `db_path`.

### Slow semantic search

Reduce `prefetch_top_k` or increase `prefetch_min_score` in config.

## Links

- [Memorix Documentation](https://github.com/yourusername/memorix)
- [Hermes Memory Provider Plugins](/docs/developer-guide/memory-provider-plugin)
