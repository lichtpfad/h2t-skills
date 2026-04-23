---
title: "Skills v3 Architecture Design"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-04-03"
milestone: ""
---
# Skills v3 Architecture Design

*Created: 2026-04-03 · Updated: 2026-04-06 · Status: living document · Author: Stanislav Glazov + Claude*

### Changelog
- **2026-04-06** — Phase 1 marked complete; Phase 2 progress updated; lib/ structure corrected; h2t-graphs marked live; Skill Intelligence Graph added (Section 14)

---

## 1. Context & Motivation

### Problem

29 h2t skills exist as a monolithic plugin. They lack:
- Coordination between skills (L3 orchestration gap = 2/5 per AIM Sprint)
- Quality measurement (no evals integrated)
- Session telemetry (no central activity tracking)
- Domain boundaries (dev, personal OS, education, creative mixed together)

### Research Findings (12 experiments, 2026-03-31)

Key architectural constraints from hook injection research:
- **Hooks deliver data but cannot control behavior.** systemMessage instructions are ignored by Claude.
- **Linear pipeline in SKILL.md** is the only way to guarantee step execution (including GATEs).
- **Gmail-style CLI pattern** (concrete bash commands) suppresses Claude's manual gather impulse.
- **hookify block** (harness-level enforcement) is the only way to prevent Claude from using native alternatives.
- **Scripts work when Claude has no native alternative** (external APIs). Ignored when Claude can do the task itself.

Source: `docs/research/2026-03-31-hook-injection-vs-skill-instructions.md`

### Goals

1. Skills as **agent interface to Personal OS ETL pipeline** — not standalone tools
2. **Eval-first** — h2t-evals integrated from first commit
3. **Activity stream** — every session registered in central DB
4. **Department split** — skills grouped by domain with clear boundaries
5. **Iterative migration** — no big bang, one department at a time

---

## 2. Positioning

Skills = agent interface layer. Not a standalone system — a layer through which Claude interacts with two backends:

```
                    ┌──────────────┐
                    │  Claude Code │
                    └──────┬───────┘
                           │ invokes
                    ┌──────▼───────┐
                    │  Skills v3   │  ← SKILL.md + Python scripts
                    │  (plugins)   │
                    └──┬───────┬───┴──────────────┐
                       │       │                  │
              writes   │       │  writes    query/write
                       │       │                  │
            ┌──────────▼──┐ ┌──▼──────────────┐ ┌▼───────────────────┐
            │  Activity   │ │  h2t-evals      │ │  h2t-graphs        │
            │  Stream     │ │  (quality)      │ │  skill-patterns    │
            │  (POS DB)   │ │                 │ │  skill-lessons     │
            └─────────────┘ └────────┬────────┘ └────────────────────┘
                                     │ eval findings
                                     └──────────────► skill-lessons
```

**Activity Stream** = time/task management. What was done, when, which artifacts, evidence of task completion. Each agent session = potential insights, generated artifacts, closed tasks. Part of knowledge graph.

**h2t-evals** = productivity and quality metrics. How well the agent performed.

They communicate (eval references activity, activity can pull quality score), but they are separate entities with different purposes and storage.

**Activity Stream storage:** PostgreSQL as primary (time-series, aggregations). h2t-graphs as projection Phase 2+.

**h2t-graphs status:** Live at `graphs.lichtpfadstudio.com`. Existing sources: `creative`, `triz`, `design-thinking`, `td`, `courses-en`, `courses-ru`. New sources `skill-patterns` + `skill-lessons` added in Phase 3 (Skill Intelligence Graph — see Section 14).

---

## 3. Three Types of Skills

| Type | Pattern | Examples | Eval level |
|------|---------|---------|------------|
| **ETL skill** | Python script ingests/publishes data, Claude interprets | gmail, notion, calendar, telegram, session-start | Level 1: automated metrics in script |
| **Pipeline skill** | SKILL.md = linear pipeline, Claude executes steps | pre-merge-check, github-issues, handoff | Level 1: script metrics where available |
| **Generation skill** | Pure LLM, no external data | deck, design, landing, ceo-council, creative-think | Level 0: activity only, post-hoc |

---

## 4. Departments

### 4.1 h2t-core — Session lifecycle + infrastructure

| Skill | Type | Description |
|-------|------|-------------|
| session-start | ETL | Universal session start — modular gather by project type (git→issues, comms→calendar/gmail) |
| handoff | Pipeline | Session end — writes activity stream + markdown fallback |
| init-project | ETL | Auto-triggers from session-start if directory not registered |
| dev-overview | ETL | Cross-project dashboard |
| setup | Script | Install h2t Python dependencies |
| snap | Script | Desktop capture & interact utility |

### 4.2 h2t-ops — POS operational (ingest + publish adapters)

| Skill | Type | Description |
|-------|------|-------------|
| gmail | ETL | Ingest inbox + publish (send/draft) |
| calendar | ETL | Ingest events + publish (create) |
| notion | ETL | Ingest tasks + publish (create/update) |
| telegram | ETL | Ingest saved messages + publish (post to channel) |
| daily-brief | ETL | Aggregator — API-first with local fallback |
| drive | ETL | Google Drive file browser + MeetGeek sync |

Architecture note: `lib/ingest/` and `lib/publish/` separate read and write adapters. Each skill uses both through standard CLI interface.

**daily-brief target state:** VPS composes brief on schedule (Prefect), skill calls `GET /api/brief/today`. Fallback to local ingest when VPS unavailable.

### 4.3 h2t-edu — Content/education pipeline

| Skill | Type | Description |
|-------|------|-------------|
| process-transcripts | ETL | LLM enrichment of meeting/course transcripts |
| youtube-transcript | Script | Extract YouTube transcripts with chapters |
| convert-meeting-transcript | Script | DOCX → Markdown with speaker names |
| lesson-parser | Pipeline | Parse tutorial transcripts into structured topology |

### 4.4 h2t-dev — Dev tools

| Skill | Type | Description |
|-------|------|-------------|
| pre-merge-check | Pipeline | Security, test, build gates before merge |
| github-issues | Pipeline | Create/update issues with consistent structure |
| gh-memory | Pipeline | GitHub Issues as persistent agent memory |
| milestone-closure | Pipeline | Close milestone when all issues done |

### 4.5 h2t-creative — HTML design & visual generation

| Skill | Type | Description |
|-------|------|-------------|
| deck | Generation | HTML presentations (terminal/editorial styles) |
| design | Generation | HUD design system application |
| landing | Generation | Single-page landing generator |

Future: design system libraries, responsive validation, visual AI integration.

### 4.6 h2t-thinking — Strategic frameworks & conceptual processing

| Skill | Type | Description |
|-------|------|-------------|
| ceo-council | Generation | AI advisor council with persona profiles |
| creative-think | Generation | Creative problem-solving with frameworks |

Future: additional strategic frameworks. Separate brainstorm needed for metrics.

### 4.7 h2t-arch — Architecture diagrams

| Skill | Type | Description |
|-------|------|-------------|
| drawio | Pipeline + Script | Generate and export draw.io diagrams |
| diagram-node | Pipeline | Document architecture diagram nodes |

### 4.8 h2t-research — Research pipeline

| Skill | Type | Description |
|-------|------|-------------|
| nlm | ETL | NotebookLM for large data research |
| node-researcher | ETL | Deep research diagram nodes via Exa API |

Future: newsengine skills, h2t-factory skills.

### creative-thinking plugin — boundary clarification

`creative-thinking` remains a **separate plugin** (`plugins/creative-thinking/`) with its own publisher namespace. The skill `creative-think` stays there as canonical source.

`h2t-thinking` contains only `ceo-council` (migrated from h2t monolith). The two plugins are peers, not merged.

### dev-session-start → session-start — compatibility story

The skill is **renamed** as part of h2t-core extraction. Compatibility plan:
1. Phase 1: new `h2t-core` plugin contains `session-start` (new implementation)
2. Phase 1: `dev-session-start` stays in `plugins/h2t/` as **alias shim** — SKILL.md that simply says "invoke session-start"
3. Phase 2+: alias removed once all references updated (CLAUDE.md, hooks, docs)

This preserves the iterative migration promise — no breaking change on Phase 1 cutover.

### Removed

| Skill | Reason |
|-------|--------|
| ctx-load | Experimental, replaced by session-start v3 |
| session-name | Experimental, merged into session-start v3 |

---

## 5. Repo Structure

```
claude-agent-skills/
├── plugins/
│   ├── h2t-core/
│   │   ├── skills/
│   │   │   ├── session-start/   (SKILL.md + scripts/)
│   │   │   ├── handoff/
│   │   │   ├── init-project/
│   │   │   ├── dev-overview/
│   │   │   ├── setup/
│   │   │   └── snap/
│   │   ├── hooks/
│   │   └── plugin.json
│   │
│   ├── h2t-ops/
│   │   ├── skills/
│   │   │   ├── gmail/
│   │   │   ├── calendar/
│   │   │   ├── notion/
│   │   │   ├── telegram/
│   │   │   ├── daily-brief/
│   │   │   └── drive/
│   │   └── plugin.json
│   │
│   ├── h2t-edu/
│   │   ├── skills/ ...
│   │   └── plugin.json
│   │
│   ├── h2t-dev/
│   │   ├── skills/ ...
│   │   └── plugin.json
│   │
│   ├── h2t-creative/
│   │   ├── skills/ ...
│   │   └── plugin.json
│   │
│   ├── h2t-thinking/
│   │   ├── skills/ ...
│   │   └── plugin.json
│   │
│   ├── h2t-arch/
│   │   ├── skills/ ...
│   │   └── plugin.json
│   │
│   ├── h2t-research/
│   │   ├── skills/ ...
│   │   └── plugin.json
│   │
│   └── creative-thinking/     ← existing, stays separate
│
├── lib/                       ← Shared Python (Phase 1 → future h2t-cli)
│   ├── activity/              ✅ Activity stream writer (writer.py)
│   ├── eval/                  ✅ h2t-evals SDK wrapper (session.py)
│   ├── gather/                ✅ Gather modules (git, github, project, user, stack...)
│   ├── clients/               ✅ API clients (gmail, calendar, notion)
│   ├── cli/                   ✅ CLI utilities
│   ├── skill_graph/           ← h2t-graphs interface: query + write (Phase 3)
│   ├── ingest/                ← ETL read adapters — refactor from clients/ (Phase 2)
│   └── publish/               ← ETL write adapters (Phase 2)
│
│   NOTE — Packaging decision: Claude Code plugin installer copies only one
│   plugin directory into cache. Repo-root lib/ is NOT automatically available
│   to plugins at runtime. Resolution strategy (Phase 1):
│   - update-plugin.sh extended to copy lib/ into each plugin's cache dir
│     alongside skills/, hooks/, etc.
│   - Each plugin references lib/ via relative path from its cache root
│   - Long-term: lib/ extracted as proper installable h2t-cli wheel
│
├── evals/
│   ├── repo.toml              ← Repo identity + thresholds for validate-repo
│   └── manifests/             ← Eval test case scenarios
│
└── docs/
```

---

## 6. Skill Design Patterns

### 6.1 ETL Skill Pattern

```
SKILL.md (gmail-style CLI pattern):
  Step 1: $CLI inbox --limit 20        ← ingest
  Step 2: Из результата выбери важное   ← LLM interpretation
  Step 3: $CLI send --to X --body Y     ← publish (if needed)

scripts/cli.py:
  argparse → calls lib/ingest/<source>.py → JSON stdout

Eval: cli.py calls EvalSession via lib/eval/
Activity: cli.py logs to activity stream via lib/activity/
```

Rule: Claude reliably calls scripts when no native alternative exists (Gmail API, Notion API).

### 6.2 Pipeline Skill Pattern

```
SKILL.md (linear pipeline — each step depends on previous):
  Step 1: Run $GATHER --cwd $(pwd)
  Step 2: Parse output, show briefing
  Step 3: ⛔ GATE — user decision
  Step 4: Execute action
  Step 5: Log result

Hook (optional accelerator):
  PreToolUse → gather script → inject via systemMessage
  Accelerates Step 1 but pipeline in SKILL.md guarantees GATE

Eval: gather/action scripts call EvalSession
Activity: session lifecycle skills write session record
```

Rule: Linear pipeline is the only way to guarantee GATE execution.

### 6.3 Generation Skill Pattern

```
SKILL.md (concrete pipeline, 5+ steps):
  Step 1: Clarify parameters with user
  Step 2: Generate HTML/content per design system
  Step 3: Write to file
  Step 4: Validate (if script exists)

Eval: post-hoc — artifact created? valid?
Activity: artifact → activity stream (logged via PostToolUse hook on Write)
```

Rule: Claude follows concrete pipelines without improvisation.

---

## 7. Metrics Framework

### Per-department metrics

**h2t-core:**

| Metric | Level | Type | Description |
|--------|-------|------|-------------|
| `skills.gather_success_rate` | unit | num | Percentage of data sources that responded |
| `skills.checklist_compliance` | integration | num | Percentage of SKILL.md steps completed (including session naming) |
| `skills.token_consumption` | unit | num | Tokens consumed by skill execution |
| `skills.output_consistency` | integration | num | Format stability between runs |
| `skills.time_to_briefing_ms` | integration | num | Time from invoke to briefing shown |
| `skills.context_loss_rate` | business | num | How often user re-asks for context already in handoff |

**h2t-ops:**

| Metric | Level | Type | Description |
|--------|-------|------|-------------|
| `ops.ingest_success_rate` | unit | num | Script fetch success rate |
| `ops.prioritization_quality` | integration | num | LLM prioritization vs user feedback |
| `ops.brief_completeness` | integration | num | Did user manually check sources after brief? |
| `ops.triage_time_saved_min` | business | num | Time saved on email/task triage |

**h2t-edu:**

| Metric | Level | Type | Description |
|--------|-------|------|-------------|
| `edu.enrichment_quality` | unit | num | Summary accuracy (judge) |
| `edu.backlog_reduction_rate` | business | num | Videos processed per week |

**h2t-dev:**

| Metric | Level | Type | Description |
|--------|-------|------|-------------|
| `dev.gate_pass_rate` | unit | num | All pre-merge gates passed |
| `dev.false_negative_rate` | integration | num | Post-merge regressions after "ok" check |
| `dev.issue_structure_valid` | unit | bool | Labels, milestone, sections correct |

**h2t-creative:**

| Metric | Level | Type | Description |
|--------|-------|------|-------------|
| `creative.html_valid` | unit | bool | Generated HTML is valid |
| `creative.needs_manual_edit` | integration | bool | Did user manually edit output? |
| `creative.design_system_compliance` | integration | num | Judge score for style adherence |

### Three Maturity Levels

| Level | What | When |
|-------|------|------|
| **Level 0: Activity only** | Record skill invocation, artifacts created | New skills, generation skills |
| **Level 1: Automated metrics** | Python script logs success/failure, timing, completeness | ETL skills, pipeline skills |
| **Level 2: Judge + feedback loop** | LLM-as-judge, user feedback, A/B comparison | Mature skills with sufficient volume |

Every skill starts at Level 0 and grows to Level 1-2 as it stabilizes.

---

## 8. h2t-evals Integration (from day 0)

### SDK usage in every Python script

```python
# lib/eval/session.py — thin wrapper over h2t-evals SDK
from h2t_evals.sdk import EvalClient, EvalSession

def skill_eval(skill: str, domain: str, project: str) -> EvalSession:
    client = EvalClient(
        service_url=os.getenv("H2T_EVALS_SERVICE_URL", "http://127.0.0.1:8088"),
        token=os.getenv("H2T_EVALS_TOKEN"),
        spool_path="./.h2t_evals_spool.db",
    )
    return EvalSession(
        client=client,
        repo="claude-agent-skills",
        framework="h2t-skills",
        source=f"{skill}:v3",
        eval_set_id=f"{skill}-baseline-v1",
        host=socket.gethostname(),
        run_env="agent",
    )
```

Data flow: `EvalSession` → local spool.db → sync to h2t-evals service on VPS.

### repo.toml

```toml
repo = "claude-agent-skills"
framework = "h2t-skills"
default_source = "h2t-core:v3"

[thresholds.unit]
core_tool_call_success_rate = 0.95

[thresholds.integration]
core_task_success = 0.85
```

### CI gate

```yaml
# .github/workflows/evals.yml
- name: Validate evals compliance
  run: h2t-evals validate-repo --repo-config evals/repo.toml
```

### Tracker issues

After integration: report in h2t-evals#44 (M3) and h2t-evals#45 (M5) per runbook format.

---

## 9. Ingest Architecture + VPS Deployment

### Two Runtime Modes

**Mode 1: Local (Phase 1-2)**
```
Claude Code → skill call → lib/ingest/<source>.py → JSON stdout → Claude interprets
                         → lib/eval/ → spool.db → sync to VPS
                         → lib/activity/ → spool → sync to VPS
```

**Mode 2: VPS (target state)**
```
Prefect (scheduled) → lib/ingest/<source>.py → PostgreSQL cache
Claude Code → skill call → GET /api/brief/today → instant response
```

### One code, two runtimes

Existing ingest scripts in `plugins/h2t/skills/*/scripts/` are working. Task: refactor to standard interface, extract to `lib/ingest/`. Not rewrite from scratch.

```python
# lib/ingest/gmail.py (refactored from existing gmail_cli.py)
class GmailIngestor:
    def fetch_inbox(self, limit=20) -> list[dict]:
        """Same code — local CLI and VPS"""
        ...

    def fetch_since(self, since: datetime) -> list[dict]:
        """For scheduled VPS ingest"""
        ...
```

### VPS Architecture

```
VPS (registered, Ubuntu)
├── POS API (FastAPI, systemd)
│   ├── /api/ingest/*        ← cached data endpoints
│   ├── /api/brief/*         ← pre-composed daily brief
│   ├── /api/activity/*      ← activity stream write/read
│   └── /api/health
│
├── h2t-evals service
│   ├── /v1/sessions/*       ← eval data
│   └── /v1/stats/*
│
├── h2t-graphs (when ready)
│
├── newsengine (possibly)
│
├── Prefect (scheduled jobs)
│   ├── ingest-gmail         ← every 15 min
│   ├── ingest-calendar      ← every 30 min
│   ├── ingest-notion        ← every 30 min
│   ├── ingest-telegram      ← every 60 min
│   ├── compose-brief        ← 07:00 daily + on-demand
│   ├── sync-evals-spool     ← every 5 min
│   └── daily-digest         ← 23:00 daily
│
├── PostgreSQL
│   ├── activity_stream      ← sessions, artifacts, actions
│   ├── ingest_cache         ← latest data per source
│   └── (evals may use same PG or separate SQLite)
│
└── /var/pos/
    ├── spool/               ← incoming from machines
    └── backups/
```

---

## 10. Backfill + Daily Loading

### ETL Pattern

```
EXTRACT                          TRANSFORM                    LOAD
─────────────────               ──────────────               ─────────────
Backfill:                       classify(item)               → PostgreSQL
├── gmail: all since 2022         → {domain, type,           → Knowledge graph
├── notion: all tasks               project, priority}         (h2t-graphs,
├── DOR vault: all .md          normalize                      Phase 2+)
├── GetCourse: Q&A export         → unified schema           → Eval metrics
└── transcripts: 619 vids      deduplicate                     (where applicable)
                                  → by source_id
Incremental:                    enrich (optional)
├── gmail: since last_run         → LLM summary, tags
├── calendar: next 7 days
├── notion: modified > last
├── telegram: new messages
└── github: new events
```

### Backfill Strategy

```
Phase 1: Schema + incremental only
  → Define unified schema per entity type
  → Start incremental ingest on VPS
  → NO backfill yet — stabilize pipeline first

Phase 2: Backfill by source (one at a time)
  → Gmail archive (MBOX export → parse → load)
  → Notion tasks (full export → normalize → load)
  → DOR vault (scan .md → frontmatter → load)
  → Each backfill = separate Prefect flow with checkpoint/resume

Phase 3: Heavy backfill
  → GetCourse Q&A (4 years, JSON export)
  → Transcripts (619 enriched videos)
  → Telegram archives
```

### Checkpoint/Resume

```python
class BackfillJob:
    source: str          # "gmail", "notion", "dor-vault"
    cursor: str          # last processed ID / timestamp
    total: int           # estimated total items
    processed: int       # items loaded so far
    status: str          # "running" | "paused" | "completed"
```

If backfill interrupted — restart from cursor, not from beginning.

### Daily Schedule (VPS)

```
07:00  compose-brief (gmail + calendar + notion → brief cache)
*/15   ingest-gmail (delta since last)
*/30   ingest-calendar (next 7 days refresh)
*/30   ingest-notion (modified tasks)
*/60   ingest-telegram (new saved messages)
*/5    sync-evals-spool (collect from AUTOMATA + MacBook)
23:00  daily-digest (summarize day → activity stream)
```

---

## 11. Migration Plan

### Principle: iterative, one department at a time, max ROI first

### Phase 1: Foundation (h2t-core + lib/) ✅ COMPLETE

| Step | Action | Status |
|------|--------|--------|
| 1.1 | Create `lib/activity/` — activity stream writer | ✅ writer.py |
| 1.2 | Create `lib/eval/` — thin wrapper over h2t-evals SDK | ✅ session.py |
| 1.3 | Extract `plugins/h2t-core/` from monolith | ✅ v3.0.12 |
| 1.4 | Rewrite session-start v3 | ✅ live |
| 1.5 | Rewrite handoff v3 | ✅ live |
| 1.6 | Delete ctx-load, session-name | ✅ removed |
| 1.7 | Add `evals/repo.toml` + CI gate | ⬜ pending |
| 1.8 | Report in h2t-evals#44 and #45 | ⬜ pending |

### Phase 2: Daily Drivers (h2t-ops + h2t-dev) 🔄 IN PROGRESS

| Step | Action | Status |
|------|--------|--------|
| 2.1 | Extract `plugins/h2t-ops/` | 🔄 5/6 skills (drive missing — #37) |
| 2.2 | Refactor existing ingest scripts → `lib/ingest/` | ⬜ clients/ exists, needs ingest/ refactor |
| 2.3 | Add `lib/publish/` | ⬜ pending |
| 2.4 | Extract `plugins/h2t-dev/` | ⬜ scaffold + 4 skills (#26–30) |
| 2.5 | daily-brief: API-first + local fallback | ⬜ pending |

Eval Level: ops → Level 1. Dev → Level 0.

### Phase 3: Domain-specific (as needed)

| Department | When | Trigger |
|------------|------|---------|
| h2t-edu | Return to transcription pipeline | Enrichment sprint |
| h2t-creative | Next landing/presentation needed | + brainstorm design system |
| h2t-thinking | Metrics brainstorm done | Separate session |
| h2t-arch | Next diagram needed | Stable, low priority |
| h2t-research | newsengine/factory start | Business priority dependent |

### Monolith shrinkage

Actual count: 30 skills in `plugins/h2t/skills/` (verified).
ctx-load and session-name are deleted (not migrated), dev-session-start becomes alias shim.

```
Now:     plugins/h2t/ (30 skills)

Phase 1: Extract h2t-core (6: session-start, handoff, init-project, dev-overview, setup, snap)
         dev-session-start stays as alias shim
         Delete: ctx-load, session-name
         Result: plugins/h2t-core/ (6) + plugins/h2t/ (22 = 30-6-2)

Phase 2: Extract h2t-ops (6) + h2t-dev (4)
         Result: + plugins/h2t-ops/ + plugins/h2t-dev/ + plugins/h2t/ (12 = 22-6-4)
         Remove dev-session-start alias shim
         Result: plugins/h2t/ (11)

Phase 3: Extract h2t-edu (4), h2t-creative (3), h2t-thinking (1), h2t-arch (2), h2t-research (2)
         Total extracted: 12
         Result: plugins/h2t/ (0) → deleted
```

Skills remaining for Phase 3 (11): ceo-council, deck, design, landing, drawio, diagram-node,
node-researcher, process-transcripts, youtube-transcript, convert-meeting-transcript,
lesson-parser, nlm (also 1 for h2t-thinking from h2t-arch node-researcher moves to h2t-research)

---

## 12. Parking Lot (separate sessions)

| # | Topic | Type |
|---|-------|------|
| 1 | Data ontology: vault organization, what data to load, backfill processing | Design session |
| 2 | Git naming convention: issues, branches, statuses + mandatory PR/review check across repos | Standard |
| 3 | h2t-creative: design system library, visual validation, responsive, style library | Brainstorm |
| 4 | h2t-thinking: metrics and architecture for creative-think + ceo-council | Brainstorm |
| 5 | h2t-research: metrics and architecture for node-researcher + nlm + newsengine | Brainstorm |
| 6 | Activity stream schema: PostgreSQL table design, artifact registration | Design session |
| 7 | VPS deployment: POS API setup, Prefect configuration, PostgreSQL schema | Implementation |
| 8 | update-plugin.sh: extend to copy lib/ into each plugin cache + add multi-plugin support | Phase 1 prerequisite |

---

## 13. Key Architectural Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Hybrid approach: departments in monorepo, ETL pattern for new/rewritten skills | Iterative migration, no big bang |
| 2 | Session lifecycle is system layer, not dev-specific | session-start serves any session type |
| 3 | Two data layers: Activity Stream (PostgreSQL) + h2t-evals (quality metrics) | Different purposes: operations vs quality |
| 4 | Activity Stream → PostgreSQL primary, h2t-graphs as projection Phase 2+ | PG already on VPS, graphs not stable yet |
| 5 | Ingest adapters: one code, two runtimes (local CLI + VPS Prefect) | Refactor existing scripts, don't rewrite |
| 6 | daily-brief: API-first with local fallback | VPS not ready yet, but architecture prepared |
| 7 | Eval-first: h2t-evals from first commit of Phase 1 | Stepan's rule: no skills without metrics |
| 8 | Three eval maturity levels: Activity → Automated → Judge | Natural growth path per skill |
| 9 | Skills = agent interface to ETL ingestors, not standalone tools | Part of POS, not independent system |
| 10 | DOR = pure knowledge vault, skills extracted | Historical accident corrected |
| 11 | h2t-graphs is live — use directly, no PostgreSQL transit for skill knowledge | graphs.lichtpfadstudio.com is stable |
| 12 | Two graph sources: skill-patterns (research) + skill-lessons (runtime) | Different provenance and update cadence |
| 13 | LLM enrichment step between research and graph write | Raw research needs normalization before storage |
| 14 | Developer review gate before GEPA patterns applied to SKILL.md | Prevent garbage-in-garbage-out loop |

---

---

## 14. Skill Intelligence Graph (Phase 3)

Skills are developed from base model memory without access to accumulated project knowledge.
Errors repeat across sessions because there is no persistent record of what failed and why.

**Solution:** Two h2t-graphs sources with cross-links — full spec in
`docs/superpowers/specs/2026-04-06-skill-intelligence-graph-design.md`

### Sources

| Source | What | Updated by |
|--------|------|------------|
| `skill-patterns` | Best practices from research (hooks, ETL, pipeline, eval, marketplace) | Research subagents → LLM enrichment |
| `skill-lessons` | Runtime lessons: bugs, anti-patterns, eval findings | SKILL.md explicit step + EvalSession.close() |

### Integration in SKILL.md

Every skill gets two optional steps:
1. **Before unclear work:** `skill_graph query --context "<problem>" --skill "<name>"`
2. **After debug resolution:** `skill_graph add-lesson --trigger "..." --resolution "..."`

### Research pipeline (Phase 3.1)

5 parallel subagents (haiku + exa-ai):

| Agent | Source | Method |
|-------|--------|--------|
| gstack-researcher | github.com/anthropics/gstack | git codebase analysis |
| superpowers-researcher | superpowers marketplace repo | SKILL.md pattern analysis |
| plugin-dev-researcher | `.claude/plugins/cache/claude-plugins-official/plugin-dev/` | local files |
| eval-researcher | GEPA, DSPy, agent eval papers | exa-ai search |
| claude-docs-researcher | Claude Code hooks/skills API | context7 |

Raw JSON → LLM enrichment (normalize, dedup, score) → batch write to `skill-patterns`.

### GEPA loop (Phase 3.3)

```
EvalSession → skill-lessons (eval-finding) → LLM-as-judge → skill-patterns (eval-derived)
                                                                      ↓
                                                         Developer review gate
                                                                      ↓
                                                              Applied to SKILL.md
```

### lib/skill_graph/

```python
SkillGraphClient.query(context, skill_name, top_k) → list[dict]
SkillGraphClient.add_lesson(skill_name, trigger, resolution, ...) → node_id
SkillGraphClient.add_pattern(pattern_type, title, body, source, ...) → node_id
```

---

## References

- Hook research: `docs/research/2026-03-31-hook-injection-vs-skill-instructions.md`
- Architecture vision v1: `docs/superpowers/specs/2026-03-30-skill-architecture-vision.md`
- h2t-evals design: `github.com/lichtpfad/h2t-evals/docs/h2t-evals-design.md`
- h2t-evals integration standard: `github.com/lichtpfad/h2t-evals/docs/h2t-evals-repo-integration-standard.md`
- Agent runbook M3-M5: `C:/dev/h2t-evals/docs/ops/agent-runbook-m3-m5.md`
- POS architecture v2: `github.com/lichtpfad/POS/docs/specs/2026-03-21-pos-architecture-v2.md`
- AIM Sprint week 1-2: `C:/Users/stani/aim-sprint/`
- Project registry: `github.com/lichtpfad/h2t-landings/projects.yaml`
