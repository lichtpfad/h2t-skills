# Granola Connector Reference

## Intent Map

| Intent | Command |
| --- | --- |
| auth check | `h2t-ops granola auth-check --json` |
| list notes | `h2t-ops granola list --limit 20 --format md` |
| list notes by date range | `h2t-ops granola list --since 2026-08-01 --until 2026-08-19 --json` |
| list notes edited since a date | `h2t-ops granola list --updated-after 2026-08-01 --json` |
| list notes in a folder | `h2t-ops granola list --folder "opencall-guru" --json` |
| list folders | `h2t-ops granola folders --format md` |
| get note with summary | `h2t-ops granola get NOTE_ID_FROM_LIST --format md` |
| summary only, provider markdown | `h2t-ops granola summary NOTE_ID_FROM_LIST --format md` |
| verbatim transcript | `h2t-ops granola transcript NOTE_ID_FROM_LIST --format md` |
| transcript without speaker merging | `h2t-ops granola transcript NOTE_ID_FROM_LIST --format md --raw` |
| pull notes to disk | `h2t-ops granola sync --to ~/.dor/lake/granola --since-cursor` |
| list webhook endpoints | `h2t-ops granola webhooks --json` |

`--folder` accepts a folder name or a `fol_...` ID. An ambiguous name fails with the
candidate IDs rather than guessing.

## Safety

- Every command in this connector is a provider read; there are no provider writes.
- `sync` writes to the local filesystem and needs an explicit `--to` destination and user intent.
- Webhook endpoints are **read-only** here. Creating one returns a signing secret that Granola
  shows exactly once; registering endpoints stays a deliberate manual action outside this connector.
- Never put note summaries, transcript bodies, or attendee lists into GitHub issues.
- Transcripts are personal meeting content: keep synced lake directories out of shared repos.

## Commands

```bash
h2t-ops granola auth-check --json
h2t-ops granola list --limit 20 --format md
h2t-ops granola get NOTE_ID_FROM_LIST --format md
h2t-ops granola transcript NOTE_ID_FROM_LIST --format md
h2t-ops granola sync --to ~/.dor/lake/granola --include summaries,transcripts --since-cursor
```

## Auth

Granola expects `GRANOLA_API_KEY` (a `grn_...` key from Granola Settings -> API) from
environment, `H2T_SECRETS_FILE`, `~/.dor/secrets/secrets.env`, or legacy `~/.dor/secrets.env`.

In Claude Code, check readiness through:

```text
/h2t-core:setup connectors-check
```

## Sync Model

- Files land as pairs: `<dir>/summaries/<note_id>.{md,json}` and `<dir>/transcripts/<note_id>.{md,json}`.
  The `.json` half is the raw provider payload, so markdown can always be regenerated offline.
- The cursor tracks `updated_at`, not `created_at`. Granola keeps editing a note after creation
  (the `note.edited` event always reports `changed_fields: ["summary"]`), so a created-at cursor
  would freeze the first version forever. A re-synced note overwrites its markdown and appends a
  new `manifest.jsonl` row, so the manifest carries version history while the files stay current.
- Default cursor file: `~/.dor/lake/_cursors/granola.json`. Override with `--cursor-file`.
- Granola auto-deletes transcripts under its retention policy — a regular `sync` is the only way
  to keep verbatim text beyond that window.

## Transcript Rendering

- Consecutive fragments from one speaker merge into a single block: `**Name** [HH:MM:SS] — text`.
  `--raw` keeps provider fragments one per line.
- Speaker labels resolve as name -> diarization label -> `Me`/`Them` (from `attribution`).
  Calls recorded before Granola's Google Meet extension often carry no names at all, so the
  frontmatter reports `speakers:` and `unnamed_fragments:` — check those before trusting attribution.
- A fragment that exactly repeats the previous one (same text and timestamps) is dropped from
  markdown only; the raw JSON keeps the provider payload untouched.

## Common Failures

- `auth[4]` on every command: `GRANOLA_API_KEY` missing or revoked; keys are created per user in
  Granola Settings -> API.
- Note absent from `list`: Granola only exposes notes that already have a generated AI summary and
  transcript. Wait for processing.
- `usage[2]` mentioning `page_size`: `/v1/notes` and `/v1/folders` cap page size at 30,
  `/v1/notes/{id}/transcript` at 100. The connector clamps automatically; a raw API call may not.
- `/v1/audit` returns 404 with a personal API key — audit events require a workspace-scoped key,
  and the connector deliberately does not expose them.
- Rate limit is 25 requests per 5 seconds, sustained 5/s. The client honours `Retry-After` on 429;
  a full-history `sync` still takes minutes, not seconds.
