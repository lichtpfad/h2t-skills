# Skill Intelligence Graph — Design

*Created: 2026-04-06 · Status: approved design · Author: Stanislav Glazov + Claude*

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
  "pattern_type": "hook | etl | pipeline | generation | eval | marketplace | trigger",
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
  "crosslinks": ["pattern_id_1", "pattern_id_2"]
}
```

### 3.3 Cross-links

Cross-links are bidirectional and stored in both nodes:

| Relation | Direction | Meaning |
|----------|-----------|---------|
| `caused_by` | lesson → pattern | Anti-pattern in skill-patterns caused this lesson |
| `resolves_via` | lesson → pattern | Resolution matches a known pattern |
| `confirms` | lesson → pattern | Eval finding confirms a pattern's value |
| `contradicts` | lesson → pattern | Finding contradicts an assumed best practice |

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
        crosslinks: list[str] = None,
    ) -> str:
        """
        Write a lesson learned. Called after debug resolution or from EvalSession.close().
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

Credentials: `H2T_GRAPHS_TOKEN_RW` from `~/.dor/secrets.env`

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

### 5.3 EvalSession — automatic lesson on close

`lib/eval/session.py` calls `add_lesson()` on session close if score delta is significant:

```python
def close(self, score: float):
    if abs(score - self.score_before) > 0.1:
        self.graph.add_lesson(
            skill_name=self.source,
            trigger="eval score change",
            resolution=f"score {self.score_before:.2f} → {score:.2f}",
            lesson_type="eval-finding",
            session_id=self.session_id,
            eval_score_before=self.score_before,
            eval_score_after=score,
        )
```

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
Skill runs → EvalSession records → eval-findings in skill-lessons
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

## 8. Implementation Phases

### Phase 1: lib/skill_graph/ + research run

| Step | Action |
|------|--------|
| 1.1 | Implement `lib/skill_graph/client.py` |
| 1.2 | Run 5 research subagents → raw JSON |
| 1.3 | LLM enrichment pass → populate `skill-patterns` |
| 1.4 | CLI wrapper: `skill_graph query` + `skill_graph add-lesson` |

### Phase 2: SKILL.md integration

| Step | Action |
|------|--------|
| 2.1 | Add query step to 3-5 highest-frequency skills (session-start, handoff, gmail, github-issues) |
| 2.2 | Add lesson-write step to same skills |
| 2.3 | Wire EvalSession → add_lesson on score delta |

### Phase 3: GEPA loop

| Step | Action |
|------|--------|
| 3.1 | Implement batch GEPA job |
| 3.2 | LLM-as-judge review of skill-lessons |
| 3.3 | Auto-generate improvement patterns → skill-patterns |
| 3.4 | Developer review gate before applying to SKILL.md |

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

---

## References

- Skills v3 architecture: `docs/superpowers/specs/2026-04-03-skills-v3-architecture-design.md`
- Hook injection research: `docs/research/2026-03-31-hook-injection-vs-skill-instructions.md`
- h2t-graphs API: `C:/Users/stani/.h2t/config/rules/graphs-api.md`
- h2t-evals design: `github.com/lichtpfad/h2t-evals/docs/h2t-evals-design.md`
