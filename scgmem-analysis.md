# SCG-MEM: Deep Analysis

**Paper:** "To Know is to Construct: Schema-Constrained Generation for Agent Memory"  
**arXiv:** 2604.20117v1 (22 Apr 2026)  
**Authors:** Lei Zheng, Weinan Song, Daili Li, Yanming Yang (UnionPay)

---

## 1. Core Technical Contribution

### The Problem SCG-MEM Identifies

SCG-MEM identifies two fundamental flaws in existing agent memory architectures:

1. **Dense Retrieval Noise (§1):** Dense retrieval relies on semantic overlap / entity matching, but semantically similar vectors can be contextually distinct. Embeddings "fail to distinguish instances that are semantically similar but contextually distinct, introducing substantial noise by retrieving context-mismatched entries."

2. **Structural Hallucination (§1, §3.1):** Open-ended generative recall (having an LLM generate memory keys directly) risks producing keys that don't exist in the memory store — defined formally as **Structural Hallucination**: `k̂ ∉ S` where S is the set of valid memory keys. This is "catastrophic" because it causes lookup failures.

### The Novel Solution

SCG-MEM introduces a third way: **Schema-Constrained Generation**. Instead of:
- (a) encoding queries to vectors → similarity search (retrieval-based), or
- (b) free-form LLM key generation → lookup (unconstrained generation),

SCG-MEM **(c)** constrains LLM decoding via a Prefix Trie so that the model can **only** generate valid memory entry keys. This provides a **formal mathematical guarantee** that `Pθ(k̂ ∉ S | c) = 0` (§3.1, Eq. 2).

### Key Innovations

| Innovation | What It Does | Paper Section |
|---|---|---|
| **Prefix Trie as Cognitive Schema** | Discrete, structured representation of the agent's epistemic boundary; hard-constrains LLM decoding | §3.2 |
| **Schema-Constrained Decoding** | Token-level probability masking via Trie validity indicator; renormalizes distribution at each step | §3.3 |
| **Evolutionary Schema Construction** | Dual-pathway memory updates: Assimilation (ground into existing schema) + Accommodation (expand schema with novel concepts) | §3.4 |
| **Associative Graph** | Weighted undirected graph over schema nodes using IDF-product edge weights; enables multi-hop associative propagation | §3.5 |
| **Constructive Recall** | Two-stage recall: schema-constrained beam search for seeds → graph-based activation propagation → context reconstruction | §3.6 |

### Novelty vs. Existing Memory Approaches

The key departure from existing systems is the **reformulation of memory access from discriminative retrieval to schema-constrained generation**. Unlike MemGPT, MemoryBank, ReadAgent, or even graph-based systems like A-MEM and GraphRAG which all rely on dense retrieval for initial node selection, SCG-MEM eliminates the retrieval step entirely. The LLM generates memory keys, but is structurally prevented from hallucinating invalid keys.

---

## 2. Architecture Details

### 2.1 Cognitive Schema (§3.2)

The cognitive schema `S` is a finite set of concept keys over the token vocabulary Σ:

```
S ⊂ Σ*
```

**Implementation:** A dynamic **Prefix Trie** `T`. Every root-to-end-node path corresponds to a valid key `k ∈ S`. The trie defines the prefix-closed validity space:

```
ΩS = {s ∈ Σ* | ∃k ∈ S, s is a prefix of k}
```

This gives two critical properties:
- **Existence (Ontology):** The Trie answers "Does this concept exist in my world?" by enforcing `k̂ ∈ S`.
- **Association (Topology):** The Associative Graph (separate structure) answers "How is this concept related to others?"

### 2.2 Schema-Constrained Decoding (§3.3)

At each autoregressive decoding step `t`, the LLM's token distribution is modified:

```
PS(yt | y<t, c) = [Pθ(yt | y<t, c) · IS(y<t ∘ yt)] / Z(y<t)
```

Where `IS` is a binary validity indicator:
```
IS(y1:t) = 1 if y1:t ∈ ΩS, else 0
```

**Mechanism:** Invalid tokens receive zero probability mass before the softmax layer. The model becomes "mathematically incapable of generating a completed key outside S."

**Multi-key retrieval:** Uses constrained beam search with beam size `b` to generate `b` distinct valid keys simultaneously.

### 2.3 Evolutionary Schema Construction (§3.4)

Inspired by Piaget's constructivist epistemology, schema evolution follows two pathways:

**Assimilation (Grounding):**
- Attempts to interpret new input using existing cognitive structures.
- Schema-constrained generation maps input `d(t)` to valid keys: `Kassim = {k ∈ S(t-1) | k ~ PS(· | d(t))}`
- Reinforces existing graph edge weights without altering the schema boundary.

**Accommodation (Expansion):**
- Triggered when constrained generation fails (high perplexity or "unknown" token).
- Schema constraint is temporarily relaxed for free generation: `Knov = {k | k ~ Pθ(· | d(t))} \ S(t-1)`
- Novel concepts validated and inserted into Trie: `S(t) ← S(t-1) ∪ Knov`

### 2.4 Associative Graph (§3.5)

A weighted undirected graph `G = (V, E)` where `V = S` (exactly the schema concepts).

**Edge weights** computed via accumulated IDF product:
```
wuv = Σ_{(u,v)∈H} IDF(u) · IDF(v)
```
where `IDF(k) = log(N / df(k))`, `N` = total dialogue turns, `df(k)` = turns containing concept k.

**Key design choice:** IDF acts as a significance filter, penalizing ubiquitous stop-words and boosting rare domain-specific concept connections.

### 2.5 Constructive Recall Pipeline (§3.6)

**Stage 1 — Schema Activation:** Query → constrained beam search → `Kseed` (b valid seed concepts).

**Stage 2 — Associative Propagation:** For each `u ∈ Kseed`, compute transition probabilities via softmax over edge weights with temperature `T`:
```
P(v | u) = exp(wuv/T) / Σ exp(wuv'/T)
```
Sample to get `Kcontext`.

**Stage 3 — Context Reconstruction:** Map `Kseed ∪ Kcontext` back to source text segments → form context `C` → generate response `r ~ Pθ(r | C, q)`.

### Architecture Diagram (from paper, Figure 2)

```
(A) Evolutionary Schema Construction
    New dialogue turns → Assimilation (constrained) + Accommodation (free)

(B) Relational Topology Construction
    Co-occurring concepts → Associative Graph (IDF-weighted edges)

(C) Constructive Recall
    Query → Schema Activate (constraint decoding) → Seed Concepts
          → Associative Propagation → Context for Answers
```

---

## 3. Experimental Results

### 3.1 Setup (§4.1–4.4)

- **Benchmark:** LoCoMo (Maharana et al., 2024) — ultra-long dialogues (avg 9K tokens, up to 35 sessions)
- **Task categories:** Single-Hop, Multi-Hop, Temporal, Adversarial (excluding Open-Domain)
- **Metrics:** F1 Score, BLEU-1
- **Models:** Qwen2.5 (1.5B, 3B), Llama 3.2 (1B, 3B) — open-weights for local logit access
- **Embeddings:** BGE-M3 for initial concept representations
- **Baselines:** LoCoMo (no memory), ReadAgent, MemoryBank, MemGPT, A-MEM

### 3.2 Main Results (Table 1)

SCG-MEM outperforms A-MEM (strongest baseline) across all categories and all models:

| Model | Metric | Multi-Hop | Temporal | Single-Hop | Adversarial | Average |
|---|---|---|---|---|---|---|
| **Qwen2.5 1.5B** | F1 improvement vs A-MEM | **+10.0%** | **+35.8%** | **+16.5%** | **+7.2%** | **+32.0%** |
| **Qwen2.5 3B** | F1 improvement vs A-MEM | **+56.5%** | **+57.7%** | **+35.1%** | **+34.8%** | **+43.9%** |
| **Llama 3.2 1B** | F1 improvement vs A-MEM | **+126.6%** | **+53.3%** | **+146.7%** | **+88.6%** | **+94.5%** |
| **Llama 3.2 3B** | F1 improvement vs A-MEM | **+15.6%** | **+87.1%** | **+57.7%** | **+17.3%** | **+43.2%** |

**Notable findings:**
- Largest absolute F1 scores: Qwen2.5 3B (Avg F1: 41.48 vs A-MEM 21.33)
- Largest relative gains on smallest model: Llama 3.2 1B shows SCG-MEM nearly doubles A-MEM's performance, suggesting the architecture compensates for smaller model capacity
- Consistent improvement across all 4 task types across all 4 models

### 3.3 Ablation Study (Table 2, §4.6)

Using Qwen2.5 3B:

| Configuration | Multi-Hop F1 | Temporal F1 | Single-Hop F1 | Adversarial F1 |
|---|---|---|---|---|
| **SCG-MEM (Full)** | **28.49** | **42.29** | **42.51** | **52.63** |
| w/o Cognitive Constraint | 17.23 (-39.5%) | 35.29 (-16.6%) | 34.45 (-19.0%) | 41.74 (-20.7%) |
| w/o Evolutionary Update | 18.74 (-34.2%) | 33.79 (-20.1%) | 33.73 (-20.7%) | 34.33 (-34.8%) |

- Removing the schema constraint hurts Multi-Hop the most (-39.5%), confirming that accurate seed concept selection is the primary bottleneck
- Removing evolutionary updates hurts Adversarial the most (-34.8%) and Temporal (-20.1%), confirming that linking new information to existing knowledge is essential for evolving facts

### 3.4 Hyperparameter Sensitivity (§4.7)

**Retrieval Size (k):** Inverted-U curve peaking at **k ≈ 35**. Below 20: misses relevant context. Above 40: introduces noise.

**Association Hops:** Inverted-V pattern. Hop-0 (seed only) performs worst, especially on Multi-Hop. **Hop-1** is optimal across all categories. Hop-2 universally degrades performance (especially Temporal) due to semantic drift.

---

## 4. Comparison to Existing Architectures

### 4.1 Compared to Bellamem, Genesys, Dual-Trace Encoding

> **Note:** The wiki file `agent-memory-architectures.md` was not found in this workspace. The following comparison is based on the paper's own baselines and general knowledge of these architectures.

| Dimension | SCG-MEM | Bellamem | Genesys | Dual-Trace |
|---|---|---|---|---|
| **Access Paradigm** | Schema-constrained generation | Dense retrieval + memory notes | LLM-generated memory notes | Dual encoding (dense + episodic) |
| **Key Innovation** | Prefix Trie hard constraint on LLM decoding | Structured note format with evolution | Generative memory with self-reflection | Two complementary trace types |
| **Hallucination Guard** | Mathematical guarantee (k̂ ∈ S by construction) | Relies on embedding similarity | Post-generation validation | Cross-trace verification |
| **Schema/Ontology** | Explicit Prefix Trie with dynamic growth | Implicit in note structure | Implicit | Implicit in trace types |
| **Multi-hop Reasoning** | Associative Graph with IDF-weighted edges | Sequential note traversal | Generative synthesis | Cross-trace linking |
| **Memory Updates** | Assimilation + Accommodation (Piagetian) | Evolutionary refinement | Self-reflection + rewrite | Episodic + semantic update |
| **Retrieval Required?** | **No** — generation replaces retrieval | Yes — dense retrieval for notes | Yes — for initial access | Yes — dense retrieval |
| **Requires Model Access** | Yes — needs token-level logits | No — API-compatible | No — API-compatible | No — API-compatible |

### 4.2 Compared to Paper's Baselines (from §4.3)

| System | Access Method | Key Limitation SCG-MEM Addresses |
|---|---|---|
| **LoCoMo** (no memory) | Full context in prompt | Context window limits, no structured memory |
| **ReadAgent** | Gist compression + interactive lookup | Still retrieval-based, semantic gap |
| **MemoryBank** | Ebbinghaus forgetting curve + dense retrieval | Flat index, semantic≠contextual relevance |
| **MemGPT** | OS-style tiered memory (RAM/disk) | Still uses dense retrieval for access |
| **A-MEM** | Structured notes + dense retrieval + graph traversal | **Still uses dense retrieval for initial node access** — inherits the same noise problem SCG-MEM eliminates |

**Critical distinction:** A-MEM is the closest baseline — it also uses structured memory with graph traversal. But A-MEM still relies on dense retrieval for initial node selection, which SCG-MEM replaces with schema-constrained generation. This is the decisive architectural difference.

---

## 5. Practical Applicability Assessment

### Strengths

1. **Formal Hallucination Guarantee:** The strongest claim — mathematical elimination of structural hallucination by construction. This is not heuristic; it's enforced at the token level.

2. **Small Model Performance:** SCG-MEM on Llama 3.2 1B (41.48 avg F1) outperforms A-MEM on Qwen2.5 3B (21.33 avg F1). The architecture significantly amplifies smaller model capability.

3. **No Embedding Drift:** By eliminating dense retrieval, the system avoids the "semantic similarity ≠ contextual relevance" problem entirely.

4. **Natural Multi-hop Support:** The associative graph with IDF-weighted edges provides principled (not heuristic) multi-hop traversal.

5. **Online Schema Evolution:** The assimilation/accommodation mechanism enables true lifelong learning without costly schema reconstruction.

### Limitations & Concerns

1. **Requires Open-Weights Models:** Schema-constrained decoding needs access to token-level logit distributions. **Cannot work with closed API models** (GPT-4, Claude). This is a significant practical limitation for production use. (§4.4: "Since SCG-MEM requires direct access to token-level probability distributions... we deploy all models locally")

2. **Trie Construction Overhead:** The paper doesn't detail how raw text is distilled into discrete concepts for the Trie. The LLM must extract concepts from each dialogue turn, adding a processing step that could be costly at scale.

3. **Schema Size Scalability:** As the Prefix Trie grows with accommodation, beam search constrained over an expanding Trie could slow down. No scalability analysis provided.

4. **Single Benchmark:** Evaluated only on LoCoMo. No testing on standard QA benchmarks (HotpotQA, MuSiQue), code repositories, or real-world agent deployments.

5. **Hop Depth Limited to 1:** Optimal performance at hop-1 with degradation at hop-2. This limits the system's ability to perform deep multi-hop reasoning.

6. **No Compression/Rewriting:** The paper explicitly identifies these as future work (§5). Without them, the schema will grow unbounded and accumulate noise.

7. **Concept Extraction Quality:** The entire system depends on the quality of the LLM's concept extraction. Poor concept granularity (too coarse or too fine) will cascade through all components.

### Applicability Verdict

| Use Case | Fit | Notes |
|---|---|---|
| **Personal assistant memory** | ✅ Good | Long-term conversations, evolving user knowledge |
| **Research agent memory** | ⚠️ Moderate | Requires open-weights model; Trie may grow large |
| **Code assistant memory** | ⚠️ Moderate | Concepts would be APIs, patterns, project structure |
| **Production API-based agents** | ❌ Poor | Requires closed API models; incompatible by design |
| **Edge/on-device agents** | ✅ Good | Works well on small open-weights models |
| **Multi-agent systems** | ⚠️ TBD | Schema sharing between agents not explored |

---

## 6. Wiki Inclusion Value

### Assessment: **HIGH VALUE** for inclusion

SCG-MEM represents a genuinely distinct 4th paradigm in agent memory architectures:

1. **Novel Access Paradigm:** It's the only architecture that replaces retrieval with constrained generation, providing a formal hallucination guarantee.

2. **Clear Differentiation:** Unlike Bellamem/Genesys/Dual-Trace which all sit within the retrieval-generate spectrum, SCG-MEM occupies its own point — **generative access with structural constraints**.

3. **Strong Empirical Results:** Consistent improvements across all task categories and models, with particularly dramatic gains on smaller models.

4. **Theoretical Grounding:** Piagetian constructivist framework provides a principled basis for schema evolution, not just engineering heuristics.

5. **Clear Limitations Documented:** The API-compatibility requirement is a known constraint, making it easy to position alongside other architectures with their own trade-offs.

### Suggested Wiki Entry Structure

```
## SCG-MEM (Schema-Constrained Generative Memory)
- **Access:** Schema-constrained generation (no retrieval)
- **Structure:** Prefix Trie (schema) + Associative Graph (topology)
- **Updates:** Piagetian assimilation + accommodation
- **Strengths:** Formal hallucination guarantee, strong on small models
- **Weaknesses:** Requires open-weights models, no API compatibility
- **Key Paper:** arXiv:2604.20117 (Zheng et al., UnionPay, 2026)
```

---

## Summary

SCG-MEM introduces a fundamentally different approach to agent memory by reformulating retrieval as schema-constrained generation. Its core innovation — using a Prefix Trie to hard-constrain LLM decoding — provides a mathematical guarantee against structural hallucinations that no retrieval-based system can match. The empirical results on LoCoMo are compelling, particularly the finding that SCG-MEM on a 1B model outperforms retrieval-based baselines on 3B models. The main practical limitation is the requirement for open-weights model access, which excludes closed API deployments. For self-hosted agent systems, especially those running on edge devices or smaller models, SCG-MEM is a strong architectural choice worth serious consideration.
