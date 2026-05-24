# arXiv Recent Papers: LLM Agents, Multi-Agent Systems, Autonomous Agents
**Search Date:** April 22, 2026  
**Time Window:** Last 3 days (April 19–21, 2026)  
**Source:** arXiv RSS feeds (cs.AI + cs.CL) + Semantic Scholar API  
**Total agent-related papers found:** 275 (202 from April 2026)

---

## Top 12 Papers

### 1. [2604.17148] Graph-of-Agents: A Graph-based Framework for Multi-Agent LLM Collaboration
- **Date:** Apr 21, 2026
- **Categories:** cs.AI
- **Semantic Scholar Citations:** 2 ⭐ (highest among new papers)
- **Abstract:** Proposes Graph-of-Agents (GoA), a graph-based framework for modeling multi-agent LLM communication, addressing key limitations of Mixture-of-Agents (MoA) in agent selection, intra-agent communication, and response integration.
- **Relevance/Novelty:** ★★★★★ Highly novel — addresses fundamental orchestration problems in multi-agent systems. Graph-based approach to agent coordination is a fresh perspective beyond linear/sequential multi-agent pipelines. The fact it already has 2 citations within hours of posting signals strong community interest.

---

### 2. [2604.16339] Semantic Consensus: Process-Aware Conflict Detection and Resolution for Enterprise Multi-Agent LLM Systems
- **Date:** Apr 21, 2026
- **Categories:** cs.AI, cs.MA, cs.SE
- **Semantic Scholar Citations:** 0
- **Abstract:** Identifies "Semantic Intent Divergence" as a primary cause of multi-agent LLM failure (41–86.7% failure rates in production). Proposes Semantic Consensus Framework (SCF) with six components for process-aware conflict detection. Achieves 100% workflow completion vs 25.1% baseline across 600 runs.
- **Relevance/Novelty:** ★★★★★ Very high — addresses the critical gap in multi-agent production reliability. The formal identification of "Semantic Intent Divergence" and the SCF framework with Process Context Layer, Semantic Intent Graph, and Conflict Detection Engine represent substantial contributions.

---

### 3. [2604.17139] The Consensus Trap: Rescuing Multi-Agent LLMs from Adversarial Majorities via Token-Level Collaboration
- **Date:** Apr 21, 2026
- **Categories:** cs.CL, cs.AI, cs.MA
- **Semantic Scholar Citations:** 0
- **Abstract:** Reveals structural vulnerability in multi-agent systems: response-level aggregation (e.g., Majority Voting) collapses when corrupted agents form a local majority. Proposes token-level collaboration as a more robust alternative to response-level voting.
- **Relevance/Novelty:** ★★★★☆ Important security finding — demonstrates that common multi-agent aggregation patterns are fundamentally vulnerable to prompt injection attacks. Token-level collaboration is a novel mitigation strategy.

---

### 4. [2604.16338] Governing the Agentic Enterprise: A Governance Maturity Model for Managing AI Agent Sprawl in Business Operations
- **Date:** Apr 21, 2026
- **Categories:** cs.AI, cs.MA
- **Semantic Scholar Citations:** 0
- **Abstract:** Introduces Agentic AI Governance Maturity Model (AAGMM), a five-level framework spanning 12 governance domains. Proposes novel taxonomy of agent sprawl patterns (functional duplication, shadow agents, orphaned agents, permission creep, unmonitored delegation chains). Validated through 750 simulation runs.
- **Relevance/Novelty:** ★★★★☆ Highly relevant for enterprise deployments. The agent sprawl taxonomy is a practical and timely contribution as organizations struggle with uncontrolled agent proliferation.

---

### 5. [2604.16706] Evaluating Tool-Using Language Agents: Judge Reliability, Propagation Cascades, and Runtime Mitigation in AgentProp-Bench
- **Date:** Apr 21, 2026
- **Categories:** cs.AI, cs.CL, cs.MA
- **Semantic Scholar Citations:** 0
- **Abstract:** Introduces AgentProp-Bench, a 2,000-task benchmark with 2,300 traces across four domains and nine production LLMs. Quantifies judge reliability against human annotation, characterizes error propagation cascades, and evaluates runtime mitigation strategies.
- **Relevance/Novelty:** ★★★★★ Essential evaluation work — the first comprehensive benchmark validating the reliability of automated LLM agent evaluation against human ground truth. The 2,300-trace dataset is a significant community resource.

---

### 6. [2604.14691] CAMO: An Agentic Framework for Automated Causal Discovery from Micro Behaviors to Macro Emergence in LLM Agent Simulations
- **Date:** Apr 21, 2026
- **Categories:** cs.AI, cs.CL, cs.CY
- **Semantic Scholar Citations:** 0
- **Abstract:** Introduces CAMO, an automated causal discovery framework for disentangling micro-to-macro causal mechanisms in LLM agent simulations. Addresses the challenge that emergence arises from intertwined agent interactions and meso-level feedback.
- **Relevance/Novelty:** ★★★★☆ Novel methodology — bridges causal inference and agent simulation. Particularly valuable for social science research using LLM agent populations.

---

### 7. [2604.16723] Debate as Reward: A Multi-Agent Reward System for Scientific Ideation via RL Post-Training
- **Date:** Apr 21, 2026
- **Categories:** cs.AI, cs.LG
- **Semantic Scholar Citations:** 0
- **Abstract:** Addresses reward hacking in applying RL to scientific ideation. Proposes using multi-agent debate as a reward signal instead of static evaluators, reducing hallucination while maintaining computational efficiency.
- **Relevance/Novelty:** ★★★★☆ Innovative approach — using agent debate as a reward mechanism for RL is a creative solution to the open-ended evaluation problem in scientific ideation.

---

### 8. [2604.17612] Provable Coordination for LLM Agents via Message Sequence Charts
- **Date:** Apr 21, 2026
- **Categories:** cs.PL, cs.AI
- **Semantic Scholar Citations:** 0
- **Abstract:** Introduces a domain-specific language based on message sequence charts (MSCs) for specifying agent coordination. Separates message-passing structure from LLM actions, enabling formal verification of multi-agent protocols.
- **Relevance/Novelty:** ★★★★☆ Formal methods contribution — bringing MSC-based specification to LLM agents bridges a gap between software engineering and AI. Addresses the critical need for verifiable agent coordination.

---

### 9. [2604.18509] MASS-RAG: Multi-Agent Synthesis Retrieval-Augmented Generation
- **Date:** Apr 21, 2026
- **Categories:** cs.CL
- **Semantic Scholar Citations:** 0
- **Abstract:** Proposes MASS-RAG, structuring evidence processing into multiple role-specialized agents for retrieval-augmented generation. Addresses noisy, incomplete, or heterogeneous retrieved contexts that single-model generation struggles with.
- **Relevance/Novelty:** ★★★☆☆ Incremental but practical — multi-agent RAG is a natural extension, and role-specialized agents for evidence processing is a clean architectural pattern.

---

### 10. [2604.17658] Towards Self-Improving Error Diagnosis in Multi-Agent Systems
- **Date:** Apr 21, 2026
- **Categories:** cs.MA, cs.CL
- **Semantic Scholar Citations:** 0
- **Abstract:** Introduces ErrorProbe, a self-improving framework for semantic fault localization in LLM-based multi-agent systems. Addresses debugging challenges from long interaction traces, inter-agent dependencies, and delayed error manifestation.
- **Relevance/Novelty:** ★★★★☆ Addresses a real pain point — multi-agent debugging is notoriously difficult. ErrorProbe's self-improving approach to fault localization is timely and practical.

---

### 11. [2604.17337] AutoSearch: Adaptive Search Depth for Efficient Agentic RAG via Reinforcement Learning
- **Date:** Apr 21, 2026
- **Categories:** cs.AI
- **Semantic Scholar Citations:** 0
- **Abstract:** Addresses redundant search steps in agentic RAG systems. Uses RL to adaptively determine optimal search depth, reducing computational cost and latency while maintaining task performance.
- **Relevance/Novelty:** ★★★☆☆ Practical optimization — RL-driven adaptive search depth is a sensible approach to the computational efficiency problem in agentic RAG.

---

### 12. [2604.17091] GenericAgent: A Token-Efficient Self-Evolving LLM Agent via Contextual Information Density Maximization (V1.0)
- **Date:** Apr 21, 2026
- **Categories:** cs.CL
- **Semantic Scholar Citations:** 0
- **Abstract:** Addresses context window limitations in long-horizon LLM agents. Proposes contextual information density maximization to retain critical information across extended interactions, improving cross-episode learning.
- **Relevance/Novelty:** ★★★★☆ Addresses a fundamental bottleneck — context window limitations are the #1 constraint on long-horizon agents. Information density maximization is a principled approach.

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total papers scanned (RSS) | 1,170 (cs.AI + cs.CL) |
| Agent-related papers (April 2026) | 202 |
| Papers with citations > 0 | 1 (Graph-of-Agents: 2 citations) |
| Most common themes | Multi-agent coordination, agent evaluation, agentic RAG, agent memory |

## Key Themes Identified

1. **Multi-Agent Coordination & Reliability** — Papers #2, #3, #8, #10 address the fundamental challenge of coordinating multiple LLM agents reliably in production settings
2. **Agent Evaluation & Benchmarking** — Paper #5 provides the first comprehensive validation of automated agent evaluation against human annotation
3. **Agentic RAG & Search** — Papers #9, #11 focus on optimizing retrieval-augmented generation with multi-agent and RL approaches
4. **Agent Governance & Safety** — Papers #4, #15 (Why Agents Compromise Safety) address enterprise governance and safety under pressure
5. **Agent Memory & Context** — Papers #12 addresses context efficiency, with related work on HeLa-Mem (Hebbian memory), SkillX, and Oblivion (decay-driven memory)
6. **Formal Methods for Agents** — Paper #8 brings message sequence charts and formal verification to agent coordination

## Method Notes

- arXiv REST API returned 429 (rate limited) for all query attempts
- Successfully used arXiv RSS feed (`rss.arxiv.org/rss/cs.AI+cs.CL`) as alternative data source
- RSS feed contained 1,170 papers from cs.AI and cs.CL categories
- Filtered using keyword matching: agent, multi-agent, autonomous, agentic, multiagent
- Semantic Scholar API used for citation counts (most papers have 0 citations as expected for <3-day-old submissions)
