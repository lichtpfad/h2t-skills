# Session Continuity POS Alignment Note

## Purpose

This note captures the current alignment between local `h2t-core` session continuity and future POS session modeling.

It is intentionally narrower than a full POS design. The goal is to freeze:

- minimal structured event/schema expectations;
- authority boundaries;
- sync model;
- migration path.

## Current Local Model

Today `h2t-core` already has four distinct outputs, even if they are not fully normalized yet:

1. `session-start` / `handoff` interaction flow
2. local bounded continuity file: `latest.json`
3. activity events:
   - `session.start`
   - `session.end`
4. markdown mirror/archive

The redesign keeps this split and makes it explicit.

## Local -> POS Field Mapping

Minimum v1 semantic mapping:

| Local `latest.json` | POS event/session payload |
|---|---|
| `session_id` | `session.session_id` |
| `domain` | `session.domain` |
| `project` | `session.project` |
| `summary_short` | `summary.text` |
| `next_actions` | `summary.open_threads` or equivalent bounded carry-forward field |
| `artifacts` | `summary.artifacts` |
| `truncated` | summary metadata / degraded detail, not raw prose reconstruction |

This mapping is semantic, not byte-for-byte.

## Minimum POS Session Event Schema

POS should consume structured session events, not markdown prose.

Reference envelope:

```json
{
  "schema": "pos_session_event/v0.1",
  "event_id": "session-event:sha256:...",
  "event_type": "session.start|session.end|session.summary_confirmed",
  "occurred_at": "2026-05-26T12:00:00Z",
  "producer": "h2t-core/session-start|h2t-core/handoff",
  "machine_id": "automata",
  "session": {
    "session_id": "session:sha256:...",
    "started_at": "2026-05-26T10:00:00Z",
    "ended_at": "2026-05-26T12:00:00Z",
    "context_type": "repo|project|personal|strategy|research|creative|ops|unknown",
    "context_id": "repo:POS|project:ai-native|selfwork|...",
    "domain": "business|personal|education|research|creative|infra|null",
    "project": "pos|h2t-skills|ai-native|null",
    "repo": "C:/dev/POS|null",
    "branch": "main|null"
  },
  "summary": {
    "status": "confirmed|draft",
    "text": "bounded summary after user confirmation",
    "decisions": [],
    "open_threads": [],
    "artifacts": []
  },
  "refs": {
    "latest_json": "...",
    "markdown_mirror": "...",
    "source_transcript": null
  }
}
```

Minimum required fields for v1:

- `event_id`
- `event_type`
- `occurred_at`
- `producer`
- `session.session_id`
- `session.context_type`
- `summary.status`
- `refs.latest_json`

## Identity Model

Repo-centric identity is insufficient.

Recommended session identity basis:

- `producer`
- `started_at`
- `machine_id`
- `context_type`
- `context_id`

Recommended `context_type` vocabulary:

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

Example `context_id` values:

- `repo:POS`
- `repo:h2t-skills`
- `project:ai-native`
- `person:self`
- `domain:research`
- `workflow:daily-brief`

Notes:

- `domain` and `project` are routing fields and may be nullable;
- `repo` and `branch` are useful implementation context, but not the universal identity root.

## Authority Boundary

V1 authority must remain simple:

- `latest.json` is authoritative for local Claude runtime continuity;
- POS is a downstream structured consumer;
- markdown is archive/mirror only.

That means:

- Claude runtime does not depend on POS availability;
- local continuity continues to work offline;
- POS does not become canonical in this phase.

## Recommended V1 Sync Contract

Use:

- append-only event stream;
- idempotent session-summary upsert.

Not:

- fire-and-forget events only;
- summary-upsert only with no event log.

Recommended behavior:

1. `h2t-core` writes local `latest.json`
2. `h2t-core` emits append-only events:
   - `session.start`
   - `session.end`
   - `session.summary_confirmed`
3. POS consumes events idempotently:
   - append event if `event_id` unseen
   - upsert current summary by `session_id`

This yields:

- event log = timeline / audit surface
- summary view = current query surface
- markdown = mirror only

`session.summary_confirmed` is emitted only after the user confirms the handoff summary.

## Dual-Write Validation Semantics

During v1.5 dual-write validation, parity does not require byte-for-byte equality between local continuity and POS summary payloads.

Validation should check semantic agreement on:

- same `session_id`
- same continuity subject (`context_type`, `context_id`, `project`, `domain` where present)
- same bounded summary meaning:
  - local `summary_short`
  - POS `summary.text`
- same normalized `next_actions` set
- same normalized artifact references set

Textual formatting differences are acceptable as long as the bounded summary semantics are equivalent.

## Migration Path

### v1 — h2t-core authoritative

- `latest.json` authoritative
- markdown mirror
- POS downstream consumer

This keeps Claude runtime stable and independent.

### v1.5 — dual-write with validation

- `h2t-core` writes `latest.json`
- `h2t-core` emits POS events
- POS builds session registry
- doctor/diagnostic compares `latest.json` against POS current summary semantically, not by exact text equality

### v2 — POS authoritative for history

- Claude runtime may still read local `latest.json` for fast bounded injection
- POS owns historical session registry
- local `latest.json` becomes cache of latest POS-confirmed state

### v3 — POS-assisted runtime context

- gather/session-start may query POS for bounded context
- injection remains local and bounded
- POS provides richer cross-session memory without replacing hook-driven runtime flow

## Design Constraint

`gather.py` and the current Claude hook/injection model remain in place.

POS alignment must not break:

- folder-based context detection;
- deterministic runtime gathering outside the agent;
- `BRIEFING + GATHER_META` injection that is already empirically validated with Claude Code.

## Implementation Status

- Phase 1 local continuity landed.
- Repo-session lookup is the only guaranteed continuity lookup in v1.
- Markdown is still written by default but is no longer treated as canonical runtime memory.
- POS sync remains deferred to a later implementation wave.
