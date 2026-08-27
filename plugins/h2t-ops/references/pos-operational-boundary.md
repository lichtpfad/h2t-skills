# POS Operational Boundary for Skills

Canonical decision: `docs/adr/0006-pos-operational-journal-and-connector-boundary.md`
in the private POS repository.

This is a skill-facing operational reference, not the canonical architecture
decision. The POS repo decides architecture. The h2t-skills repo teaches agents
how not to violate it.

## Ownership

| Layer | Owns | Does not own |
|---|---|---|
| `h2t-ops` | Connector runtime: auth, stateless clients, envelopes, errors | POS journal, sync state, interpretation, privacy/routing, daily loop |
| POS | Operational journal, sync state, interpretation, privacy/routing, daily loop | Connector implementation |
| vault/lake | Raw evidence and long-term knowledge archive | Operational state transitions |
| skills/agents | Workflow orchestration and user-facing procedure | Direct database or lake mutations |

## Rules for Skills

- Skills do not own connector logic.
- `h2t-ops` owns Gmail, Notion, Calendar, Drive, MeetGeek, Telegram, research,
  and future external connector runtime.
- POS owns the operational journal, sync state, interpretation, privacy/routing,
  and daily loop.
- Skills may call `h2t-ops` CLI for external reads.
- Skills may call POS CLI/API for capture, decision, task, lesson, follow-up,
  and daily-loop writes once those commands exist.
- Skills must not write directly to `~/.dor/pos.db`.
- Skills must not use the existing `dor.db` for POS journal data.
- Skills must not modify vault/lake directly except through an approved
  `pos_ingest` or coordinator workflow.
- Skills must preserve `source_refs` and `artifact_refs` when turning external
  data into captures.
- Agent discoveries that imply decisions, tasks, lessons, or follow-ups should
  be routed through POS journal commands once available.
- Until POS journal commands exist, skills should emit structured proposed
  captures, not mutate stores.

## Structured Proposed Capture

When POS journal commands are unavailable, output a machine-readable block:

```json
{
  "type": "proposed_capture",
  "kind": "decision|task|lesson|follow_up|note",
  "summary": "",
  "body": "",
  "source_refs": [],
  "artifact_refs": [],
  "connector": "gmail|notion|calendar|drive|meetgeek|telegram|research|manual",
  "privacy_label": "public|work|client|private|sensitive",
  "requires_human_review": true
}
```

## Allowed

- Read external data through `h2t-ops`.
- Summarize external data for the user.
- Propose captures, decisions, tasks, lessons, or follow-ups as structured
  output.
- Call POS journal commands when they exist.
- Preserve links to raw evidence, source IDs, issues, notes, and artifacts.

## Forbidden

- Create provider-specific connector API code inside skills.
- Write SQLite rows directly.
- Treat raw Gmail, Notion, MeetGeek, Telegram, Drive, or Calendar events as POS
  memory without interpretation.
- Save raw provider payloads as canonical KB truth in `dor.db`.
- Mutate vault/lake outside approved ingestion or coordinator workflows.

## Out of Scope

- Deciding POS storage architecture.
- Changing `h2t-ops` connector internals.
- Implementing POS CLI/API.
- Copying the full ADR into skills.
