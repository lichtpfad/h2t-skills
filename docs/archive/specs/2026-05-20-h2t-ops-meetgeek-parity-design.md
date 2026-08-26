---
title: "h2t-ops MeetGeek Parity Migration — Design (#134)"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-20"
milestone: ""
---
# h2t-ops MeetGeek Parity Migration — Design (#134)

**Status:** Draft — review-ready  
**Date:** 2026-05-20  
**Author:** lichtpfad  
**Issue:** [#134 Migrate MeetGeek connector](https://github.com/lichtpfad/h2t-skills/issues/134)  
**Hard non-regression:** [#149 Preserve MeetGeek local recording recovery workflow](https://github.com/lichtpfad/h2t-skills/issues/149)

---

## Goal

Migrate the pure-API read verbs and the single provider-write verb (`submit-url`) from
`plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py` into the `h2t_ops` connector
runtime, following the established three-file pattern (Gmail/Calendar/Drive).

The composite coordinator workflows (`sync`, `upload --from-file`, `convert`,
`drive-upload`, `webhook-server`) are **not migrated** — they are explicitly out of scope
and preserved via legacy skill path until #149 and future POS/VPS work address them.

---

## Scope

### IN — h2t_ops/connectors/meetgeek/

| Verb | Maps to legacy | API endpoint |
|---|---|---|
| `auth-check` | `cmd_auth_check` | `GET /v1/meetings?limit=1` |
| `teams` | `cmd_teams` | `GET /v1/teams` |
| `list` | `cmd_list` | `GET /v1/meetings` |
| `get` | `cmd_get` | `GET /v1/meetings/{id}` |
| `transcript` | `cmd_transcript` | `GET /v1/meetings/{id}/transcript` |
| `summary` | `cmd_summary` | `GET /v1/meetings/{id}/summary` |
| `highlights` | `cmd_highlights` | `GET /v1/meetings/{id}/highlights` |
| `insights` | `cmd_insights` | `GET /v1/meetings/{id}/insights` |
| `download-url` | `cmd_download` (URL only) | `POST /v1/meetings/{id}/download` → `download_link` |
| `submit-url` | `_post_upload` / `cmd_upload --download-url` | `POST /v1/upload` |

`download-url` returns the signed URL only — no file download to disk. Binary download
to disk is a coordinator concern (out of scope).

### OUT — preserved via legacy skill path

| Verb | Why out of scope | Tracked in |
|---|---|---|
| `sync` | Writes `~/.dor/lake/meetgeek/**`, cursor, manifest | #149 / future |
| `webhook-server` | Local HTTP server + disk writes — dev-only until POS/VPS | POS/VPS issue |
| `convert` | ffmpeg, local filesystem — no API calls | #149 |
| `drive-upload` | Duplicates Drive connector (#133) | #149 |
| `upload --download-url` | Compatibility alias → `h2t-ops meetgeek submit-url`; legacy `_post_upload` no longer called after T3 | T3 |
| `upload --from-file` | Coordinator pipeline: convert + Drive + submit + manifest/resume | #149 |
| `manifest.jsonl` state | POS artifact in `~/.dor/lake/` | #149 |

**Webhook handling is explicitly out of scope for #134.**  
The current skill-local `webhook-server` remains legacy/dev-only until POS/VPS exists.
Production webhook integration belongs to POS/VPS, where a stable public endpoint can
verify MeetGeek signatures, persist raw source events, route them through `pos_ingest`,
and trigger journal/capture workflows.  
Do not migrate `webhook-server` into `h2t_ops.connectors.meetgeek`.

---

## Architecture

### Three-file connector shape

```
h2t_ops/connectors/meetgeek/
    __init__.py     CONNECTOR = ConnectorSpec(...)
    client.py       MeetGeekClient
    commands.py     register(subparsers) → 10 argparse subcommands
```

Mirrors `h2t_ops/connectors/{gmail,calendar,drive}/` exactly.

### MeetGeekClient

Stateless HTTP wrapper. Consumes secrets via `h2t_ops.core.secrets` pattern — not
direct `~/.dor/secrets.env` dotenv load at module scope.

```python
# In __init__ (inside function, lazy):
from h2t_ops.core.secrets import load_secrets
load_secrets()
api_key = os.environ.get("MEETGEEK_API_KEY", "").strip()
if not api_key:
    raise ConfigError(
        "MEETGEEK_API_KEY not set.",
        hint="Add MEETGEEK_API_KEY to ~/.dor/secrets.env or set in environment.",
    )
```

No `google-api-python-client` or OAuth in this connector — MeetGeek uses Bearer key only.

### Lazy imports

No module-level `requests` import; import lazily inside client init. `dev check
lazy-registry` must stay green after every task.

### Error mapping

| HTTP status | h2t_ops error |
|---|---|
| 401 | `AuthError` |
| 404 | `NotFoundError` |
| 400 | `UsageError` |
| 429 | `ProviderError` (with rate-limit message) |
| 5xx | `ProviderError` |
| network timeout | `NetworkError` |

### API field refresh (T0 gate)

Legacy code sends `{"download_url": ..., "language": ..., "title": ...}` to `POST /v1/upload`.  
Official MeetGeek v1 docs mention `language_code` and `template_name`.

**T0 must verify the actual accepted fields before writing `submit_url()` in client.py.**  
Strategy: doc check + if inconclusive, send both `language` and `language_code` (MeetGeek
appears to accept either; send the canonical form once confirmed).  
`template_name` → add as `Optional[str]` in `submit_url()`, document in SKILL.md.  
Do not make destructive/live submit in T0 — API discovery only (GET endpoints only in T0 smoke).

---

## File Map

### T0 — API discovery (no code commit)

**Output artefacts (assembled in reply, not committed):**
- Endpoint/field matrix for `POST /v1/upload`: confirmed field names (`language_code` vs `language`, `template_name`, `title`)
- Confirmation of `POST /v1/meetings/{id}/download` response field (`download_link` vs `download_url`)
- Safe GET-only live smoke results (`auth-check`, `list --limit 1`)
- Decision: use `language_code` in `submit_url()` (or dual-field if API accepts both)

No provider-write submit (`POST /v1/upload`) in T0. Any live submit requires explicit maintainer approval before T2.

### T1–T3 code files

| File | Action | Task |
|---|---|---|
| `h2t_ops/connectors/meetgeek/__init__.py` | Create (T1 marker) → Modify (T2 CONNECTOR body) | T1, T2 |
| `h2t_ops/connectors/meetgeek/client.py` | Create | T1 |
| `h2t_ops/connectors/meetgeek/commands.py` | Create | T2 |
| `h2t_ops/cli.py` | Modify — add `"meetgeek"` to `_MIGRATED` | T2 |
| `tests/connectors/meetgeek/__init__.py` | Create (empty) | T1 |
| `tests/connectors/meetgeek/test_client.py` | Create | T1 |
| `tests/connectors/meetgeek/test_commands.py` | Create | T2 |
| `plugins/h2t-ops/skills/meetgeek/SKILL.md` | Modify — delegate migrated verbs to `h2t-ops meetgeek …`; `upload --download-url` becomes alias for `submit-url`; preserve `convert`/`drive-upload`/`upload --from-file` as legacy; pointer → #149 and webhook → POS/VPS | T3 |

**File-state verification before each task (per #144-T1 overwrite lesson):**

```bash
test -d h2t_ops/connectors/meetgeek/ && echo "T1: PRE-EXISTING" || echo "T1: clean Create"
test -d tests/connectors/meetgeek/   && echo "T1: PRE-EXISTING" || echo "T1: clean Create"
grep -q '"meetgeek"' h2t_ops/cli.py  && echo "T2: already in _MIGRATED" || echo "T2: clean Modify"
```

---

## Verb Contracts

### `list`
```
meetgeek list [--limit N] [--cursor C] [--from-date YYYY-MM-DD] [--to-date YYYY-MM-DD] [--json]
```
Client returns the **raw API response** for each meeting row. Display layer normalizes
known field aliases: `meeting_id|id` → `id`; `timestamp_start_utc|start_time` → `start_time`;
`timestamp_end_utc|end_time` → `end_time`. Both alias forms must be supported so the pre-existing
date-field fix from e29804a is not regressed. Pagination: `next_cursor` in envelope when more pages
exist.

### `get`
```
meetgeek get <meeting-id> [--json]
```
Returns full meeting metadata.

### `transcript / summary / highlights / insights`
```
meetgeek transcript <meeting-id> [--format md|json] [--json]
meetgeek summary    <meeting-id> [--format md|json] [--json]
meetgeek highlights <meeting-id> [--format md|json] [--json]
meetgeek insights   <meeting-id> [--format md|json] [--json]
```
`md` format: frontmatter (POS data-architecture v3.3 compatible) + body.  
`json` format: raw API response.  
Default: `md`.

### `download-url`
```
meetgeek download-url <meeting-id> [--json]
```
Returns `{meeting_id, download_url}` (normalizes from `download_link|download_url|url` — whichever
field the API returns). Does **not** download the file — returns the signed URL only. Caller decides
what to do with it. T0 verifies the actual response field name.

### `submit-url`
```
meetgeek submit-url <URL> [--title TITLE] [--language-code CODE] [--template TEMPLATE] [--json]
```
`POST /v1/upload` with `{download_url: URL, language_code?: CODE, title?: TITLE, template_name?: TEMPLATE}`.  
Returns `{message, meeting_id?}` envelope.  
Named `submit-url` (not `upload`) to distinguish from the recovery workflow pipeline.  
This is the only provider-write verb in #134.

### `auth-check`
```
meetgeek auth-check
```
`GET /v1/meetings?limit=1`. Exit 0 = ok, exit 1 = invalid key.

### `teams`
```
meetgeek teams [--json]
```
`GET /v1/teams`. Returns team list.

---

## SKILL.md Rewrite Strategy (T3)

- Migrated verbs (`auth-check`, `teams`, `list`, `get`, `transcript`, `summary`, `highlights`, `insights`, `download-url`, `submit-url`): delegate to `h2t-ops meetgeek <verb>`.
- `upload --download-url <URL>`: becomes a **compatibility alias** — SKILL.md routes it to `h2t-ops meetgeek submit-url <URL>` (new connector path). This eliminates the dual-path ambiguity; the legacy script's `_post_upload` is no longer called for this case after T3.
- Legacy-only verbs (`convert`, `drive-upload`, `upload --from-file`, `sync`, `webhook-server`): **keep in skill**, still invoke `$CLI <verb>` via legacy script. Add section header "Legacy / Recovery workflow (tracked in #149)" and note that `sync` and `webhook-server` are not migrated.
- Bump `metadata.version` from `1.1.0` to `1.2.0` (partial delegation is a contract change).

---

## Hard Constraints

- No module-level `requests`, `google.*`, or `dotenv` imports anywhere in `h2t_ops/connectors/meetgeek/`.
- `load_secrets()` called lazily inside `MeetGeekClient.__init__` only — not at module scope.
- No POS imports, no `~/.dor` writes, no `DOR_ROOT`/`VAULT_ROOT`/`MEETINGS_DIR` references in new code.
- No `sync` or `webhook-server` logic in the connector.
- `download-url` returns URL only — never writes binary to disk.
- `submit-url` is the only write verb; `upload --from-file` pipeline is #149.
- Stage only named task files per task; never `git add -A`.
- Outward-facing actions (push, GitHub comment, close issue) are user-gated.
- #149 is a hard non-regression: `convert`, `drive-upload`, `upload --from-file` must remain
  accessible via skill path throughout #134.

---

## Non-Goals

- `sync` migration — #149 / future
- `webhook-server` migration — POS/VPS issue
- `upload --from-file` pipeline extraction — #149
- Drive client de-duplication from `meetgeek_cli.py:612–755` — #149
- MeetGeek API scope expansion beyond current public endpoints
- Rate-limit retry tuning beyond current 3-retry exponential backoff
