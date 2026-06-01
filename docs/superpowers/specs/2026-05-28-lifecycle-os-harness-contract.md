---
title: "Lifecycle OS Harness Contract"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-28"
milestone: "lifecycle-os"
related:
  - "docs/superpowers/specs/2026-05-27-dev-github-skills-refactor-design.md"
  - "docs/superpowers/specs/2026-05-22-h2t-core-setup-update-lifecycle-context-budget-design.md"
  - "docs/superpowers/specs/2026-05-26-session-continuity-redesign.md"
  - "#196"
  - "#197"
  - "#211"
  - "#240"
---

# Lifecycle OS Harness Contract

## Purpose

Lifecycle OS is not a set of documentation utilities. It is the project harness
that makes work resumable across agents, sessions, machines, and runtimes.

The target state is:

```text
registered project
+ current real task state
+ clean navigable docs
+ executable plans
+ tested changes
+ synced GitHub/roadmap
+ structured handoff
= another agent can resume without archaeology
```

This file is the source-of-truth contract for the Lifecycle OS work split across
`scaffold-project`, `init-project`, `session-start`, `docs-lint`,
`pre-merge-check`, `milestone-closure`, `handoff`, `project-audit`, and
`gh-memory` deprecation.

Earlier specs remain useful for history and implementation detail. When they
conflict with this contract, this contract wins.

## Design Inputs

- The live Rejuve `docs-lint` run showed that metadata-only linting is the wrong
  main job. The expected output is a clean indexed documentation system, not a
  list of frontmatter fixes.
- `session-start` and `handoff` improved planning quality, but unbounded
  markdown handoff is too expensive as a runtime context source.
- GitHub issues and milestones are the current project-management backend.
  Handoff memory must not override real open issue state.
- AIM harness practice confirms the right abstraction: skills are not prompts;
  they are parts of a repeatable operator/harness/tools/environment loop.

## Core Model

Lifecycle OS follows the operator/harness/tools/environment model:

| Layer | In h2t |
|-------|--------|
| Operator | User decisions, safe/destructive boundaries, acceptance review |
| Harness | Session lifecycle, plans, hooks, gates, reports, evidence |
| Tools | Git, GitHub CLI/API, docs scripts, h2t-ops, test runners |
| Environment | Repo, filesystem, GitHub, local config, plugin cache |
| Model | Claude/Codex/Cursor/Gemini runtime using the harness |

The model is intentionally multi-runtime. Runtime-specific files such as
`SKILL.md`, `AGENTS.md`, `CLAUDE.md`, and command wrappers are adapters, not the
canonical lifecycle state.

## Scope and Context Types

Lifecycle OS must support more than one kind of activity context, but v1 has a
clear implementation center.

| Context type | v1 support | Notes |
|--------------|------------|-------|
| `repo` | Full | Git + optional GitHub is the primary v1 path |
| `project` | Full | project may own `current_repo` plus `related_repos` |
| `multi_repo` | Partial | modelled as project/session with related repos |
| `research` | Partial | artifacts may be local; POS ingestion is future |
| `creative` | Partial | may not have GitHub milestone; use local summary/report |
| `personal` / `selfwork` | Minimal | session continuity only in v1 |
| `unknown` | Minimal | gather should report uncertainty, not invent identity |

v1 default is Git/GitHub-backed repo lifecycle. Non-code and personal-OS
sessions are not excluded, but their v1 contract is narrower:

- `session-start` can identify and brief them;
- `handoff` can write bounded local continuity;
- project/task closure may not have a GitHub source of truth;
- docs and milestone gates are skipped unless a repo/docs root exists;
- machine reports must mark missing GitHub/docs state as `skipped_not_applicable`,
  not `pass`.

This prevents repo-centric code paths from silently misrepresenting non-code
work.

### Project Templates

Lifecycle OS should not force all projects into one repo-engineering template.
`scaffold-project` / `init-project` should pick or ask for a template, then
apply the matching baseline.

Initial template set:

| Template | Typical context | Baseline |
|----------|-----------------|----------|
| `code_repo` | software repo | GitHub issues, tests, docs, ADR/spec/plan surfaces |
| `client_project` | client delivery such as Rejuve | docs, research, ops, deliverables, lighter code gates |
| `research_project` | research thread or knowledge work | research artifacts, synthesis, evidence, project links |
| `creative_project` | landing/deck/content work | briefs, assets, variants, review/evidence |
| `personal_os` | selfwork/strategy/vault | session continuity, local notes, optional POS links |
| `ops_workflow` | recurring operational workflow | runbooks, checklists, logs, handoff |

Each template defines:

- required docs directories;
- optional GitHub labels/milestones;
- docs-lint profile;
- pre-merge / pre-close gates;
- handoff fields;
- POS sync expectations.

Templates are configuration, not separate skills.

## Command Contract

Every lifecycle command must produce four things:

1. Human-readable summary.
2. Machine-readable report or state envelope.
3. Safe next action.
4. Evidence, or a concrete reason evidence is unavailable.

For example:

```json
{
  "schema": "h2t_lifecycle_report/v0.1",
  "schema_version": "0.1",
  "command": "docs-lint",
  "repo_root": "C:/work/rejuve",
  "status": "warn",
  "summary": "9 orphan docs, 6 naming violations, README out of date",
  "findings": [
    {
      "type": "orphan",
      "severity": "warn",
      "path": "docs/old-design.md",
      "message": "Not reachable from any README/index",
      "safe_fix": null
    }
  ],
  "safe_next_action": "Run docs-lint plan before any rename/move",
  "evidence": {
    "git_head": "abc123",
    "checked_at": "2026-05-28T00:00:00Z"
  }
}
```

### Schema Compatibility

All machine-readable lifecycle artifacts must include:

- `schema`
- `schema_version`
- `producer`
- `produced_at`
- stable context identity fields where known
- `status`
- `findings` or equivalent detail list

Readers must be forward-compatible:

- ignore unknown fields;
- treat unknown enum values as `unknown`, not fatal;
- preserve unrecognized fields when rewriting state;
- fail with a clear `schema_unsupported` error only when a required field for
  the requested operation is missing.

Existing `latest.json` and archival markdown handoff files remain valid v1
inputs. They are legacy continuity sources, not invalid data. New code should
read them through adapters and write the newer bounded state/report shape. No
task may require deleting or rewriting historical handoff archives as part of a
schema migration.

### POS Alignment for Artifact Versioning

Lifecycle artifact schemas must be synchronized with POS before becoming
canonical beyond local h2t-core runtime.

v1 rule:

- h2t-core remains local authority for runtime continuity;
- POS is a downstream consumer when available;
- lifecycle reports/events use stable `schema` and `schema_version` fields;
- POS ingestion must accept versioned envelopes and store raw source refs;
- schema upgrades require readers that handle at least the previous minor
  version.

The lifecycle report family should align with the POS session envelope direction:

```text
h2t_lifecycle_report/v0.1
pos_session_event/v0.1
research_* /v0.1
```

Do not introduce a lifecycle artifact shape that POS cannot later ingest without
markdown parsing. If POS needs different required fields, update this contract
before implementing the writer.

## POS Integration Contract

Lifecycle OS v1 must not make POS canonical, but it must write artifacts that POS
can ingest without markdown parsing.

### Ownership Boundary

| Surface | v1 owner | Responsibility |
|---------|----------|----------------|
| h2t-core / h2t-dev | local runtime | `session-start`, `handoff`, `latest.json`, lifecycle reports, CLI behavior |
| GitHub | PM truth | issues, PRs, milestones |
| POS | downstream memory | session registry, project graph, accepted decisions/learnings, cross-project context |
| Markdown | mirror/archive | human-readable docs, not canonical machine state |

### Lifecycle Events

Lifecycle commands should be able to emit append-only POS-compatible events when
POS is configured.

Initial event types:

```text
lifecycle.project_registered/v0.1
lifecycle.session_started/v0.1
lifecycle.session_ended/v0.1
lifecycle.docs_health_reported/v0.1
lifecycle.plan_created/v0.1
lifecycle.pre_merge_checked/v0.1
lifecycle.milestone_closed/v0.1
lifecycle.project_audited/v0.1
```

Minimal envelope:

```json
{
  "schema": "h2t_lifecycle_event/v0.1",
  "schema_version": "0.1",
  "event_id": "lifecycle-event:sha256:...",
  "run_id": "lifecycle-run:sha256:...",
  "correlation_id": "session:sha256:...",
  "event_type": "lifecycle.docs_health_reported",
  "occurred_at": "2026-05-28T00:00:00Z",
  "producer": "h2t-dev/docs-lint",
  "privacy": "internal",
  "context": {
    "context_type": "repo",
    "project_id": "project:rejuve",
    "current_repo": {
      "repo_root": "C:/work/rejuve",
      "github": "lichtpfad/rejuve"
    },
    "related_repos": []
  },
  "subject": {
    "type": "project",
    "id": "project:rejuve",
    "title": "Rejuve"
  },
  "status": "warn",
  "severity": "medium",
  "meaning_state": "observed",
  "refs": [
    {
      "type": "report_json",
      "uri": "dor://state/lifecycle/..."
    },
    {
      "type": "markdown_mirror",
      "uri": "docs/..."
    },
    {
      "type": "git_commit",
      "sha": "abc123"
    }
  ]
}
```

Events are short indexable facts. Reports are full artifacts. Events should
reference reports through typed refs rather than embedding large findings,
recommendations, or changed-file lists.

Required event fields:

- `schema`
- `schema_version`
- `event_id`
- `event_type`
- `occurred_at`
- `producer`
- `privacy`
- `context`
- `subject`
- `status`
- `meaning_state`
- `refs`

Optional but recommended:

- `run_id` groups events from one lifecycle command/run;
- `correlation_id` links events to a session, PR, issue, or external workflow;
- `severity` supports filtering without overloading status.

### Event Normalization

`subject` describes what the event is about:

```json
{
  "type": "project|session|plan|pr|issue|milestone|audit|docs|repo|custom",
  "id": "project:rejuve",
  "title": "Rejuve"
}
```

Known subject types are advisory, not a closed runtime enum. POS and other
readers must accept unknown subject types as `unknown`/`custom` and continue
ingestion when required fields are otherwise valid.

`status` uses a small operational enum:

```text
ok | warn | fail | error | skipped | unknown
```

`severity` uses:

```text
info | low | medium | high | critical
```

`meaning_state` uses:

```text
observed | proposed | accepted | rejected | superseded
```

Lifecycle OS v1 should emit mostly `observed` events. Events that propose tasks,
decisions, or knowledge must remain `proposed` until a POS review/acceptance
step promotes them.

`privacy` uses:

```text
public | internal | mixed | personal | restricted
```

Default privacy is `internal`, not `public`. Personal/non-code sessions and
client work should use `personal`, `mixed`, or `restricted` when appropriate.

`refs` is always a list of typed references:

```json
[
  {"type": "report_json", "uri": "dor://state/lifecycle/..."},
  {"type": "markdown_mirror", "uri": "docs/reports/..."},
  {"type": "github_pr", "repo": "lichtpfad/rejuve", "number": 123},
  {"type": "github_issue", "repo": "lichtpfad/rejuve", "number": 45},
  {"type": "git_commit", "sha": "abc123"}
]
```

This keeps POS ingestion indexable without turning the event body into a report.

v1 invariant:

- event is an append-only observed fact;
- report is the full artifact;
- refs are typed;
- subject identifies the target;
- meaning_state prevents accidental promotion;
- POS is an optional downstream consumer.

### POS Ingestion v1

If POS is configured, it consumes lifecycle events as an optional downstream
consumer:

1. append event if `event_id` is unseen;
2. upsert current project/session summary by stable id;
3. index refs/artifacts;
4. preserve raw report refs for traceability;
5. never block local h2t runtime if POS is unavailable.

This gives:

```text
h2t local report = source artifact
POS event log = timeline
POS registry = query surface
POS graph = accepted meaning only
```

### POS Promotion Boundary

Lifecycle findings are observations, not canonical POS knowledge.

POS must distinguish:

```text
observed event
proposed task/decision
accepted task/decision
canonical knowledge
```

Examples:

- `docs_health_reported` may create a `ProjectHealth` snapshot.
- `pre_merge_checked` may create a `QualityGateResult`.
- `milestone_closed` may create `ReleaseEvidence`.
- `project_audited` may create proposed tasks or decisions.

But warnings, findings, and inferred next actions do not become accepted POS
knowledge without review.

Promotion rule:

- event `meaning_state=observed` may create timeline/health/query records;
- event `meaning_state=proposed` may create review queue items;
- only POS review can produce `accepted` decisions, tasks, knowledge, or graph
  edges;
- rejected/superseded events remain audit history.

### POS Roadmap

v1:

- h2t-core/h2t-dev write local lifecycle reports.
- If POS is configured, emit append-only lifecycle events.
- POS is downstream, optional, and idempotent.
- POS may index reports and refs, but does not control runtime.

v1.5:

- POS builds session/project registry from lifecycle events.
- `doctor` compares local `latest.json` / lifecycle reports against POS last
  known state.

v2:

- POS registry becomes historical query surface.
- h2t local `latest.json` remains fast runtime cache.

v3:

- `session-start` asks POS for bounded project/person/domain context.

### POS Non-Goals v1

- Do not make POS required for `session-start`, `handoff`, or docs commands.
- Do not write markdown-only summaries as POS source data.
- Do not treat raw lifecycle findings as accepted knowledge.
- Do not make POS source of truth for GitHub issues in v1.

CLI scripts own deterministic work. Skills are thin orchestrators that call
scripts, interpret structured output, and ask the user before unsafe operations.

## Lifecycle Phases

| Phase | Trigger | User-facing skill | Status |
|-------|---------|-------------------|--------|
| Register / Inventory | existing repo, unknown cwd | `init-project`, `project-audit` | open: no first-class inventory contract |
| Project Init | new repo/project | `scaffold-project` | open: `DEV_ROOT`-centric |
| Session Start | new session | `session-start` | works, but bounded context remains mandatory |
| Plan Work | feature/research task | superpowers plans | not lifecycle-native yet |
| Execute | branch/worktree work | superpowers execution | works outside Lifecycle OS |
| Docs Health | any time, pre-merge, close | `docs-lint` | implemented by #240 / PR #241 |
| Pre-Merge | PR ready | `pre-merge-check` | open: no docs health gate |
| Milestone Close | milestone done | `milestone-closure` | open: separate `docs-index`, broken `gh milestone` assumption |
| Handoff | session end | `handoff` | implemented by #211 / PR #239 |
| Periodic Audit | weekly / on demand | `project-audit` | open: boundary with `docs-lint` not explicit |

## Phase Contracts

### 1. Register / Inventory

Before scaffolding, the harness must inspect what already exists.

Inputs:

- explicit `--repo-root`, or current working directory;
- Git remote and branch;
- GitHub owner/repo if available;
- existing docs layout;
- existing rules, plans, specs, ADRs, roadmaps, memory files;
- existing labels, milestones, open issues, open PRs.

Outputs:

- project identity candidate;
- inventory report;
- missing lifecycle baseline;
- safe scaffold/update plan.

Rules:

- Do not assume the project is under `C:/dev`.
- Do not create files before inventory unless the user explicitly asks for a new
  blank project.
- Existing repo state wins over old handoff and local memory.

### Current Repo and Related Repos

Some real sessions touch more than one repository, for example `h2t-skills` plus
`h2t-ai`. The default model should not be "many equal current repos"; it should
be `current_repo` plus `related_repos`.

v1 rule:

- choose one `current_repo` for command execution;
- include `related_repos` as refs in reports and handoffs;
- run repo-scoped commands such as `docs-lint`, `pre-merge-check`, and
  `milestone-closure` per repo, not across all repos implicitly;
- if a handoff contains work in multiple repos, "what remains" must be grouped
  by repo/context.

Example:

```json
{
  "context_type": "multi_repo",
  "current_repo": {
    "type": "repo",
    "repo_root": "C:/dev/h2t-skills",
    "github": "lichtpfad/h2t-skills"
  },
  "related_repos": [
    {
      "type": "repo",
      "repo_root": "C:/dev/h2t-ai",
      "github": "lichtpfad/h2t-ai",
      "relation": "referenced"
    }
  ]
}
```

Commands must not infer that all related repos are safe to modify. They are
read-only refs unless the user explicitly switches context or approves work
there.

### 2. Project Init

`scaffold-project` is the one-time project setup orchestrator.

Responsibilities:

- create missing lifecycle docs structure;
- install or update repo-local lifecycle rules;
- sync GitHub labels;
- create or validate project registry entry;
- install thin hooks where appropriate;
- write a machine-readable setup report.

Required fixes:

- accept `--repo-root` and respect current working directory;
- support repos outside `DEV_ROOT`;
- call deterministic scripts rather than embedding long shell recipes;
- separate "new repo creation" from "existing repo registration".

### 3. Session Start

`session-start` remains the runtime context entrypoint.

Responsibilities:

- detect context from `cwd`;
- gather real Git/GitHub state;
- show bounded previous context;
- avoid injecting archival handoff bodies;
- make stale handoff subordinate to real issue/PR state.

Boundaries:

- archival markdown can be listed or linked, but not dumped into prompt;
- bounded machine-readable latest state is the runtime continuity source;
- POS publishing is optional and downstream in v1.

### 4. Plan Work

Planning is a lifecycle phase, even when implemented through superpowers.

Every implementation plan should include:

- issue links;
- scope and non-goals;
- acceptance criteria;
- safe/destructive boundary;
- test and evidence plan;
- parallelization notes if subagents/worktrees are useful;
- expected docs/roadmap updates.

Future lifecycle-native planning can write a project registry entry, but v1 may
continue to use existing `docs/superpowers/plans/` files.

### 5. Execute

Execution remains branch/worktree based.

Rules:

- use worktrees for parallel agents;
- keep commits scoped;
- do not reset or clean without explicit confirmation;
- destructive external actions require explicit user approval;
- live-service actions should prefer draft/read-only modes unless user approves.

### 6. Docs Health

`docs-lint` is the unified documentation health and navigation command.

It absorbs the user-facing role of `docs-index`.

Required modes:

```text
docs-lint audit/default   # diagnostics
docs-lint plan            # human-readable cleanup plan
docs-lint fix-safe        # only safe mechanical fixes
docs-lint fix-index       # rebuild README/navigation/index surfaces
docs-lint doctor --json   # machine-readable report for hooks/CI/agents
```

Required checks:

- structure baseline;
- naming convention across docs, not only specs/plans;
- orphan markdown files;
- README/index coverage;
- navigation consistency;
- data/docs boundary;
- stale or superseded plan/spec surfaces;
- frontmatter/metadata as a secondary concern;
- repository root clutter;
- per-repo exceptions.

Rules:

- Index entries must be rebuildable from canonical files.
- If index and file state disagree, file state wins.
- `fix-safe` must not rename, move, archive, delete, or rewrite navigation in a
  way that changes user-facing structure without a plan and user confirmation.
- `fix-index` may rewrite generated navigation surfaces, but must report exactly
  what changed.

Partial execution:

- `plan` writes no changes.
- `fix-safe` may write only changes classified as safe in the report.
- `fix-index` should prefer generated regions in index/README files. Full-file
  regeneration is allowed only after explicit confirmation and must record that
  policy in the report.
- Every apply mode writes an operation report with planned, applied, skipped,
  and failed actions.
- If execution is interrupted, re-running the same command must recompute state
  from disk and continue idempotently; do not rely on hidden in-memory state.
- No checkpoint file is required for `docs-lint fix-index` v1. The recovery
  model is dry-run, explicit apply, operation report, and idempotent recompute
  from canonical files.

### fix-index Bootstrap

When `fix-index` runs on a README or index file with no
`<!-- h2t-index-start -->` / `<!-- h2t-index-end -->` markers:

1. Compute the generated navigation section.
2. Report the planned change as dry-run output without writing.
3. On explicit `--apply`: append the generated section with markers at end of
   file.
4. Write an operation report with before/after state.

First run is always dry-run unless `--apply` is given.

### Backward Compatibility

CLI flags from the legacy API are supported with a deprecation warning to
stderr:

| Legacy flag | v1 equivalent | Deprecation note |
|-------------|---------------|------------------|
| `--fix` | `fix-safe` | removed in v2 |
| `--fix-frontmatter` | `fix-safe --only=frontmatter` | removed in v2 |

Deprecation warnings must go to stderr only and must not affect structured
JSON output.

### Configuration Discovery

`docs-lint` reads per-repo configuration from `.claude/rules/docs-lint.yaml`
if it exists. If absent, built-in defaults apply.

Configurable per-repo:

- docs root (default: `docs/`)
- required directories
- naming convention exceptions
- per-repo template overrides

Configuration must not override core safety boundaries or gate policies.

### 7. Pre-Merge

`pre-merge-check` is the PR readiness gate.

Required checks:

- tests/CI status;
- dirty worktree / accidental generated files;
- linked issues and plans;
- roadmap/docs update if user-facing behavior changed;
- `docs-lint doctor --json` as a soft docs gate.

Docs gate policy:

- warn by default;
- fail only for severe conditions that break navigation or release evidence;
- never auto-rename/move docs during pre-merge.

Gate reports must distinguish:

- `pass`
- `warn`
- `fail`
- `skipped_not_applicable`
- `skipped_missing_context`
- `waived_by_user`

If the user waives a gate, the report must include the reason or mark it
`reason_not_recorded`.

### 8. Milestone Closure

`milestone-closure` closes a phase, not just a GitHub milestone.

Required steps:

1. Resolve owner/repo and current milestone from real GitHub state.
2. Fetch milestones through `gh api repos/{owner}/{repo}/milestones`, not
   `gh milestone list`.
3. Confirm there are no blocking open issues, or explicitly move them.
4. Run `docs-lint plan`.
5. Ask before any archive/move/delete/rewrite action.
6. Run `docs-lint fix-index` after approved cleanup.
7. Update roadmap and release/evidence notes.
8. Write structured milestone closure report.
9. Select next real open item.

GitHub is the authoritative PM state for v1. Roadmaps and handoffs mirror or
explain GitHub state; they do not override it.

Partial closure:

- milestone closure must support dry-run without writes;
- every write step must be individually visible before apply;
- if cleanup/index/roadmap update partially fails, the closure report status is
  `partial`, not `pass`;
- closing the GitHub milestone is the final destructive step and requires
  explicit user confirmation.

### 9. Handoff

`handoff` writes the session continuity boundary.

Required behavior:

- preserve user-confirmed summary interaction;
- write bounded machine-readable latest state;
- write markdown mirror/archive;
- include commits, PRs, issues, artifacts;
- derive "what remains" from live GitHub open P0/P1/blocker issues where
  possible;
- mark inferred items as inferred when no GitHub source exists.

Required fix:

- Step 3 must query real GitHub open issues for the current repo/milestone.

For non-code or non-GitHub sessions, `handoff` must mark "what remains" as
`inferred_from_conversation` or `local_state`, not as GitHub-confirmed.

### 10. Project Audit

`project-audit` is periodic lifecycle health, not documentation lint.

It answers:

- Is the project registered?
- Does project identity match repo/GitHub/local config?
- Are issues, milestone, roadmap, and docs in sync?
- Are there stale branches, stale plans, or unclosed loops?
- Is session continuity bounded?
- Are docs navigable according to `docs-lint`?

`project-audit` may call `docs-lint doctor --json`, but it should not duplicate
docs-specific logic.

v1 invocation policy:

- explicit invocation only;
- hooks may suggest running `project-audit`, but must not run it automatically;
- scheduled audit is v2, after project registry and POS ingestion stabilize.

## Deprecated Surface

### `docs-index`

`docs-index` is no longer a user-facing lifecycle skill.

Allowed status:

- internal module/script used by `docs-lint fix-index`, or
- compatibility wrapper that prints a deprecation notice and calls
  `docs-lint fix-index`.

### `gh-memory`

`gh-memory` is deprecated as agent memory.

Allowed status:

- compatibility shim for old workflows;
- thin wrapper over GitHub issue creation if still useful.

It must not be promoted as the primary session continuity or project memory
surface. Session continuity belongs to `session-start` / `handoff`; long-term
accepted state later belongs to POS.

## Runtime Adapter Contract

Lifecycle OS logic must live in deterministic scripts and structured reports.
Runtime surfaces are adapters.

| Runtime | Adapter surface | Contract |
|---------|-----------------|----------|
| Claude Code | `SKILL.md`, hooks, commands | primary current implementation |
| Codex | `AGENTS.md`, local skills, shell commands | must read same specs/reports |
| Cursor | repo rules / command docs | should use same scripts |
| Gemini CLI | `GEMINI.md` or equivalent | future adapter |

Adapter requirements:

- do not duplicate lifecycle rules in runtime-specific prose where a shared
  spec/report exists;
- point to the same deterministic script entrypoints;
- preserve safety boundaries;
- prefer `AGENTS.md` / repo docs for cross-runtime project instructions;
- keep `SKILL.md` as a Claude adapter, not the canonical source of truth.

## Hook Contract

Hooks are thin wrappers around deterministic scripts. They should not contain
business logic.

Recommended v1 hooks:

| Hook | Action | Policy |
|------|--------|--------|
| Session start | call gather/session-start | bounded context only |
| PostToolUse git commit | docs-lint quick check on changed docs | non-blocking, timeout |
| PR/pre-merge | pre-merge-check | report/gate |
| Stop/session end | suggest handoff or milestone closure | non-blocking |
| Milestone close | milestone-closure | explicit user action |

Hook output must be short. Long reports should be written to files and linked.

### Hook Timeout and Cache

Hook-invoked `docs-lint` runs must not block the user session.

Timeout:

- Default: 8 seconds.
- Override: `H2T_LINT_HOOK_TIMEOUT` environment variable (integer seconds).
- On timeout: write `status: "error", message: "hook timeout"` to the report
  and exit 0 to keep the hook non-blocking.

Cache:

- Cache file: `.h2t-lint-cache.json` at repo root.
- Cache key per file: mtime of the `.md` file + current git HEAD hash.
- Invalidate when any tracked `.md` mtime or git HEAD changes.
- Cache applies only to hook invocations; direct CLI runs always recompute.

## Data Ownership

| Data | v1 owner | Notes |
|------|----------|-------|
| GitHub issues/PRs/milestones | GitHub | authoritative project-management state |
| Roadmap markdown | repo docs | curated mirror and strategy surface |
| Plans/specs | repo docs | executable design history |
| Docs index/navigation | generated by `docs-lint` | rebuildable, not source of truth |
| Session latest state | h2t-core local state | bounded runtime continuity |
| Handoff markdown | archive mirror | human-readable, not runtime source |
| POS session/research graph | POS future | downstream consumer in v1 |

## Safety Boundaries

Safe without extra confirmation:

- read-only audit;
- machine-readable report generation;
- creating missing empty directories;
- adding missing generated index sections when explicitly in `fix-index`;
- formatting metadata when reversible.

Requires explicit user confirmation:

- rename files;
- move files;
- archive files;
- delete files;
- rewrite large README/navigation surfaces outside generated regions;
- close issues/milestones;
- push, merge, or tag;
- send messages or perform destructive connector actions.

Recovery rules:

- no command should require a hidden transaction log to recover;
- commands recompute current state from disk/GitHub before applying;
- operation reports are evidence, not the only source of recovery truth;
- incomplete generated files should be detected as findings on the next audit;
- destructive operations should be last in any multi-step command.

### Concurrency Policy

Multiple commands or hooks may run concurrently against the same repo.

v1 policy:

- All writes use atomic tmp-file + `os.rename()` pattern.
- Last-writer-wins is acceptable for report and cache files in v1.
- No distributed lock is required for local-only commands.
- If `os.rename()` fails, the command reports an error and exits without
  partial writes.

## Acceptance Tests

Lifecycle OS is not accepted by unit tests alone.

Minimum dogfood matrix:

| Repo | Purpose |
|------|---------|
| `C:/dev/h2t-skills` | native h2t repo with many specs/plans |
| `C:/work/rejuve` | repo outside `C:/dev`, client docs, real navigation issues |
| temporary minimal repo | scaffold/init baseline |

Required evidence:

- `docs-lint doctor --json` output for each repo;
- human-readable `docs-lint plan` for Rejuve;
- `docs-lint fix-index` dry run and approved apply on at least one repo;
- `handoff` report showing real open GitHub issues in "what remains";
- `milestone-closure` dry run using `gh api` milestones;
- `pre-merge-check` warning on docs health without unsafe auto-fixes.

## Issue Mapping

| Issue | Contract slice | Status |
|-------|----------------|--------|
| #240 | `docs-lint` unified docs health, navigation, index, plan, JSON doctor | done: PR #241, merge `51a0563` |
| #211 | `handoff` reads real GitHub open P0/P1/blocker issues | done: PR #239, merge `22bea49` |
| #196 | `scaffold-project`, project init, milestone closure integration | open |
| #197 | lifecycle hooks and `gh-memory` deprecation | implemented by PR for this plan |

Current execution order after #240/#211:

1. Implement #196 using `docs-lint` as the docs/index surface.
2. Implement #197 after #196 defines stable lifecycle hook entrypoints.
3. Revisit `project-audit` / lifecycle-native planning after #196/#197.

## Non-Goals

- POS as canonical lifecycle registry in v1.
- Replacing GitHub as PM backend in v1.
- Making every superpower lifecycle-native immediately.
- Auto-fixing destructive documentation moves.
- Building a new UI.

## Open Questions

1. Should `plan-work` become a first-class h2t lifecycle skill, or remain
   implemented through superpowers plans for now?
2. What is the canonical local project registry path for non-code projects and
   repos outside `C:/dev`?
3. Which runtime adapter should be implemented first after Claude: Codex
   `AGENTS.md`, Cursor rules, or Gemini?

## GSTACK REVIEW REPORT

Reviewed by: plan-eng-review (gstack v1.48.0.0)
Date: 2026-05-28
Reviewer commit: ed25e87

### Summary

This spec passed architectural review with 11 decisions resolved (D1-D11).
#240 and #211 have since shipped; the contract now primarily drives #196 and
#197.

### Decisions Applied

| ID | Decision | Applied |
|----|----------|---------|
| D1 | BFS orphan detection from docs/README.md | spec §Phase 6 |
| D2 | Marker-based fix-index (preserve manual content) | spec §Phase 6 |
| D3 | Map + deprecate legacy --fix flags (stderr warning) | T2 applied |
| D4 | Configurable hook timeout (H2T_LINT_HOOK_TIMEOUT, 8s default) + mtime+HEAD cache | T3 applied |
| D5 | Use spec as design doc, not impl plan | no spec change needed |
| D6 | Python package: plugins/h2t-dev/lib/docs/ | noted for #240 impl plan |
| D7 | TDD: unit tests + dogfood acceptance (h2t-skills + rejuve) | noted for #240 impl plan |
| D8 | Cache invalidation: mtime+HEAD hash | T3 applied |
| D9 | fix-index bootstrap: dry-run first, append with markers on --apply | T4 applied |
| D10 | Concurrency: atomic tmp+os.rename, last-writer-wins v1 | T5 applied |
| D11 | Config discovery: .claude/rules/docs-lint.yaml, fallback to defaults | T6 applied |

Additional: T7 status enum — standardized `skipped_not_applicable` (was `not_applicable`).
T1 (findings[] item schema) applied in previous commit ac7aa17.

### Verdict

**PARTIALLY IMPLEMENTED** — #240 and #211 are complete. The remaining Lifecycle
OS work is #196 followed by #197.

Historical implementation tasks were written to:
`~/.gstack/projects/lichtpfad-h2t-skills/tasks-eng-review-*.jsonl`

Current execution order: #196 → #197
