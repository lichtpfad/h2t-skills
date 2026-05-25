---
title: "h2t-ops Drive Parity Migration — Design"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-20"
milestone: ""
---
# h2t-ops Drive Parity Migration — Design

**Status:** Draft for review
**Date:** 2026-05-20
**Issue:** #133
**Model:** procedural index (references authority, does not duplicate it)

**Related authority documents:**

- Connector runbook (`plugins/h2t-ops/references/h2t-connector-runbook.md`)
- API coverage audit (`docs/reports/2026-05-19-h2t-ops-api-coverage-audit.md`) — §3 "Drive — #133", §6 "Google Drive (Drive API v3)", item §6.8 "Drive — share/permissions and create-folder" (deferred)
- Calendar parity design (`docs/superpowers/specs/2026-05-20-h2t-ops-calendar-parity-design.md`) — establishes the Google OAuth substrate (`core/google_auth.py`) which Drive consumes
- POS operational boundary (`plugins/h2t-ops/references/pos-operational-boundary.md`)
- Testing plan (`docs/h2t-ops-testing-plan.md`)
- Roadmap section `### skills: [TZ-1] Migrate Drive connector` in `docs/h2t-ops-roadmap.md`
- Follow-up: **#147** — Retire Drive `sync-meetings` legacy workflow (explicit non-goal here)
- Provider-features follow-up (separate scope): create-folder, share/permissions, move/copy/rename, delete, revisions, shared drives (audit §6.8) — tracked when filed.
- Legacy — `plugins/h2t-ops/skills/drive/scripts/drive_cli.py`, `plugins/h2t-ops/skills/drive/SKILL.md`
- Gmail / Calendar connectors — `h2t_ops/connectors/{gmail,calendar}/` (pattern to copy)

---

## Goal

Migrate Drive from the skill-local `drive_cli.py` to the h2t-ops standard at
**parity** with the legacy script's pure-API surface (`list`, `search`,
`folders`, `download`, `export`, `upload`). Provider-feature expansion
(create-folder, share/permissions, move/copy, delete, revisions, shared
drives — audit §6.8) and security-tightening (`drive.file` + `drive.readonly`
narrower scopes) are explicitly **out of scope**; they will be tracked as
follow-up issues.

`sync-meetings` is **not migrated**. It is a coordinator/POS pipeline that
predates the MeetGeek connector and writes `$DOR_ROOT/context/meetings/**`
via a DOR-internal converter; this violates the runtime/coordinator split.
Its disposition is tracked in **#147**.

The Google OAuth substrate `h2t_ops/core/google_auth.py` (introduced for
#132 Calendar) is **extended** by this design to recognise
`service_name="drive"` — its first non-Gmail/Calendar consumer. No
behavioural change for existing services.

## Authority order

When this design and an authority document disagree, the authority wins:

1. TZ-0 connector architecture spec
2. Connector runbook (#138)
3. API coverage audit (2026-05-19)
4. POS operational boundary
5. Testing plan
6. Calendar parity design (Google OAuth substrate contract)
7. Gmail / Calendar connector code + legacy `drive_cli.py`

## Scope / non-goals

**In scope:**

- `h2t_ops/connectors/drive/{__init__.py, client.py, commands.py}` — parity
  surface only (6 verbs, see "Drive connector — parity surface").
- `h2t_ops/core/google_auth.py` — extend `_candidate_paths()` to accept
  `service_name="drive"` (shared OAuth store only; no Drive-specific
  fallback path). Single ~3-line delta; no other change.
- `h2t_ops/cli.py` — add `"drive"` to `_MIGRATED`. No `ingest drive`
  deprecation shim is needed (legacy `lib/clients/drive.py` does not exist;
  there is no `h2t ingest drive` path in `cli.py`).
- Skill-side update — `plugins/h2t-ops/skills/drive/SKILL.md` rewritten to
  delegate to `h2t-ops drive …` for the six parity verbs; `sync-meetings`
  documented as legacy debt with a pointer to #147 (the section is **not
  removed in this PR** — that is #147's job).
- Tests — Drive API + Drive CLI + missing-scopes upfront detection +
  `download` envelope shape + lazy-registry guard coverage already-present
  for `google*` (Calendar pre-req).
- Live read-only smoke through the installed CLI.

**Non-goals (explicitly excluded — prevents doc/scope mixing):**

- `sync-meetings` migration → **#147**.
- Provider-feature expansion (create-folder, share/permissions, move/copy,
  delete, revisions, shared drives) → separate follow-up issue.
- Security-tightening (narrower scopes) → separate follow-up issue.
- De-duplication of the Drive client embedded in
  `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py:612-755` → part
  of #134 MeetGeek migration.
- Bootstrap CLI for the Drive scope — bootstrap remains an explicit operator
  action (same stance as Calendar).
- POS / storage workflows (`~/.dor/**` writes) — boundary preserved, no
  introduction.

## Auth model

Inherits the Calendar design auth model in full. The Drive-specific points:

- **Scope (parity):** `https://www.googleapis.com/auth/drive` — the same
  broad scope the legacy `drive_cli.py:65` requested. Security-tightening to
  `drive.file` + `drive.readonly` is a separate follow-up issue; doing it
  inside #133 would (a) break parity, (b) almost certainly require a token
  re-bootstrap, and (c) silently restrict `upload`/read of pre-existing
  non-app-created files.
- **Combined-token assumption:** Drive joins Gmail + Calendar in the
  **single combined token** at `~/.config/google-calendar-mcp/tokens.json`
  with union scopes. Today's locally bootstrapped tokens typically lack the
  Drive scope; the connector surfaces this as a typed `ConfigError` with the
  neutral bootstrap hint at the first call. This is intentional UX, mirroring
  Calendar's missing-scopes upfront detection.
- **Token store policy:** shared OAuth store **only** for Drive (no
  Drive-specific fallback path). Mirrors Calendar's policy in
  `core/google_auth.py:_candidate_paths()`.
- **Bootstrap hint (neutral):** the existing hint in
  `core/google_auth.py:_BOOTSTRAP_HINT` already reads:
  > "Run an explicit Google OAuth bootstrap/setup flow to create the
  > Google OAuth token store, then retry."
  This is reused verbatim; the `ConfigError.message` itself may name the
  missing scope (e.g. `"missing required scope(s):
  https://www.googleapis.com/auth/drive"`), which `_validate_scopes()`
  already does. No hint-text change is needed.

## `core/google_auth.py` — minimal extension

Single delta at `h2t_ops/core/google_auth.py:90` (`_candidate_paths()`):

```python
if service_name == "drive":
    return [shared]
```

No other change. The function still raises `ConfigError("google_auth:
unknown service_name …")` for anything else. The lazy-import seams, scope
validation, refresh / writeback paths, and bootstrap hint stay byte-identical.

## Drive connector — parity surface

`h2t_ops/connectors/drive/__init__.py`:

```python
CONNECTOR = ConnectorSpec(
    name="drive",
    help="Work with Google Drive files",
    client="h2t_ops.connectors.drive.client:DriveClient",  # lazy ref
    register=register,
)
```

`h2t_ops/connectors/drive/client.py` — `DriveClient` with parity methods:

| Method | Wraps legacy | Parity notes |
|---|---|---|
| `list_files(folder=None, max_results=None)` | `drive_cli.py:list_files` | pagination preserved; rows = `id/name/mimeType/modifiedTime/size` |
| `search_files(query, mime_filter=None, max_results=None)` | `search_files` | `--type docx\|folder` mime filter preserved |
| `list_folders(parent=None, max_results=50)` | `list_folders_cmd` | parity (folders-only listing) |
| `download_file(file_id, dest=None)` | `download_file` | default `dest = CWD / original_name`; **never writes to stdout**; returns `{saved_path, file_id, name, mimeType}` plus `size` only when provider metadata included it |
| `export_file(file_id, fmt=None, dest=None, to_stdout=False)` | `export_file` | Google Docs/Sheets/Slides export with format map; `--print` → stdout; `md` keeps html2text path (lazy import → `ConfigError` if missing) |
| `upload_file(file_path, folder, no_convert=False)` | `upload_file` | **`folder` is required** (no interactive `input()`); auto-convert map preserved |

`_map_http_error` mirrors `h2t_ops/connectors/gmail/client.py:137` (no
behavioural difference vs Calendar). Lazy google imports via
`core/google_auth.py`. Typed errors per `core/errors.py`.

`h2t_ops/connectors/drive/commands.py` — six argparse subcommands matching
the methods above. Non-export verbs use the standard envelope flags
`--json` and `--format md|human`. `export` is a deliberate exception:
its `--format` flag keeps the legacy/provider meaning (`text|csv|md|docx|xlsx|pdf|pptx`),
so it only gets the envelope `--json` flag and does not expose envelope
`--format md|human`. Lazy client import inside `run()`. No envelope
construction in commands (runbook §6).

`h2t_ops/cli.py` — add `"drive"` to `_MIGRATED` (currently at line 18). **No
`ingest drive` deprecation shim** — there is no legacy ingest entrypoint.

## Verb contracts (locked decisions)

### `download` — output contract

Decision: default to legacy behaviour (write into CWD with original
filename), **never** emit binary to stdout, return a structured envelope.

| Argument | Default | Effect |
|---|---|---|
| `<file_id>` | required | provider file id |
| `--dest PATH` | `./{name}` | resolved path; mkdir parents as needed |

| Output | `--json` | Human |
|---|---|---|
| envelope body | `{saved_path, file_id, name, mimeType}` plus `size` **only when** the provider's `files.get(fields="size")` returned a value (Google editor files report no size) | `Downloaded: <saved_path>` (one line) |
| progress | suppressed | suppressed (legacy printed a `%` line; this is dropped — runbook §6 forbids printing from commands, and progress is incompatible with `--json`) |

### `export` — output contract

| Argument | Default | Effect |
|---|---|---|
| `<file_id>` | required | Google editor file id |
| `--format` | per-mime default | provider export format: `text\|docx\|pdf` (Doc), `csv\|xlsx\|pdf` (Sheet), `pdf\|pptx` (Slides), `md` (Doc — via lazy html2text). This is **not** the envelope `--format md|human` flag used by other verbs. |
| `--dest PATH` | `./{safe_name}{ext}` | resolved path |
| `--print` | false | when set, write text content to stdout; allowed formats: `text`, `csv`, `md`. Binary formats (`docx`, `xlsx`, `pdf`, `pptx`) → `UsageError`. |

Envelope on file output: `{saved_path, file_id, name, source_mime, export_mime, format}` plus `size` when the resulting file's size is known after write.

### `upload` — output contract

| Argument | Default | Effect |
|---|---|---|
| `<file>` | required | local path |
| `--folder NAME` | **required for parity** | folder **name** resolved via `_resolve_folder_id` |
| `--no-convert` | false | disable auto-convert map |

Interactive `input()` prompt is **dropped**. If `--folder` is omitted, the
parser raises `UsageError("--folder is required")`.

**Folder-name resolution semantics** (Drive folder names are not unique):

| Resolved count | Behaviour |
|---|---|
| 0 matches (folder missing or trashed) | `NotFoundError("folder not found: <name>")` |
| 1 match | use it |
| ≥ 2 matches | `UsageError("folder name '<name>' is ambiguous: N matches; pass an unambiguous name (folder-id selection will be added by a future follow-up)")` |

A future `--folder-id` flag may be added by a follow-up issue (out of scope
for #133). Parity #133 ships **only** `--folder NAME`.

Envelope: `{file_id, name, mimeType, web_view_link, folder_name}`.

### `list` / `search` / `folders` — output contract

Envelope rows preserve the columns surfaced by the legacy human output, in
canonical form: `[{id, name, mimeType, modifiedTime, size?}, …]` plus
`{folder_name?, count}` envelope meta. Human output stays close to the
legacy table.

## Skill-side update — Drive `SKILL.md`

The skill is rewritten to delegate the six parity verbs to `h2t-ops drive
…`. The historical `sync-meetings` section is **kept** (deletion is #147's
DoD) but is reframed as legacy debt:

> **Legacy workflow (do not use for new work):** the `sync-meetings`
> subcommand of the local `drive_cli.py` predates the MeetGeek connector and
> writes into `$DOR_ROOT/context/meetings/`. It is being retired — see
> #147. New work should use `h2t-ops meetgeek …` (when available) plus an
> explicit coordinator step.

`DOR_ROOT` / `VAULT_ROOT` env vars stay documented in the skill **only** for
that legacy section; the new `h2t-ops drive …` verbs do not read them.

## Tests

- **Drive API** — happy path for each verb against a mocked `service`;
  typed error mapping (`ConfigError` for missing libs/creds/scope,
  `AuthError` for 401/403, `NotFoundError` for 404, `ProviderError` for
  5xx, `NetworkError` for transport/timeouts).
- **Drive CLI** — parser registration; `--json` envelope shape per verb;
  `--help` exits 0; `upload` without `--folder` → `UsageError`; `--print`
  on a binary export format → `UsageError`.
- **Missing-scopes test case (NEW vs legacy)** — token loaded with Gmail +
  Calendar scopes but **without** the Drive scope →
  `resolve_google_credentials("drive", [drive_scope])` raises `ConfigError`
  with the neutral bootstrap hint. Mirrors the Calendar missing-scopes test.
- **`download` envelope shape** — explicit assertion that no bytes leak to
  stdout and that the envelope contains `saved_path` matching the resolved
  default path; verifies the legacy CWD default is preserved.
- **`export --format md`** — html2text missing → `ConfigError` (lazy import
  guard); html2text present → expected markdown.
- **Lazy-registry guard** — already covers `google*` after Calendar's T1.
  Drive adds no new heavy SDK; reusing the same guard is sufficient (#138
  cross-cutting risk closed by Calendar).

## DoD / PR gate (runbook §4 nine-item checklist, #133-specific evidence)

1. **Legacy parity** — list / search / folders / download / export / upload
   re-wrap; `sync-meetings` excluded with a pointer to #147.
2. **Provider API gaps** — create-folder, share/permissions, move/copy,
   delete, revisions, shared drives tracked as separate follow-up;
   acknowledged as audit §6.8.
3. **Auth/secrets** — consumes `core/google_auth.py` substrate via the new
   `service_name="drive"` branch; shared OAuth store only; broad `drive`
   scope (parity).
4. **Lazy imports** — `dev check lazy-registry` already covers `google*`
   (Calendar pre-req); no module-level google imports in Drive code.
5. **Tests** — Drive API + Drive CLI + missing-scopes + `download` envelope
   + `export md` html2text guard.
6. **Live smoke** — `h2t-ops drive list --json`, `drive folders --json`,
   `drive export <known-doc-id> --print --format text`. Live `upload` is
   not part of automatic live smoke — it is a provider write and runs only
   when explicitly requested with a known test-safe folder. Honest "blocked
   on bootstrap/scope" classification if the local token lacks the Drive
   scope.
7. **POS boundary** — no `~/.dor` writes from any new code; module-level
   DOR constants are **not** carried into `h2t_ops/connectors/drive/`;
   `sync-meetings` migration tracked in #147.
8. **Distribution-without-POS** — connector imports no
   `pos`/`dor.db`/`vault`/`lake`; runs with POS absent.
9. **Write side effects** — `drive upload` is the only write verb; an
   explicit user-intent CLI verb per runbook §7; covered by tests; not
   auto-triggered from workflows.

## Implementation plan outline (5 tasks, mirrors #144 / Calendar #132)

1. **T0** — Extend `core/google_auth.py:_candidate_paths()` with the
   `service_name="drive"` branch + tests covering the new branch
   (positive: shared path resolved; negative: still `ConfigError` for
   unknown services). **One commit.**
2. **T1** — Create `h2t_ops/connectors/drive/{__init__.py, client.py}` +
   client-level tests (API + typed errors + missing-scopes case +
   `download` envelope shape + `export md` html2text guard +
   `upload` ambiguous-folder resolution). **One commit.**
3. **T2** — Create `h2t_ops/connectors/drive/commands.py`; wire `cli.py`
   (`_MIGRATED` only — no ingest shim); commands-level tests (parser
   registration, `--json`, `--help`, `upload` requires `--folder`,
   `--print` on binary → `UsageError`, `--print` allowed-formats set
   `{text, csv, md}`). **One commit.**
4. **T3** — Skill `SKILL.md` rewrite to delegate to `h2t-ops drive …`;
   reframe `sync-meetings` as legacy debt (pointer to #147); the
   subcommand itself and its DOR_ROOT/VAULT_ROOT/MEETINGS_DIR/CONVERT_SCRIPT
   constants are **not** removed here (that is #147's DoD). **One commit.**
5. **T4** — Closure: full pytest sweep + runbook §4 9-gate self-review +
   installed-CLI live read-only smoke (`drive list --json`,
   `drive folders --json`, `drive export … --print --format text`).
   **Zero commits unless drift is found**; evidence captured in the issue
   per `docs/h2t-ops-testing-plan.md`.

Each commit-bearing task (T0–T3) is a single commit on a single branch;
commits are sequenced T0 → T1 → T2 → T3 → T4-evidence. T0 is purely
additive to a shared module and is safe to ship independently if review on
T1–T3 stalls.
