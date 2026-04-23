---
title: "Skill Intelligence Graph — Design"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-04-06"
milestone: ""
---
# Skill Intelligence Graph — Design

*Created: 2026-04-06 · Updated: 2026-04-07 · Status: approved design · Author: Stanislav Glazov + Claude*

### Changelog
- **2026-04-07** — Fixed P1: EvalSession interface aligned with SkillEval context manager; P1: added source bootstrap step; P2: cross-link schema with typed edges; P2: dual-token policy; P2: renamed internal phases to Step 6.x

---

## 1. Problem

Skills are developed from model base memory without understanding how they actually work. Errors repeat
across sessions because there is no persistent memory of what failed and why. The existing design doc
(skills-v3-architecture-design.md) establishes the infrastructure, but lacks a knowledge layer for
skill-specific patterns and lessons.

**Root causes:**
- No persistent storage of debugging resolutions
- No research-backed pattern library for skill authoring
- Eval results not feeding back into development practice

---

## 2. Solution: Skill Intelligence Graph

Two h2t-graphs sources with cross-links:

```
Research subagents                  Debug/Eval runtime
(gstack, superpowers,               (skill execution,
 claude-docs, eval-lit)              h2t-evals)
        │                                   │
        ▼  LLM Enrichment                   ▼
  skill-patterns                    skill-lessons
  (best practices,                  (что сломалось,
   hook patterns,                    как починили,
   eval criteria,                    eval scores,
   marketplace signals)              crosslinks)
        │◄──────── crosslinks ──────────────►│
        └───────────────┬───────────────────┘
                        │
                 h2t-graphs API
                 (graphs.lichtpfadstudio.com)
                        │
             ┌──────────▼──────────┐
             │  lib/skill_graph/   │
             │  query() + write()  │
             └──────────┬──────────┘
                        │
        ┌───────────────▼────────────────┐
        │           SKILL.md             │
        │  Step N: query graph if stuck  │
        │  Step M: write lesson resolved │
        └────────────────────────────────┘
```

---

## 3. Graph Sources

### 3.1 `skill-patterns` — static knowledge from research

Node schema:
```json
{
  "pattern_type": "hook | etl | pipeline | generation | eval | marketplace | trigger | eval-derived",
  "applies_to": ["session-start", "etl-skills", "all"],
  "title": "string",
  "body": "string — actionable description of the pattern",
  "source": "gstack | superpowers | plugin-dev | claude-docs | eval-literature",
  "source_url": "string (optional)",
  "confidence": 0.0–1.0,
  "tags": ["hook", "injection", "gate", ...]
}
```

### 3.2 `skill-lessons` — runtime knowledge

Node schema:
```json
{
  "lesson_type": "bug | anti-pattern | eval-finding | regression",
  "skill_name": "string",
  "trigger": "string — what caused the issue",
  "resolution": "string — how it was fixed",
  "eval_score_before": "float (optional)",
  "eval_score_after": "float (optional)",
  "session_id": "string",
  "date": "ISO 8601",
  "crosslinks": [
    {"to": "pattern_id_1", "relation": "caused_by"},
    {"to": "pattern_id_2", "relation": "resolves_via"}
  ]
}
```

### 3.3 Cross-links

Edge schema — each crosslink entry has two fields:
```json
{"to": "<node_id>", "relation": "<relation_type>"}
```

| Relation | Origin | Target | Meaning |
|----------|--------|--------|---------|
| `caused_by` | lesson | pattern | Anti-pattern in skill-patterns caused this lesson |
| `resolves_via` | lesson | pattern | Resolution matches a known pattern |
| `confirms` | lesson | pattern | Eval finding confirms a pattern's value |
| `contradicts` | lesson | pattern | Finding contradicts an assumed best practice |

**Transactional rule:** When `add_lesson()` is called with crosslinks, `SkillGraphClient` also patches each referenced pattern node to add a reverse edge (eventual consistency — patch failure is logged but does not roll back the lesson write).

---

## 4. Python Interface: `lib/skill_graph/`

```python
# lib/skill_graph/client.py

class SkillGraphClient:
    def query(
        self,
        context: str,
        skill_name: str = None,
        sources: list[str] = ("skill-patterns", "skill-lessons"),
        top_k: int = 5,
    ) -> list[dict]:
        """
        Semantic search across skill-patterns and skill-lessons.
        Called from SKILL.md when stuck or before writing a new skill.
        """
        ...

    def add_lesson(
        self,
        skill_name: str,
        trigger: str,
        resolution: str,
        lesson_type: str = "bug",
        session_id: str = None,
        eval_score_before: float = None,
        eval_score_after: float = None,
        crosslinks: list[dict] = None,  # [{"to": node_id, "relation": relation_type}]
    ) -> str:
        """
        Write a lesson learned. Called after debug resolution or from SkillEval.__exit__.
        Patches referenced pattern nodes with reverse edges (eventual consistency).
        Returns node ID.
        """
        ...

    def add_pattern(
        self,
        pattern_type: str,
        title: str,
        body: str,
        source: str,
        applies_to: list[str] = None,
        confidence: float = 0.7,
        source_url: str = None,
        tags: list[str] = None,
    ) -> str:
        """
        Write a best-practice pattern. Called by research subagents.
        Returns node ID.
        """
        ...
```

**Token policy** — project-scoped (h2t-graphs#98 diagnosis, fixed in #99):
- `query()` → `H2T_SKILL_GRAPH_TOKEN_RO`
- `add_lesson()`, `add_pattern()` → `H2T_SKILL_GRAPH_TOKEN_RW`
- Project ID → `H2T_SKILL_GRAPH_PROJECT_ID`
- All read from `~/.dor/secrets.env`; source IDs constructed as `{project_id}-{alias}`

After h2t-graphs#99 lands, source access:
```
GET /api/query?source={project_id}-skill-patterns   + H2T_SKILL_GRAPH_TOKEN_RO
POST /api/nodes  {"source_id": "{project_id}-skill-patterns", ...}  + H2T_SKILL_GRAPH_TOKEN_RW
```

---

## 5. Integration Points

### 5.1 SKILL.md — query on stuck

Every SKILL.md that interacts with graph adds an optional step:

```markdown
## Before starting (if context is unclear)

Run:
$H2T_PYTHON "$SKILL_GRAPH" query --context "<problem description>" --skill "<skill-name>"

If results contain relevant patterns or lessons, apply them before proceeding.
```

### 5.2 SKILL.md — write lesson on resolve

After a debugging session resolves an issue:

```markdown
## After resolving a bug or unexpected behavior

Run:
$H2T_PYTHON "$SKILL_GRAPH" add-lesson \
  --skill "<skill-name>" \
  --trigger "<what broke>" \
  --resolution "<what fixed it>" \
  --session-id "<SESSION_NAME>"
```

### 5.3 SkillEval — automatic lesson on failure

`lib/eval/session.py` uses `SkillEval` context manager (no `close(score)` or `score_before`).
Integration point is `__exit__` when `exc_type is not None` (skill raised an exception).

**Interface change in `SkillEval.__init__`:**
```python
def __init__(self, skill, domain, project, plugin_version="", evals_root=None,
             skill_graph=None):   # ← add optional SkillGraphClient
    ...
    self._skill_graph = skill_graph
```

**In `__exit__`:**
```python
def __exit__(self, exc_type, exc_val, exc_tb):
    status = "failure" if exc_type else "success"
    ...
    if status == "failure" and self._skill_graph:
        self._skill_graph.add_lesson(
            skill_name=self.skill,
            trigger=str(exc_val) if exc_val else "skill execution failure",
            resolution="",   # filled manually via SKILL.md step 5.2 after debug
            lesson_type="eval-finding",
        )
    return False
```

Note: `resolution` is empty at write time — it is a failure marker. The actual resolution
is written separately via SKILL.md step 5.2 once the developer fixes the issue.
Baseline score tracking is not applicable — `SkillEval` uses pass/fail status, not numeric scores.
Numeric eval scores come from h2t-evals SDK (`s.metric(...)`) and are processed by GEPA batch (#60).

---

## 6. Research Pipeline

5 subagents in parallel, all on haiku model + exa-ai for web search.

### Pipeline

```
Subagents (parallel, haiku)
        │
        ▼
   Raw JSON output
        │
   LLM Enrichment    ← normalize, deduplicate, score confidence
        │
   Batch write
        │
   skill-patterns source
```

### Subagents

| # | Agent | Source | Method |
|---|-------|--------|--------|
| 1 | gstack-researcher | github.com/anthropics/gstack | git clone → codebase analysis |
| 2 | superpowers-researcher | superpowers marketplace repo | git clone → SKILL.md analysis |
| 3 | plugin-dev-researcher | `.claude/plugins/cache/claude-plugins-official/plugin-dev/` | Read local files |
| 4 | eval-researcher | GEPA, DSPy evals, agent eval papers | exa-ai search |
| 5 | claude-docs-researcher | Claude Code hooks API, skills spec, marketplace | context7 |

### Output format per agent (raw JSON before enrichment)

```json
{
  "source": "gstack",
  "patterns": [
    {
      "pattern_type": "hook",
      "title": "PreToolUse for data injection",
      "body": "...",
      "source_url": "...",
      "raw_confidence": 0.8
    }
  ]
}
```

### Enrichment step (single LLM pass over all agent outputs)

- Normalize `pattern_type` to canonical enum
- Deduplicate near-identical patterns (merge, keep highest confidence)
- Score `confidence` based on: source authority + specificity + actionability
- Tag with `applies_to` based on body content
- Write to `skill-patterns` via `add_pattern()`

---

## 7. GEPA Integration (Generative Eval Pipeline Architecture)

GEPA is the auto-improvement loop:

```
Skill runs → SkillEval records → eval-findings in skill-lessons
                                           │
                         LLM-as-judge reviews skill-lessons
                                           │
                         generates improvement suggestions
                                           │
                         writes back as skill-patterns (type="eval-derived")
                                           │
                         developer applies to SKILL.md
```

This closes the loop: eval → lesson → pattern → better skill → eval.

**Trigger:** batch job run manually or on schedule, reads `skill-lessons` where `lesson_type="eval-finding"` and `date > last_gepa_run`.

---

## 8. Implementation Steps (Phase 6 — skill-graph)

Numbering matches GitHub milestone "Phase 6 — skill-graph". Skills-v3 architecture doc
refers to this block as "Phase 3" in its own phase numbering — this spec uses Step 6.x
to avoid collision.

### Step 6.0: Bootstrap graph sources (#55)

Before any code runs, `skill-patterns` and `skill-lessons` sources must exist in h2t-graphs.

| Action | Detail |
|--------|--------|
| Check `/docs` endpoint | Confirm source creation API |
| Create `skill-patterns` | Via h2t-graphs admin API or config |
| Create `skill-lessons` | Via h2t-graphs admin API or config |
| Smoke test | `curl .../api/query?source=skill-patterns&search=test` returns empty `[]`, not 404 |

If h2t-graphs has no self-serve source creation, coordinate with h2t-graphs repo directly.
Sources must be queryable before Step 6.1.

### Step 6.1: lib/skill_graph/ + CLI (#56)

| Action | Detail |
|--------|--------|
| Implement `lib/skill_graph/client.py` | query (RO token), add_lesson, add_pattern (RW token) |
| Implement `lib/skill_graph/cli.py` | argparse: `query`, `add-lesson`, `add-pattern` subcommands |
| Tests | mock h2t-graphs API, test dual-token selection, crosslink patch logic |

### Step 6.2: Research pipeline → skill-patterns (#57)

| Action | Detail |
|--------|--------|
| Run 5 parallel subagents (haiku + exa-ai) | raw JSON per agent |
| LLM enrichment pass | normalize, dedup, score confidence |
| Batch write to `skill-patterns` | via `add_pattern()` |
| Verify | ≥50 patterns, all `pattern_type` categories covered |

### Step 6.3: SKILL.md integration (#58 + #59)

| Action | Detail |
|--------|--------|
| Add query step to session-start, handoff, gmail, github-issues | optional, before unclear work |
| Add lesson-write step to same skills | explicit, after debug resolution |
| Patch `SkillEval.__init__` + `__exit__` | optional `skill_graph` param, failure → add_lesson |

### Step 6.4: GEPA batch job (#60)

| Action | Detail |
|--------|--------|
| Read skill-lessons where `lesson_type=eval-finding` | since last_gepa_run |
| LLM-as-judge → improvement suggestions | structured output |
| Staging list | human-readable, not auto-written to graph |
| Developer review → approve → write to `skill-patterns` | `pattern_type=eval-derived` |

---

## 9. Key Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Two sources (skill-patterns + skill-lessons) with crosslinks | Different provenance and update cadence |
| 2 | h2t-graphs directly, no PostgreSQL transit layer | API is live and stable |
| 3 | LLM enrichment between research and graph write | Raw research output needs normalization |
| 4 | Haiku for all research subagents | Cost efficiency for bulk research |
| 5 | GEPA as batch job, not real-time | Enough volume needed for meaningful patterns |
| 6 | Developer review gate before GEPA patterns applied | Prevent garbage-in-garbage-out loop |
| 7 | SkillEval writes empty-resolution lesson on failure, not on score delta | SkillEval has no numeric score; resolution filled separately via SKILL.md |
| 8 | Source bootstrap is Step 6.0, blocking all other steps | Sources must exist before any read/write |
| 9 | Cross-link edges typed: `{to, relation}`, patched on both nodes eventually | h2t-graphs has no native edge API; eventual consistency accepted |
| 10 | Dual-token: RO for query, RW for write | Mirrors graphs-api.md security policy |

---

## References

- Skills v3 architecture: `docs/superpowers/specs/2026-04-03-skills-v3-architecture-design.md`
- Hook injection research: `docs/research/2026-03-31-hook-injection-vs-skill-instructions.md`
- h2t-graphs API: `C:/Users/stani/.h2t/config/rules/graphs-api.md`
- h2t-evals design: `github.com/lichtpfad/h2t-evals/docs/h2t-evals-design.md`
