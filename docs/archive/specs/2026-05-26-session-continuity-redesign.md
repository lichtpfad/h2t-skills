# Session Continuity Redesign

## Context

`h2t-core:session-start` and `h2t-core:handoff` materially improved planning quality, but the current continuity model is too expensive and too mixed:

- `session-start` still exposes archival session file lists in gather output;
- archival markdown, bounded machine state, and activity/POS events are not cleanly separated;
- runtime continuity still carries legacy assumptions from the earlier markdown-first model.

At the same time, two constraints are non-negotiable:

1. `gather.py` exists for a reason:
   - it auto-detects context from `cwd`;
   - it externalizes context collection out of the agent and into deterministic runtime code.
2. The current Claude-compatible injection model is proven:
   - `PreToolUse` / `SessionStart` hooks;
   - injected `BRIEFING + GATHER_META`;
   - bounded skill instructions consuming injected context instead of re-scraping manually.

This redesign must preserve those strengths.

Live `handoff` behavior also confirms an important nuance:

- the useful part is not "markdown handoff" itself;
- the useful part is the interaction pattern:
  - agent reconstructs a bounded summary;
  - user confirms/corrects it;
  - only then does runtime persist the state.

That interaction pattern must be preserved even if the storage model changes.

## Problem

The current system overloads one concept of "handoff" with three different jobs:

1. runtime continuity for the next session;
2. human-readable archival notes;
3. operational event registration / future POS integration.

That leads to three concrete problems:

- too much context at session start;
- unclear source of truth for "what carries forward";
- weak seam between local skills and future POS session modeling.

There is also a quality problem in live `handoff` synthesis under larger context:

- repeated items can appear in `what_done`;
- artifact selection can drift or duplicate;
- persistence still happens through plugin-cache runtime, so repo fixes alone do not guarantee live behavior until plugin runtime is synced.

## Goals

1. Preserve the current gather/injection pipeline.
2. Keep the planning-quality uplift from `session-start` / `handoff`.
3. Reduce session-start context cost.
4. Make runtime continuity machine-readable first.
5. Prepare a clean sync seam with POS.
6. Support both repo and non-code sessions.
7. Preserve the current confirmation-gated `handoff` interaction pattern.

## Non-Goals

- replacing Claude hook injection with a different runtime model;
- deleting markdown handoff entirely in v1;
- redesigning POS itself in this task;
- changing project/domain autodetection away from gather.

## Design

### 1. Preserve gather as the runtime discovery layer

`gather.py` / gather CLI remains responsible for:

- detecting project context from `cwd`;
- gathering repo/runtime state outside the agent;
- formatting injected briefing for Claude-compatible hooks.

This layer remains the entry point for:

- `session-start`
- `handoff`
- `init-project`

The redesign does **not** move context collection back into ad hoc agent reasoning.

### 2. Introduce a first-class session continuity state

Runtime continuation should depend on a bounded machine-readable state object, not on scanning archival markdown.

Canonical v1 file:

- continue using bounded `latest.json` as the canonical v1 form

`session_state.json` is not introduced in v1. If naming changes later, it must be an explicit migration, not an informal alias.

Required fields:

```json
{
  "version": 1,
  "session_id": "dev-h2t-skills-issue-185-2026-05-26",
  "domain": "dev",
  "project": "h2t-skills",
  "context_type": "repo",
  "context_id": "lichtpfad/h2t-skills",
  "updated_at": "2026-05-26T10:20:00Z",
  "summary_short": "Merged PR #188; installed gather and activity-log entrypoints",
  "next_actions": [
    "Redesign session continuity memory model",
    "Sync session events with POS"
  ],
  "artifacts": [
    {"type": "commit", "ref": "3b8d047"},
    {"type": "issue", "ref": "186"}
  ],
  "blockers": [],
  "truncated": false
}
```

This is the object that the next session should consume by default.

V1 schema note:

- the canonical local continuity file continues the current `latest.json` contract;
- `summary_short` remains a bounded string in v1;
- richer structured `done[]` may exist later in POS-facing event payloads, but is not required in local `latest.json` yet.

### 2a. Define continuity lookup rules explicitly

V1 continuity lookup must be deterministic.

#### Repo sessions

For repo/code sessions:

- `context_type = "repo"`
- `context_id = <owner/repo>` when GitHub remote is known
- fallback `context_id = <project>`

Lookup key in v1 remains compatible with the current storage layout:

- machine-scoped directory
- project/repo-scoped `latest.json`

This preserves momentum with the current writer/reader contract.

#### Non-code sessions

For non-code sessions, gather must not guess from repo name.

V1 rule:

- `context_type` and `context_id` must come from explicit session context resolution
- if they cannot be resolved deterministically, runtime continuity lookup is skipped
- session-start still works, but without prior continuity carry-forward

That is stricter than a fuzzy fallback and avoids writing continuity state under unstable keys.

Examples:

- strategy session:
  - `context_type = "strategy"`
  - `context_id = "ai-business-model-2026"`
- meeting prep:
  - `context_type = "meeting"`
  - `context_id = "rejuve-kristina-2026-05-26"`
- personal session:
  - `context_type = "personal"`
  - `context_id = "weekly-review"`

Non-code continuity support is therefore part of the model in v1, but not automatic unless context identity is explicitly known.

Recommended `context_type` vocabulary for POS alignment:

- `repo`
- `project`
- `personal`
- `selfwork`
- `strategy`
- `research`
- `creative`
- `ops`
- `admin`
- `unknown`

V1 implementation boundary:

- non-code sessions are modeled in the design now;
- but persistence/lookup stays repo-layout-compatible in v1 unless an explicit generalized storage path is implemented;
- therefore, non-code continuity lookup may legitimately be absent in the first implementation wave even when the identity model is already adopted.
- v1 implementation only guarantees continuity lookup for repo sessions.

### 3. Demote markdown handoff to archive/mirror status

Markdown handoff remains useful as:

- optional human-readable mirror;
- audit/debug artifact;
- export surface for manual review.

It should no longer be the primary runtime continuity source.

Default `session-start` behavior should not scan archival handoff markdown files unless explicitly requested.

V1 default write behavior:

- handoff still writes markdown by default
- handoff also writes canonical bounded `latest.json`
- runtime ignores markdown for continuity unless explicitly requested

This keeps existing audit/export value while removing markdown from the default machine-memory path.

Failure policy in v1:

- `latest.json` is the primary continuity artifact;
- markdown is a secondary mirror;
- if bounded state is safely written but markdown mirror fails, handoff may complete in degraded-success mode;
- degraded mirror failure must be surfaced explicitly, not silently swallowed.

Minimum degraded signal contract:

- machine-readable writer result includes `status: "degraded"` when mirror write fails but bounded state succeeds;
- result includes `mirror_write_failed: true`;
- successful bounded continuity path is still explicit via the persisted `latest.json` ref/path.

### 3a. Preserve handoff as an interaction pattern

The redesign is not allowed to remove the current high-value handoff flow:

1. auto-reconstruct:
   - what was done
   - what remains
   - artifacts
2. show a bounded summary to the user;
3. require confirmation/correction;
4. persist only after confirmation.

This interaction pattern is a core reason planning quality improved and must remain first-class.

What changes is the persistence target:

- primary persistence becomes bounded machine-readable state;
- markdown becomes mirror/archive;
- event emission becomes a separate POS-facing layer.

`session.summary_confirmed` is emitted only after the user confirmation gate passes.

Draft/generated-but-not-confirmed handoff content is not emitted as confirmed session continuity state.

### 4. Separate three layers explicitly

#### Layer A — Context Discovery

Owned by gather:

- `cwd`-based project detection;
- git/github/runtime state;
- user/config context;
- optional bounded continuity lookup.

#### Layer B — Session Continuity

Owned by machine-readable bounded session state:

- what was done;
- what comes next;
- artifacts;
- blockers.

This is the default carry-forward object.

#### Layer C — Activity / POS Event Stream

Owned by activity events:

- `session.start`
- `session.end`
- `session.summary_confirmed`

This is for registration, analytics, and POS sync, not for markdown-like narrative continuity.

### 5. Support non-code sessions explicitly

The continuity model must support more than repo-bound sessions.

Required identity model:

- `domain`
- `project`
- `context_type`
- `context_id`

Repo name may remain the dominant key for code sessions, but it cannot be the universal key for all sessions.

## Expected Runtime Behavior

### session-start

Default path:

1. gather runtime context from `cwd`;
2. read bounded latest continuity state for matching context;
3. inject/display bounded briefing;
4. do **not** enumerate archival markdown files unless explicitly requested.

### handoff

Default path:

1. produce structured summary:
   - done
   - next
   - artifacts
   - blockers
2. write bounded machine-readable continuity state;
3. optionally write markdown mirror;
4. emit activity/POS-facing events.

Quality requirements for the generated summary:

- no duplicate bullets in `done`;
- no duplicate carry-forward items in `next`;
- artifacts should be bounded and de-duplicated;
- summary must stay compact enough to remain useful as next-session machine context.

## POS Alignment

This redesign intentionally creates a clean seam for future POS sync.

The expected mapping is:

- `session.start` -> POS session opened
- `session.end` -> POS session closed
- bounded continuity state -> structured session summary payload
- `session.summary_confirmed` -> POS current-summary upsert trigger

POS should not need to parse markdown handoff prose as its primary input.

Authority boundary in v1:

- local bounded `latest.json` remains the authoritative continuity object for session-start/handoff
- POS is downstream and receives structured events/payloads
- POS does not become the continuity source of truth in this task

Recommended v1 sync model:

- local `latest.json` write remains authoritative for Claude runtime continuity;
- h2t-core emits append-only structured session events;
- POS consumes those events idempotently;
- POS maintains a current session-summary view keyed by `session_id`.

This means v1 should prefer:

- append-only event log for audit/timeline;
- idempotent summary upsert for current query surface;
- no markdown parsing in POS.

Future possibility:

- a later migration may promote POS session state to the authoritative registry
- that requires an explicit sync and fallback design and is out of scope here

## Migration Direction

### Phase 1

- keep current hook injection model;
- make bounded latest state the runtime default;
- stop relying on archival markdown scan in normal `session-start`.
- preserve the current confirmation-gated handoff UX.

### Phase 2

- align local continuity state with POS session schema;
- keep markdown as optional mirror/export.
- make plugin-runtime sync part of rollout validation, since live behavior depends on installed cache/runtime, not only repo state.

## Acceptance

This design is ready to implement when the following are agreed:

1. `gather.py` and current hook injection remain in place.
2. Runtime continuity becomes machine-readable first.
3. Markdown handoff is archive/mirror, not default runtime memory.
4. Session identity supports both repo and non-code sessions.
5. POS sync uses structured events/state, not markdown parsing.
6. The existing `handoff` confirmation workflow is preserved.
7. Live rollout accounts for plugin-cache/runtime sync, not only repo-local code state.

## Implementation Status

- Phase 1 local continuity landed.
- Repo-session lookup is the only guaranteed continuity lookup in v1.
- Markdown is still written by default but is no longer treated as canonical runtime memory.
- POS sync remains deferred to a later implementation wave.
