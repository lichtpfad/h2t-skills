# Exa Evaluation Methodology — Reference

**Source:** docs.exa.ai — "How to Evaluate Exa Search" guide. Pasted by user 2026-04-18.

**Why we keep this:** Exa's own evaluation methodology prescribes exactly the telemetry shape we need to collect via `h2t-evals`. Our schema should mirror theirs for direct benchmarking.

---

## Updated Search Types (supersedes earlier 6-type model)

Exa has consolidated types. The old `auto / fast / instant / deep-lite / deep / deep-reasoning` (6 types) is now:

| Type | Median Latency | Use Case |
|---|---|---|
| `fast` | ~500ms | Speed-critical; SimpleQA, voice agents, autocomplete |
| `auto` (default) | ~1000ms | Balanced; general-purpose, chatbot grounding |
| `deep` | ~5000ms | Comprehensive; agentic workflows, multi-hop research |
| `neural` | embedded | Semantic similarity (incorporated into `fast`/`auto`) |

**Compare within latency classes only.** Don't benchmark `fast` vs `deep` — different use cases, not apples-to-apples.

---

## Recommended Minimal Configuration (from Exa)

```python
exa.search_and_contents(
    query,
    type="auto",                  # or "fast"
    num_results=10,
    text={"max_characters": 15000}
)
```

**Rationale:** adding restrictive parameters (date filters, domain restrictions, text inclusion/exclusion) often causes agents to over-optimize and artificially limit results. Start minimal.

---

## `context` Parameter Deprecated

Old `context={"max_characters": 20000}` is deprecated. Use `text={"max_characters": N}` or `highlights={"max_characters": N}` instead.

**Our spec is fine** — we don't use `context` anywhere.

---

## Deep Search Requires Query Variations

> *"Provide 2-3 query variations using `additional_queries` (Python) or `additionalQueries` (JavaScript) for best results. If not provided, Deep search will automatically generate variations."*

**Our adaptation:** already documented in Step 3 (query variation pattern). `exa_search.py` should:
- Accept `--additional-queries` flag (comma-separated 2-3 variations)
- When `--mode deep` and no variations provided — either pass nothing (Exa auto-generates) OR agent generates 2-3 through LLM reasoning before calling script.

---

## Evaluation Methodology (Four-Phase Workflow)

### Phase 1: Scope Definition

What to measure:
- Retrieval quality (accuracy, relevance)
- Latency
- Freshness
- Cost efficiency
- Agentic suitability

### Phase 2: Dataset Selection

Standard benchmarks Exa publishes results against:

| Benchmark | Focus | Recommended Type |
|---|---|---|
| **SimpleQA** | Single-step factual Q&A | `fast`, `auto` |
| **FRAMES** (single-step) | Single-hop retrieval | `fast`, `auto` |
| **FRAMES** (agentic) | Multi-step reasoning | `deep` |
| **MultiLoKo** | Multi-hop knowledge | `deep` |
| **BrowseComp** | Web browsing comprehension | `deep` |
| **Seal0** | General search quality | all types |
| **WebWalkerQA** | Navigation-style | `fast`, `auto` |
| **HLE** | Hard/long/emerging questions | `deep` |
| **FreshQA** | Time-sensitive | any + `maxAgeHours: 0` |

### Phase 3: Run Configurations

Standard retrieval → synthesis → grading loop:

```python
# 1. Retrieval
results = exa.search_and_contents(query, type="auto", num_results=10, text={...})

# 2. Answer synthesis (downstream LLM restricted to retrieved context)
context = "\n\n".join([r.text for r in results.results])
answer = llm.generate(f"Answer using only context. Q: {query}. A:")

# 3. Grading (LLM-based correctness)
grade = grading_llm.evaluate(question=query, expected=ground_truth, generated=answer)
# Returns: "correct" | "partial" | "incorrect"
```

### Phase 4: Results Analysis

Aggregate metrics:
- **Accuracy** — % correct
- **Partial-credit accuracy** — weighted (correct=1.0, partial=0.5, incorrect=0.0)
- **Retrieval coverage** — % queries where relevant info retrieved
- **P50 latency** — median response time
- **Cost per query** — total / count

---

## Reported Exa Benchmarks (for reference expectations)

**Low-latency (`fast`, <1s):**
- SimpleQA: 94% accuracy @ ~450ms

**Agentic (`deep`, >2s):**
- FRAMES: 96%
- MultiLoKo: 89%

---

## Latency Impact Factors

| Parameter | Impact | Note |
|---|---|---|
| `maxAgeHours: 0` | +500–2000ms | Only when freshness critical |
| AI-generated summaries | +300–800ms | Evaluate necessity |
| `num_results > 10` | +50–200ms | Keep at 10 for fair comparisons |
| Complex date filters | +100–300ms | Simplify when possible |
| Text filtering | +100–500ms | Use sparingly |

---

## Critical Takeaways for Our Design

### 1. Update search type mapping

Our `mode → exa_type` mapping (spec §5.2) uses old type names. Revised mapping:

| mode | type | category | notes |
|---|---|---|---|
| `generic` | `auto` | — | default, balanced |
| `news` | `auto` | `news` | freshness via date filters |
| `academic` | `auto` | `research paper` | full filter support |
| `competitor` | `auto` | `company` | company category |
| `people` | `auto` | `people` | LinkedIn profiles |
| `deep` | `deep` | — | multi-hop, require 2-3 query variations |
| `fast` (NEW) | `fast` | — | sub-second, factual lookups |

**Remove from old mapping:**
- `deep-reasoning` (merged into `deep`)
- `deep-lite` (deprecated)
- `instant` (not documented in eval guide — likely niche)

### 2. Telemetry shape should mirror Exa's evaluation metrics

Our `h2t-evals` telemetry record should enable:
- Accuracy measurement (when ground truth available)
- P50 latency per type
- Cost per query aggregation
- Retrieval coverage

Spec §9 already covers technical metrics. Need to add:
- `ground_truth_id` (optional) — link to known dataset entry
- `grade` (optional) — "correct" | "partial" | "incorrect" when evaluated

### 3. Eval mode in v0.2 roadmap

Add `/research --eval <dataset>` which:
- Iterates through dataset queries
- Runs each with configured mode
- Writes telemetry per query + aggregate stats
- Outputs: accuracy %, P50 latency, total cost

Datasets start as small local JSON files (~20 curated queries per domain). Ground truth validated manually once, then reused.

### 4. Add "fast" mode explicitly

For sub-second factual lookups (user says "quick: what's X?"), agent should route to `mode=fast`. This was missing in our MVP.

---

## Source Quote (Key Principle)

> *"The most important recommendation for fair evaluation: use Exa's default settings. Adding restrictive parameters often causes agents to over-optimize in non-meaningful ways, unnecessarily limiting results and reducing quality without providing valuable insights."*

Translation for our systemprompts: **default templates should be MINIMAL**. Add domain filters or date ranges only when user explicitly requests.
