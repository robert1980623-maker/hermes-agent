# Latest AI Agent Papers on arXiv (May 5–7, 2026)

> **Note:** No new AI agent papers were submitted on May 10–11, 2026 (last 24 hours). 
> The most recent batch is from **May 5–7, 2026**. Below are the **Top 10 most novel & relevant papers**
> curated from ~56 results across 4 search queries.

---

## 1. SkillOS: Learning Skill Curation for Self-Evolving Agents
- **Authors:** Siru Ouyang, Jun Yan, Yanfei Chen et al.
- **Submitted:** 2026-05-07
- **Categories:** cs.AI, cs.CL
- **URL:** http://arxiv.org/abs/2605.06614
- **Summary:** LLM-based agents typically act as one-off problem solvers, failing to learn from past interactions. This paper proposes **SkillOS**, a framework where agents distill reusable skills from experience for self-evolution. Addresses the critical bottleneck of high-quality skill curation in streaming/continuous task settings. Goes beyond manual skill design with automated skill discovery and composition.

## 2. STALE: Can LLM Agents Know When Their Memories Are No Longer Valid?
- **Authors:** Hanxiang Chao, Yihan Bai, Rui Sheng et al.
- **Submitted:** 2026-05-07
- **Categories:** cs.CL
- **URL:** http://arxiv.org/abs/2605.06527
- **Summary:** Identifies **Implicit Conflict** — when later observations invalidate earlier memories without explicit negation. Current benchmarks measure only static fact retrieval, not belief revision. This paper introduces the STALE benchmark for evaluating whether agents can detect when stored memories have become stale/invalid. Critical for long-term personalized agent memory.

## 3. MemReranker: Reasoning-Aware Reranking for Agent Memory Retrieval
- **Authors:** Chunyu Li, Jingyi Kang, Ding Chen et al.
- **Submitted:** 2026-05-07
- **Categories:** cs.CL
- **URL:** http://arxiv.org/abs/2605.06132
- **Summary:** Generic reranking models for agent memory rely on semantic similarity but lack genuine reasoning, returning results that are semantically relevant yet miss key information. Proposes **MemReranker**, a reasoning-aware reranking model that bridges the gap between retrieved results and what the agent actually needs for decision-making.

## 4. MASPO: Joint Prompt Optimization for LLM-based Multi-Agent Systems
- **Authors:** Zhexuan Wang, Xuebo Liu, Li Wang et al.
- **Submitted:** 2026-05-07
- **Categories:** cs.AI, cs.CL
- **URL:** http://arxiv.org/abs/2605.06623
- **Summary:** Multi-agent systems use role-specific prompts, but jointly optimizing them is non-trivial due to misalignment between local agent objectives and holistic system goals. **MASPO** addresses joint prompt optimization across interacting agents — a key unsolved problem in MAS design where optimizing one agent's prompt can degrade another's performance.

## 5. More Is Not Always Better: Cross-Component Interference in LLM Agent Scaffolding
- **Authors:** Ming Liu
- **Submitted:** 2026-05-07
- **Categories:** cs.AI, cs.CL
- **URL:** http://arxiv.org/abs/2605.05716
- **Summary:** **Critical empirical finding:** stacking agent components (planning, tools, memory, self-reflection, retrieval) does NOT always improve performance — they can interfere destructively. Full factorial experiment over all 32 subsets of 5 components across 96 conditions. Important counter-narrative to the "more components = better" assumption in agent design.

## 6. AI Co-Mathematician: Accelerating Mathematicians with Agentic AI
- **Authors:** Daniel Zheng, Ingrid von Glehn, Yori Zwols et al.
- **Submitted:** 2026-05-07
- **Categories:** cs.AI
- **URL:** http://arxiv.org/abs/2605.06651
- **Summary:** An **AI co-mathematician workbench** for interactive open-ended mathematical research. Supports the full exploratory workflow: ideation, literature search, computational exploration, theorem proving, and theory building. Asynchronous, long-running agent architecture designed for the iterative reality of mathematical research — not just single-shot problem solving.

## 7. VibeServe: Can AI Agents Build Bespoke LLM Serving Systems?
- **Authors:** Keisuke Kamahori, Shihang Li, Simon Peter et al.
- **Submitted:** 2026-05-07
- **Categories:** cs.AI, cs.DC
- **URL:** http://arxiv.org/abs/2605.06068
- **Summary:** First **agentic loop that automatically synthesizes bespoke LLM serving systems** for different usage scenarios. Flips the paradigm from one-size-fits-all serving stacks to a multi-agent system that generates, benchmarks, and iteratively improves custom serving configurations. Novel application of autonomous agents to systems infrastructure.

## 8. Teaching Thinking Models to Reason with Tools: A Full-Pipeline Recipe for Tool-Integrated Reasoning
- **Authors:** Qianjia Cheng, Yuchen Zhang, Zhilin Wang et al.
- **Submitted:** 2026-05-07
- **Categories:** cs.CL
- **URL:** http://arxiv.org/abs/2605.06326
- **Summary:** Paradoxical finding: tool-enabled evaluation can **degrade** reasoning performance even when thinking models make almost no tool calls. Provides a full-pipeline recipe for injecting natural tool-use behavior into strong reasoning/thinking models **without sacrificing** native reasoning capabilities. Addresses a key tension in the thinking-models era.

## 9. MANTRA: Synthesizing SMT-Validated Compliance Benchmarks for Tool-Using LLM Agents
- **Authors:** Ashwani Anand, Ivi Chatzi, Ritam Raha et al.
- **Submitted:** 2026-05-07
- **Categories:** cs.CL, cs.LG, cs.LO
- **URL:** http://arxiv.org/abs/2605.06334
- **Summary:** Tool-using LLM agents deployed with strict procedural manuals need compliance guarantees. **MANTRA** synthesizes SMT-validated benchmarks from natural-language procedural rules, enabling formal verification that agent tool-call traces comply with governing procedures. Bridges formal methods and agentic AI.

## 10. Safactory: A Scalable Agent Factory for Trustworthy Autonomous Intelligence
- **Authors:** Xinquan Chen, Zhenyun Yin, Shan He et al.
- **Submitted:** 2026-05-07
- **Categories:** cs.AI, cs.DC
- **URL:** http://arxiv.org/abs/2605.06230
- **Summary:** Addresses fragmentation in agentic infrastructure across evaluation, data management, and agent evolution. **Safactory** provides a unified platform for discovering risks systematically and improving models in a continuous closed loop — covering long-horizon decision making, tool use, and real environment interaction for autonomous agents.

---

## Additional Notable Papers (Honorable Mentions)

| Title | Key Focus | URL |
|---|---|---|
| **PrefixGuard: From LLM-Agent Traces to Online Failure-Warning Monitors** | Online monitoring of tool-using agent traces | http://arxiv.org/abs/2605.06455 |
| **Superintelligent Retrieval Agent** | Expert-level information retrieval agents | http://arxiv.org/abs/2605.06647 |
| **AI CFD Scientist** | Physics-aware agents for fluid dynamics discovery | http://arxiv.org/abs/2605.06607 |
| **SafeHarbor: Hierarchical Memory-Augmented Guardrail** | Memory-augmented safety guardrails for agents | http://arxiv.org/abs/2605.05704 |
| **LongSeeker: Elastic Context Orchestration** | Adaptive context management for long-horizon search agents | http://arxiv.org/abs/2605.05191 |
| **LatentRAG: Latent Reasoning and Retrieval for Agentic RAG** | Efficient multi-step retrieval with latent reasoning | http://arxiv.org/abs/2605.06285 |
| **Creative Robot Tool Use by Counterfactual Reasoning** | Causal reasoning for creative tool use in robots | http://arxiv.org/abs/2605.05411 |

## MCP (Model Context Protocol) Papers
- **No MCP-specific papers found** in the recent arXiv batch. The MCP term returned empty results, likely because papers about MCP use different terminology or are not yet submitted to arXiv.

## Summary Statistics
- **Total papers scanned:** ~56 across 4 search queries
- **Unique papers:** 46 (after deduplication)
- **Date range:** May 5–7, 2026
- **Most active categories:** cs.AI, cs.CL, cs.MA, cs.LG
- **Papers from last 24h (May 10–11):** 0
