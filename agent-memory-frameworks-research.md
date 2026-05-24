# Agent Memory & Session Management: Open-Source Frameworks (2024–2026)

> Research Date: April 15, 2026 | Data sourced from GitHub API

---

## 1. Dedicated Memory Management Frameworks (Ranked by Stars)

### Tier 1: Market Leaders (>20K Stars)

| Framework | Stars | Description |
|---|---|---|
| **[mem0ai/mem0](https://github.com/mem0ai/mem0)** | ~53K | Universal memory layer for AI Agents. The most popular dedicated memory framework. Supports multi-layer memory (short-term, long-term, entity) with self-improving retrieval. Works with LangChain, LlamaIndex, CrewAI, and any LLM. |
| **[letta-ai/letta](https://github.com/letta-ai/letta)** | ~22K | Formerly MemGPT. Platform for building stateful agents with advanced memory that can learn and self-improve. Pioneered the idea of agents managing their own context through archival/recall memory layers. |
| **[volcengine/OpenViking](https://github.com/volcengine/OpenViking)** | ~22K | Open-source context database designed specifically for AI Agents. Unifies memory, resources, and skills through a file system paradigm, enabling hierarchical context delivery and self-evolving capabilities. |
| **[gastownhall/beads](https://github.com/gastownhall/beads)** | ~20.7K | A memory upgrade for coding agents. Provides persistent issue tracking, task memory, and structured workflows that survive session compaction. Popular with Claude Code and other coding agents. |

### Tier 2: Established Frameworks (5K–20K Stars)

| Framework | Stars | Description |
|---|---|---|
| **[topoteretes/cognee](https://github.com/topoteretes/cognee)** | ~15.4K | Knowledge Engine for AI Agent Memory in 6 lines of code. Graph-based memory with automatic knowledge extraction, semantic search, and structured memory graphs. |
| **[memvid/memvid](https://github.com/memvid/memvid)** | ~14.9K | Memory layer for AI Agents. Replace complex RAG pipelines with a serverless, single-file memory layer. Instant retrieval and long-term memory with minimal setup. |
| **[NevaMind-AI/memU](https://github.com/NevaMind-AI/memU)** | ~13.3K | Memory for 24/7 proactive agents. Focuses on persistent memory for always-on agent deployments. |
| **[MemoriLabs/Memori](https://github.com/MemoriLabs/Memori)** | ~13.3K | Agent-native memory infrastructure. LLM-agnostic layer that turns agent execution and conversation into structured, persistent state for production systems. |
| **[vectorize-io/hindsight](https://github.com/vectorize-io/hindsight)** | ~9.2K | Hindsight: Agent Memory That Learns. Self-improving memory system that extracts and consolidates insights from agent interactions over time. |
| **[MemTensor/MemOS](https://github.com/MemTensor/MemOS)** | ~8.4K | AI memory OS for LLM and Agent systems. Enables persistent Skill memory for cross-task skill reuse and evolution. |
| **[getzep/zep](https://github.com/getzep/zep)** | ~4.4K | Zep provides persistent memory for conversational AI. Temporal knowledge graph for cross-session recall and personalized context assembly. SDKs for Python, TypeScript, and Go. |

### Tier 3: Emerging & Specialized (2K–5K Stars)

| Framework | Stars | Description |
|---|---|---|
| **[campfirein/byterover-cli](https://github.com/campfirein/byterover-cli)** | ~4.5K | Portable memory layer for autonomous coding agents (formerly Cipher). |
| **[EverMind-AI/EverOS](https://github.com/EverMind-AI/EverOS)** | ~3.9K | Build, evaluate, and integrate long-term memory for self-evolving agents. |
| **[aiming-lab/SimpleMem](https://github.com/aiming-lab/SimpleMem)** | ~3.2K | Efficient lifelong memory for LLM Agents — Text & Multimodal. |
| **[memodb-io/Acontext](https://github.com/memodb-io/Acontext)** | ~3.3K | Agent Skills as a Memory Layer. |
| **[MemMachine/MemMachine](https://github.com/MemMachine/MemMachine)** | ~4.1K | Universal memory layer for AI Agents. Scalable and interoperable. |

---

## 2. Session & Context Management Systems

| Framework | Stars | Description |
|---|---|---|
| **[langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)** | ~29K | De facto standard for session/state management. Checkpointing, state persistence, human-in-the-loop. |
| **[qwibitai/nanoclaw](https://github.com/qwibitai/nanoclaw)** | ~27K | Lightweight agent harness with built-in memory, scheduled jobs, session management. |
| **[parcadei/Continuous-Claude-v3](https://github.com/parcadei/Continuous-Claude-v3)** | ~3.7K | Context management for Claude Code. State via ledgers, isolated context windows. |
| **[vstorm-co/summarization-pydantic-ai](https://github.com/vstorm-co/summarization-pydantic-ai)** | ~28 | Context Management processor. LLM summarization or sliding window trimming. |
| **[Lucenor/mnesis](https://github.com/Lucenor/mnesis)** | ~16 | Deterministic memory engine to solve context window degradation. |

---

## 3. Key Trends (2024–2026)

1. **Memory-as-a-Service**: Mem0, Zep, Cognee abstract memory into pluggable layers.
2. **Graph-Based Memory**: Cognee, Zep, OpenViking use knowledge graphs for relational memory.
3. **Self-Evolving Memory**: Hindsight, Letta, MemOS improve memory over time autonomously.
4. **Coding Agent Memory**: Beads, ByteRover, memU target coding agents with cross-session persistence.
5. **Context Databases**: OpenViking treats memory, skills, resources as a unified filesystem.
6. **MCP-Native Memory**: Most frameworks expose memory via Model Context Protocol (MCP).
7. **Skill Memory**: MemOS and Acontext treat learned skills as persistent memory.

---

## 4. Quick Comparison Matrix

| Framework | Best For | Graph? | Self-Learning? | MCP? |
|---|---|---|---|---|
| **Mem0** | Universal memory | Partial | Yes | Yes |
| **Letta** | Stateful agents | No | Yes | Yes |
| **Cognee** | Knowledge graphs | Yes | Partial | Yes |
| **OpenViking** | Context database | Partial | Yes | Yes |
| **Beads** | Coding agents | No | No | Yes |
| **Hindsight** | Self-improving | No | Yes | Yes |
| **Zep** | Conversational AI | Yes | Partial | Yes |
| **MemOS** | Skill memory | No | Yes | Yes |
| **LangGraph** | Session mgmt | No | No | Partial |

---

*Data collected via GitHub API on April 15, 2026. Star counts are approximate.*
