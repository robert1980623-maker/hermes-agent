# Deep Analysis: ProactAgent — Proactive Retrieval for Lifelong LLM Agents

**Paper:** "Ask Only When Needed: Proactive Retrieval from Memory and Skills for Experience-Driven Lifelong Agents"  
**arXiv:** 2604.20572v1 [cs.CL] · 22 Apr 2026  
**Authors:** Yuxuan Cai, Jie Zhou, Qin Chen, Liang He (ECNU + Shanghai AI Lab)  
**Base Model:** Qwen2.5-7B-Instruct (main), Qwen2.5-3B-Instruct (scaling)

---

## 1. Core Insight: Proactive vs Passive Retrieval

### The Problem
Existing lifelong agents treat retrieval from past experience as a **passive operation**, triggered by:
- **Static initialization** — memory injected once at episode onset (Reflexion, MemoryBank, Mem0). Agents cannot seek new info when task dynamics shift mid-episode.
- **Continuous retrieval** — querying at every step (Memevolve). Introduces redundancy and context overload.
- **LLM-gated retrieval** — a separate model/heuristic decides necessity (ReflectiveRAG, MemSkill). Adds latency, cost, and still receives no outcome-level feedback on retrieval quality.

### The Key Insight
**Retrieval should be learned as an intrinsic policy action**, not governed by fixed schedules, external rules, or separate gating modules. The agent itself should learn:
- **WHEN** to retrieve (recognizing its own knowledge gaps mid-interaction)
- **WHAT** to retrieve (formulating effective queries for the current decision)

### Why It Matters
- Outcome-level rewards alone cannot provide step-level supervision for individual retrieval decisions. When an episode fails, the agent cannot determine whether retrieval was unnecessary, mistimed, or too vague.
- ProactAgent solves this by comparing continuations from identical prefixes *with* vs *without* retrieval — a **counterfactual credit assignment** mechanism that isolates the causal effect of a specific retrieval action.
- Results: 3B model with proactive retrieval nearly matches 7B passively-augmented baselines, suggesting learned retrieval control can partially offset raw capacity gaps.

---

## 2. Architecture of ProactAgent

ProactAgent consists of two tightly coupled components operating in a self-reinforcing cycle:

### 2.1 Experience-Enhanced Online Evolution (ExpOnEvo)

**Role:** Closes the loop between acting, experience accumulation, and policy optimization.

**Three-phase cycle per training iteration:**
1. **Interact** — Agent processes tasks under current policy πθ, augmented by proactive retrieval from structured experience base D
2. **Distill** — Completed trajectories are extracted into typed experience entries (via Qwen3-32B) and incorporated into D
3. **Update** — Policy πθ updated via GRPO on collected trajectories, where retrieval decisions are optimized jointly with task actions

**Self-reinforcing loop:** Richer experience base → more relevant retrieval → better trajectories → higher-quality experience entries → stronger policy gradients.

### 2.2 Typed Experience Base

The experience base is partitioned into **five typed stores** (not a single undifferentiated pool):

| Group | Entry Type | Content | Source |
|-------|-----------|---------|--------|
| **Memory (M)** | Factual (Mf) | Environment facts, tool outputs, persistent states | Per-trajectory |
| | Episodic (Me) | Local plans, constraints, trajectory-specific reminders | Per-trajectory |
| **Skill (S)** | Success (S⁺) | Reusable strategies from successful completions | Successful trajectories |
| | Failure (S⁻) | Error patterns and corrective rules | Failed trajectories |
| | Comparative (SΔ) | Contrastive insights on why one continuation outperforms another | Paired A/B branches |

**Retrieval mechanics:**
- Each entry stores: `when_to_use` (trigger context), `content`, embedding `e(r)`, priority score `p(r)`
- Scoring: `score(qt, r) = sim(e(qt), e(r)) + λp·p(r)`
- Type-balanced retrieval: K slots divided equally across 5 types (1 each by default)
- Priority update: Only entries actually retrieved in successful trajectories get incremented
- Deduplication: Exact-match on `when_to_use` field
- Backend: all-MiniLM-L6-v2 embeddings → FAISS inner-product index

### 2.3 Proactive RL-based Retrieval (ProactRL)

**Role:** Formulates retrieval as an explicit policy action learned through paired-branch process rewards.

**Augmented action space:** `A = Aenv ∪ Aret` where `Aret = RETRIEVE(qt)` (natural-language query)

**Three-part trajectory reward:**
```
Rtraj = Renv + rproc + reff
```
- `Renv` — cumulative environment reward
- `rproc` — paired-branch process reward (see Section 3)
- `reff` — efficiency penalty (repeated queries + trajectory length)

**Training pipeline:**
1. Cold-start SFT on successful trajectories (critical — ablation shows -12pt without it)
2. Rollout sampling with retrieval annealing (3 phases: calibration → transition → refinement)
3. Paired-branch construction for retrieval-triggered trajectories
4. GRPO policy update with group-normalized advantages

---

## 3. Paired-Branch Process Rewards — How Retrieval Supervision Works

This is the paper's most novel technical contribution.

### The Problem
Standard outcome-level rewards cannot isolate whether a specific retrieval decision at a particular step was beneficial. When an episode fails, the agent cannot determine *why* — was retrieval unnecessary? Mistimed? Too vague?

### The Mechanism

**Step 1: Detect retrieval trigger**
During rollout τ, when the policy produces a retrieval action at step `tb`, the system marks this as a branching point.

**Step 2: Generate paired branches**
```
τret  = τ<tb ⊕ τ≥tb     (retrieval branch — keeps the retrieval and its continuation)
τno-ret = Replay(τ<tb) ⊕ τ≥tb  (no-retrieval branch — suppresses retrieval at tb, samples env action instead)
```
Both branches share the **identical interaction prefix** up to `tb`. The divergence between them isolates the causal effect of that specific retrieval decision.

**Step 3: Compute rollout margin**
```
Δi = (Ri_env - Rj_env) + λT · (Tj - Ti) / max(Tj, 1)
```
Combines environment reward difference with trajectory length regularization.

**Step 4: Assign process reward**
```
rproc =  +α    if zi > 0 and Δi > 0   (retrieval improved outcome)
        -α    if zi > 0 and Δi < 0   (retrieval was redundant/harmful)
         0    otherwise
```

**Step 5: Efficiency penalty**
```
reff = -wq · 1[repeated query] + clip(wt · (T̄g - Ti) / max(T̄g, 1), -|wt|, |wt|)
```
Penalizes repeated queries; rewards shorter successful trajectories.

### Why This Works (Theoretical Basis)

The appendix proves (Proposition 1) that under the GRPO approximation, the branching-step policy gradient decomposes into:
```
gtb = ((Ai + Aj)/2) · ∇θ log(πi·πj) + ((Ai - Aj)/2) · ∇θ log(πi/πj)
```
The **advantage gap** `(Ai - Aj)` directly controls the log-odds update between retrieval and non-retrieval actions. Because both branches share the identical prefix, this signal is attached to the **necessity of retrieval at the current state**, not to unrelated earlier actions.

Crucially, the gradient also updates the **specific query content** `qt`, so the model learns both timing and query formulation simultaneously.

### Design Details
- Branching step `tb` selected uniformly from **interior** retrieval steps (excludes first/last to avoid initialization/termination confounds)
- Environment state restored via prefix replay (Assumption 1)
- Retrieval annealed across 3 phases: calibration (50% no-retrieval) → transition (25%) → refinement (0%)

---

## 4. Experimental Setup and Results

### Benchmarks
| Benchmark | Type | Metrics |
|-----------|------|---------|
| **SciWorld** | Scientific reasoning | Success Rate (SR) ↑, Rounds ↓ |
| **AlfWorld** | Embodied text games | SR ↑, Rounds ↓ |
| **StuLife** | Lifelong simulation | SR ↑, StuGPA ↑ |

### Main Results (Qwen2.5-7B-Instruct)

| Method | SciWorld SR | SciWorld Rounds | AlfWorld SR | AlfWorld Rounds | StuLife SR | StuLife StuGPA |
|--------|------------|----------------|-------------|-----------------|------------|---------------|
| **Offline baselines** | | | | | | |
| Baseline | 2.00 | 33.40 | 27.69 | 32.85 | 2.56 | 6.33 |
| SFT | 19.50 | 30.26 | 54.36 | 26.78 | 5.11 | 7.27 |
| GRPO | **52.00** | 26.51 | **67.69** | 17.84 | — | — |
| **Online baselines** | | | | | | |
| GRPO (online) | 46.50 | 27.87 | 68.71 | 13.99 | 6.71 | 10.28 |
| AWM | 1.00 | 35.65 | 31.28 | 33.56 | 3.51 | 7.60 |
| Reflexion | 4.00 | 33.73 | 36.92 | 38.57 | 6.82 | 11.31 |
| MemoryBank | 2.50 | 30.24 | 32.31 | 37.14 | 6.05 | 7.69 |
| Mem0 | 3.00 | 34.94 | 33.85 | 32.11 | **7.34** | 10.83 |
| GRPO+Reflexion | 55.50 | 27.52 | 67.18 | 16.42 | 9.37 | 13.51 |
| **ProactAgent (Ours)** | **73.50** | **18.38** | **71.28** | **12.73** | **12.35** | **19.26** |

**Key findings:**
- **+18.0 SR points** over strongest online baseline (GRPO+Reflexion) on SciWorld
- **-33.2% rounds** on SciWorld (27.52 → 18.38), **-22.5%** on AlfWorld (16.42 → 12.73)
- 0.43k tokens/task vs 0.95k for GRPO+Reflexion (55% token reduction)
- StuLife: competitive with proprietary models

### Ablation Studies (SciWorld)

**Progressive ablation:**
| Variant | SR | Rounds |
|---------|----|--------|
| Full ProactAgent | 73.50 | 18.38 |
| w/o ExpOnEvo (offline) | 71.50 | 17.15 |
| w/o ProactRL (SFT only) | 26.50 | 27.80 |
| w/o both (experience base only) | 5.50 | 30.18 |

**Component ablation:**
| Variant | SR | Rounds |
|---------|----|--------|
| Replace D with Reflexion | 62.50 | 23.15 |
| Remove paired-branch reward | 65.00 | 27.31 |
| Remove cold-start stage | 59.50 | 29.04 |

**Key takeaways:**
- ProactRL is the **most impactful component** (-45.0 pts without it)
- Typed decomposition outperforms monolithic memory by 9.0 pts
- Paired-branch rewards add 6.5 pts over standard GRPO alone
- Cold-start is critical (-12.0 pts without it)

### Model Scaling (SciWorld)

| Method | SR | Rounds |
|--------|----|--------|
| GRPO (3B) | 24.00 | 24.14 |
| GRPO+Reflexion (3B) | 29.50 | 20.09 |
| GRPO+Reflexion (7B) | 55.00 | 27.52 |
| **ProactAgent (3B)** | **53.50** | **14.35** |

**3B with proactive retrieval nearly matches 7B passive baseline** (+24.0 pts over 3B GRPO+Reflexion) while using 48% fewer rounds.

---

## 5. Relation to Agent Memory Architectures Wiki Note

**No existing wiki note** on `agent-memory-architectures` was found in the workspace. This paper would be a **high-value candidate** for creating one. Here's how it maps to potential wiki structure:

### Wiki Sections This Paper Would Inform

1. **Retrieval Triggering Strategies**
   - Static initialization → Continuous → LLM-gated → **Proactive (learned)** ← this paper's taxonomy
   - This is a clean, paper-backed classification that would anchor a wiki section

2. **Typed Memory Organizations**
   - Most systems use single undifferentiated repositories (Generative Agents, MemoryBank)
   - ProactAgent demonstrates 5-type partition (Mf, Me, S⁺, S⁻, SΔ) with type-balanced retrieval
   - Ablation proves typed decomposition > monolithic (9pt gain)

3. **Experience Evolution Mechanisms**
   - Memory-centric only (Reflexion, Voyager, ExpeL)
   - Parameter-centric only (online RL)
   - **Co-evolution** (ProactAgent) ← novel integration

4. **Retrieval Supervision Methods**
   - Confidence-threshold (FLARE)
   - Reflection tokens (Self-RAG)
   - Complexity routing (Adaptive-RAG)
   - **Paired-branch process rewards** (ProactRL) ← novel counterfactual approach

### Wiki Inclusion Verdict

| Criterion | Assessment |
|-----------|-----------|
| **Novelty** | High — first to formulate retrieval as learned policy action with counterfactual process rewards |
| **Empirical rigor** | Strong — 3 benchmarks, ablations, scaling, efficiency analysis, theoretical proof |
| **Reproducibility** | Good — clear algorithms, prompts in appendix, open base models |
| **Wiki value** | **HIGH** — would anchor sections on retrieval triggering strategies, typed memory, co-evolution, and counterfactual retrieval supervision |

**Recommendation:** Create `agent-memory-architectures` wiki note with ProactAgent as a primary reference. Its retrieval-triggering taxonomy (static → continuous → gated → proactive) provides a natural organizing framework, and its 5-type memory schema is the most structured approach documented in current literature.

---

## Summary of Findings

| Aspect | Assessment |
|--------|-----------|
| **Core contribution** | Proactive retrieval as learned policy action with paired-branch process rewards |
| **Technical novelty** | Counterfactual credit assignment for retrieval decisions; typed 5-way memory decomposition |
| **Empirical results** | 73.50% SciWorld, 71.28% AlfWorld, 12.35% StuLife — all SOTA among open-weight models |
| **Efficiency** | 33% fewer rounds, 55% fewer tokens vs strongest baseline |
| **Scaling** | 3B proactive ≈ 7B passive — retrieval control partially offsets capacity gaps |
| **Limitations** | Requires prefix-replayable environments (Assumption 1); extraction uses 32B model; no fixed capacity cap or eviction policy |
| **Wiki inclusion** | **Strong yes** — foundational for any agent memory architecture taxonomy |
