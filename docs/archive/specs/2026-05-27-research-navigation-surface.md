---
title: Research Navigation Surface
date: 2026-05-27
status: done
issue: 192
---

# Research Navigation Surface

## Goal

Add a local read/navigation surface over the Phase 1 research artifact contract.

Phase 1 writes canonical JSON objects and rebuildable indexes:

- `ResearchDocument`
- `ResearchThread`
- `ResearchRun`
- `ResearchSynthesis`
- `documents.index.json`
- `threads.index.json`
- `syntheses.index.json`
- `aliases.index.json`

Phase 2 must make that substrate usable by agents and operators without requiring manual filesystem inspection.

## Non-goals

This phase does not implement:

- retention cleanup
- index rebuild/doctor tooling
- Exa/provider key routing
- POS ingestion
- `ProjectResearchLink`
- `links.index.json`
- synthesis review/acceptance workflow
- markdown parsing for routing

## Principles

- Canonical object JSON is truth.
- Indexes are navigation caches.
- If an index row and an object disagree, object wins.
- Markdown mirrors are human review surfaces only.
- Navigation commands must never infer state by parsing Markdown.
- Missing object/index drift must be explicit, not silently ignored.

## Storage Roots

Navigation reads the same local research root used by Phase 1 writes:

- default: `~/.h2t/research`
- test/custom root: existing `ResearchClient(output_dir=...)` behavior where applicable

All navigation commands must support `--output-dir` in v1.

Rationale:

- existing artifact-producing commands already expose `--output-dir`
- tests and smoke evidence may use non-default roots
- agents must be able to inspect the same root they just wrote to

If `--output-dir` is omitted, commands use the default root.

## CLI Contract

### `research index documents`

List `documents.index.json`.

Human output should include:

- `document_id`
- `title`
- `canonical_url`
- `provider`
- `status`
- `review_status`
- `project_ids`
- `updated_at`

JSON output returns:

```json
{
  "kind": "research_index",
  "index": "documents",
  "root": "...",
  "count": 1,
  "items": []
}
```

### `research index threads`

List `threads.index.json`.

Human output should include:

- `thread_id`
- `question`
- `status`
- `owner_context`
- `topics`
- `latest_synthesis_id`
- `updated_at`

JSON output follows the same `research_index` envelope with `index="threads"`.

### `research index syntheses`

List `syntheses.index.json`.

Human output should include:

- `synthesis_id`
- `thread_id`
- `status`
- `review_status`
- `confidence_summary`
- `has_open_questions`
- `project_ids`
- `updated_at`

JSON output follows the same `research_index` envelope with `index="syntheses"`.

### `research show document <document_id>`

Load canonical object JSON from:

`objects/documents/<document_id>.json`

JSON output returns:

```json
{
  "kind": "research_object",
  "object_type": "document",
  "object_id": "research-doc:...",
  "root": "...",
  "object": {}
}
```

Human output should be compact and operator-readable:

- id
- title
- canonical/source URL
- provider
- status/review status
- project/thread/entity ids
- artifact refs

### `research show thread <thread_id>`

Load canonical object JSON from:

`objects/threads/<thread_id>.json`

Human output should include:

- id
- question
- status
- owner context
- topics
- latest synthesis id

JSON output follows the `research_object` envelope with `object_type="thread"`.

### `research show run <run_id>`

Load canonical object JSON from:

`objects/runs/<run_id>.json`

Human output should include:

- id
- thread id
- query
- provider set
- status
- document ids
- result counts

JSON output follows the `research_object` envelope with `object_type="run"`.

### `research show synthesis <synthesis_id>`

Load canonical object JSON from:

`objects/syntheses/<synthesis_id>.json`

Human output should include:

- id
- thread id
- run ids
- status/review status
- summary
- open question count
- proposed edge count

JSON output follows the `research_object` envelope with `object_type="synthesis"`.

### `research resolve`

Resolve lookup aliases through `aliases.index.json`.

Minimum v1 surface:

```powershell
h2t-ops research resolve --url <url> [--json]
h2t-ops research resolve --alias <value> [--alias-type url] [--json]
```

Resolution returns matching alias rows plus, when possible, the canonical object path.

JSON output:

```json
{
  "kind": "research_resolution",
  "root": "...",
  "query": {
    "alias_type": "url",
    "alias_value": "https://example.com"
  },
  "count": 1,
  "matches": [
    {
      "alias_type": "url",
      "alias_value": "https://example.com",
      "target_object_type": "document",
      "target_id": "research-doc:...",
      "object_path": "...",
      "object_exists": true
    }
  ]
}
```

Human output should make unresolved and stale aliases visible.

## Error Behavior

### Missing Index

`research index <name>` with no index file should return an empty list, not an error.

Rationale: a fresh installation may have no research artifacts yet.

### Unknown Index

Unknown index names are usage errors.

### Missing Object

`research show <type> <id>` where the object file does not exist is a data error.

The error should include:

- object type
- object id
- expected path

### Stale Alias

`research resolve` should not fail if an alias target object is missing.

Instead, it returns:

- `object_exists=false`
- `object_path=<expected path>`

Rationale: resolve is also a diagnostic entry point. Full drift classification belongs to the later doctor/rebuild issue.

### Schema Mismatch

If an object file exists but its `schema` does not match the requested object type, return a data error.

Examples:

- `show document research-thread:...` must fail
- `show thread research-doc:...` must fail

Expected schemas:

| Object type | Object directory | Expected schema |
| --- | --- | --- |
| `document` | `objects/documents/` | `research_document/v0.1` |
| `thread` | `objects/threads/` | `research_thread/v0.1` |
| `run` | `objects/runs/` | `research_run/v0.1` |
| `synthesis` | `objects/syntheses/` | `research_synthesis/v0.1` |

## Filtering

Phase 2 should keep filtering minimal.

Allowed v1 filters:

- `research index documents --project <project_id-or-name>`
- `research index threads --project <project_id-or-name>`
- `research index syntheses --project <project_id-or-name>`

Project filter normalization:

- input `demo` matches `project:demo`
- input `project:demo` matches `project:demo`

Project filter behavior:

- documents: match against `project_ids`
- syntheses: match against `project_ids`
- threads: match against `owner_context.context_id`

Rationale: `threads.index.json` does not currently carry `project_ids`; thread project ownership is represented by `owner_context`.

Other filters are deferred:

- provider
- status
- review status
- topic
- date ranges
- confidence

## JSON vs Human Output

Every navigation command must support `--json`.

Rules:

- JSON output is stable and machine-readable.
- Human output can be compact and lossy.
- Human output must include enough ids to continue with `show` commands.
- Human output should not dump large summaries by default.
- Human `show synthesis` prints a truncated summary preview, not the full summary.

Suggested preview limit:

- 500 characters for human output
- full object only with `--json`

## Skill Documentation

`plugins/h2t-ops/skills/research/SKILL.md` should document the agent lookup order:

1. query shared index
2. resolve object ids
3. read canonical object JSON
4. open Markdown mirror only for human review

It should also document the new commands and repeat the rule:

If index and object disagree, object wins.

## Acceptance

Phase 2 is complete when:

- `research index documents --json` lists `documents.index.json`
- `research index threads --json` lists `threads.index.json`
- `research index syntheses --json` lists `syntheses.index.json`
- `research show document <id> --json` loads canonical document JSON
- `research show thread <id> --json` loads canonical thread JSON
- `research show run <id> --json` loads canonical run JSON
- `research show synthesis <id> --json` loads canonical synthesis JSON
- `research resolve --url <url> --json` resolves URL aliases
- missing indexes return empty list
- missing objects produce explicit data errors
- stale aliases are surfaced without failing resolve
- tests cover happy paths and error behavior
- skill docs are updated
- live smoke uses artifacts created by Phase 1 commands

## Deferred

- `research doctor`
- `research rebuild-indexes`
- `research cleanup`
- `links.index.json`
- `ProjectResearchLink`
- POS intake packets
- provider key routing
- synthesis review/acceptance commands
