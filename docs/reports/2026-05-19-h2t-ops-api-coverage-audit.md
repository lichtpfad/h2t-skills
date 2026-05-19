---
title: "h2t-ops Connector Migration — API Coverage Audit"
status: "informational"
date: "2026-05-19"
milestone: "TZ-1 / TZ-2"
---

# h2t-ops Connector Migration — API Coverage Audit

**Mode:** read-only audit. No code/repo changes made.
**Method:** 7 parallel read-only researcher agents (Sonnet), each verified claims against
code on disk (Read/Grep/Glob). Cross-cutting facts (`_MIGRATED` set, secrets path,
POS-import absence, registry contract) independently agreed across agents — no conflicts.
**Roadmap:** `docs/h2t-ops-roadmap.md` · **Boundary:** `plugins/h2t-ops/references/pos-operational-boundary.md`

---

## 1. Executive summary (10)

1. **Migrated 2 of 8**: Notion and Gmail live in `h2t_ops/connectors/`. Calendar / Drive /
   MeetGeek / Telegram / Research / fetch-ladder are skill-local scripts or legacy `lib/` only.
2. **Gmail = full parity** vs legacy lib and skill scripts; 30 tests green. Sole behavioral
   change: interactive OAuth removed (one-time bootstrap via `gmail_cli.py`).
3. **Notion = partial**: client full vs lib, but CLI lost `find-project-tasks`, `video`
   blocks silently dropped (data loss), and a **secrets regression**: the connector does not
   `load_dotenv(~/.dor/secrets.env)` whereas the lib client did.
4. **Distribution-without-POS verified**: zero imports of `pos`/`dor.db`/`vault`/`lake`
   anywhere in `h2t_ops/`. Runtime works with POS absent.
5. **POS-boundary violations are confined to un-migrated scripts**: MeetGeek
   `sync/convert/webhook` writes `~/.dor/lake/**` (CRITICAL); Telegram
   `digest/tasks/research/students` writes `DOR_ROOT/context/` + Notion subprocess; Drive
   `sync-meetings` writes `DOR_ROOT/context/meetings/`.
6. **Research is POS-clean**: all sidecars under `~/.h2t/research/`, never `~/.dor/`. But its
   provider envelope is richer than canonical `h2t_ops/core/envelope.py` — wrap, don't rewrite.
7. **Fetch ladder belongs under research** (`h2t-ops research fetch --url`), not a top-level
   connector — confirmed by roadmap (#137) and code coupling. fail-loud honored in both scripts.
8. **Calendar is the cheapest next step**: shares Google OAuth with Gmail (same
   `~/.config/google-calendar-mcp/tokens.json`, no separate bootstrap). Exact #132 delta below.
9. **Cross-cutting risks**: (a) `dev check lazy-registry` guard covers only `notion_client`+
   `httpx`, not google/telethon/exa; (b) Gmail auth is inlined, not in `secrets.py` —
   Calendar/Drive will duplicate it without a shared `resolve_google_credentials()`;
   (c) Telegram session-file = full account credential, creds in
   `~/.config/telegram/config.json`, not `~/.dor/secrets.env`.
10. **Daily Brief** (consumer, not connector) still calls legacy `lib/cli/main.py ingest …`
    even in the v2 skill; Calendar is the only blocker to switch it to `h2t-ops …`
    (Gmail/Notion already migrated).

---

## 2. Coverage matrix

| Area | Canonical impl | h2t_ops? | Rating | POS risk | Tests | Issue |
|---|---|---|---|---|---|---|
| **Notion** | `h2t_ops/connectors/notion/{client,commands}.py` | yes | **partial** (CLI gap + video drop + secrets regress) | none | targeted | patch + #138 |
| **Gmail** | `h2t_ops/connectors/gmail/{client,commands}.py` | yes | **full** | none | 30 pass | done (#131) |
| **Calendar** | `lib/clients/calendar.py`, `lib/cli/main.py` | no | **missing** (legacy partial: primary-cal only) | none | 4 (normalize only) | **#132** |
| **Drive** | `plugins/h2t-ops/skills/drive/scripts/drive_cli.py` | no | **missing**; pure-API ok, sync-meetings out-of-scope | **HIGH** | none | #133 |
| **MeetGeek** | `plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py` | no | **missing**; richest skill, reads clean | **CRITICAL** (lake) | 35+ skill-local pass | #134 |
| **Telegram** | `plugins/{h2t-ops,h2t}/skills/telegram/scripts/telegram_cli.py` | no | **missing**; raw reads ok, rest = interpretation | **HIGH** (DOR+Notion) | 0 | #135 |
| **Research/Exa** | `plugins/h2t-ops/skills/research/scripts/exa_search.py` | no | **missing**; scripts mature | none (`~/.h2t/`) | ~100 pass | #136 |
| **Fetch ladder** | `…/research/scripts/fetch_url.py` | no | **missing**; belongs under research | none | ~80 pass | #137 |
| **Daily Brief** | `plugins/h2t-ops/skills/daily-brief/SKILL.md` | n/a (consumer) | **excluded** (workflow, not connector) | none (v2) | 0 | post-#132 |
| **Runtime/core** | `h2t_ops/core/*`, `h2t_ops/cli.py` | yes | contract mature; 2 gaps (lazy-guard, google-auth helper) | none | — | #138 |

Coverage rating legend: `full` / `partial` / `thin wrapper only` / `missing` / `intentionally excluded`.

---

## 3. Per-API detailed notes (file references)

### Notion — partial (migrated, needs patch)

- Client is 1:1 with `lib/clients/notion.py` (9 methods ported); errors upgraded to typed
  (`h2t_ops/connectors/notion/client.py:17-45`), imports lazy (`client.py:54-78`).
- **Delta vs lib client**: no auto `load_dotenv(~/.dor/secrets.env)`. `resolve_notion_token()`
  (`h2t_ops/core/secrets.py:27`) reads only `os.environ` → `~/.config/notion/token`; the lib
  client did `load_dotenv` at import (`lib/clients/notion.py:15`). If the token lives only in
  `secrets.env` and `load_secrets()` is not called upstream → `ConfigError`. Primary regression.
- **Delta vs skill scripts**: `find-project-tasks` missing (present `lib/cli/main.py:291-295`,
  `plugins/h2t/skills/notion/scripts/notion_cli.py:787-795`). `video` block rendered as link in
  skill (`notion_cli.py:487-493`) but returns `""` in connector (`client.py:238-298`) — silent
  data loss, also present in lib client.
- Side effects: only `sync` writes a caller-specified path (`commands.py:113-115`). No sqlite/
  vault/lake writes. POS-clean.
- Tests: `tests/connectors/notion/test_client.py` (error mapping 13 cases, md↔block roundtrip),
  `test_commands.py` (lazy-import isolation, dispatch, deprecation shim). Untested:
  `create_page`, `update_page`, `replace_page_content`, `append_blocks`, `delete_block`,
  `_extract_property_value`, `sync` write path, `video` gap.

### Gmail — full (done, #131)

- Every legacy method/subcommand matched 1:1; added typed errors, lazy imports,
  `--format md|human`, non-interactive enforcement: `client.py:246-252` raises `ConfigError`
  instead of `run_local_server`. Seam `_install_app_flow()` (`client.py:91-104`) exists only
  for test assertion it is never reached.
- Auth: `~/.config/google-calendar-mcp/tokens.json` (preferred) or `~/.config/gmail/token.json`;
  token refresh writes back (`client.py:254`). Bootstrap: run
  `plugins/h2t/skills/gmail/scripts/gmail_cli.py labels` once. ⚠️ `gmail_cli.py:84` references
  `datetime` with no import — latent `NameError` for `normal`-format tokens.
- Write-risk: `send` (`messages.send`), `label` (`messages.modify` — can move to TRASH/SPAM).
  POS-clean (token under `~/.config/`, not `~/.dor/`).
- Tests: 30 pass (`tests/connectors/gmail/test_client.py` 17, `test_commands.py` 13).
- Absent at every layer (not a regression): `messages.trash`, `threads.list/get`, received-
  attachment download.

### Calendar — #132 exact delta

Template: `h2t_ops/connectors/gmail/`. Create:

1. `h2t_ops/connectors/calendar/__init__.py` →
   `CONNECTOR = ConnectorSpec(name="calendar", help="...", client="h2t_ops.connectors.calendar.client:CalendarClient", register=register)`.
2. `client.py` — move `lib/clients/calendar.py:32-71` into `__init__` with lazy google import;
   replace `FileNotFoundError`/`sys.exit` → `ConfigError(hint=...)`; `creds.refresh()` failure
   → `AuthError`; add `_map_http_error` mirroring `gmail/client.py:138-162`; `_normalize_event`
   verbatim from `lib/clients/calendar.py:154-179`. Auth path
   `~/.config/google-calendar-mcp/tokens.json` (shared with Gmail — **no separate bootstrap**).
3. `commands.py` — subcommands `list/search/get/create/delete` each with `--json --format`;
   `p.set_defaults(_handler=run)`; lazy client import in `run`.
4. `h2t_ops/cli.py` — add `"calendar"` to `_MIGRATED` (line 18) or an `ingest calendar` shim.
5. Tests `tests/connectors/calendar/test_{client,commands}.py`: no-libs→ConfigError,
   no-creds→ConfigError (browser never launched), refresh→AuthError, lazy-import guard,
   dispatch happy-path. Migrate the 4 `_normalize_event` tests from `tests/clients/test_calendar.py`.

- Legacy capability: `list/search/get/create/delete`, **primary calendar only**, no freebusy,
  no `calendarList`, no `events.patch/update`, no recurrence. Scope is full read+write
  (`lib/clients/calendar.py:58`).
- Core contracts to satisfy: `ConnectorSpec` (`registry.py:13`), `H2TError` hierarchy
  (`errors.py:5-42`), envelope via `cli._run_connector` (no manual envelope), lazy imports.
- Daily Brief consumer needs: `calendar list --days 1 --json` (today),
  `calendar list --days 7 --json` (week), optional `calendar search "<q>" --json`. No writes.

### Drive — #133 (split required, HIGH)

- **Pure Drive API (connector scope)**: `list`, `search`, `download`, `export`, `folders`,
  `upload` — stdout or caller-specified path.
- **Out-of-scope (POS) — exclude from connector**: `sync-meetings` writes
  `$DOR_ROOT/context/meetings/*.{docx,md}` (`drive_cli.py:562-579`), subprocesses DOR-internal
  `convert_docx_to_md.py` (`:597-614`). Module-level DOR constants `DOR_ROOT`/`VAULT_ROOT`/
  `MEETINGS_DIR`/`CONVERT_SCRIPT` (`drive_cli.py:31-34`) are imported even for read commands.
  `SKILL.md:76` advertises writing into DOR context as a connector capability — must be
  corrected in migration.
- Auth: shared Google OAuth `~/.config/google-calendar-mcp/tokens.json`; token refresh
  write-back (`drive_cli.py:78`). No tests.

### MeetGeek — #134 (split required, CRITICAL)

- **Pure API reads (connector scope)**: `auth-check`, `list`, `get`, `transcript`, `summary`,
  `highlights`, `insights`, `download` (URL-only), `teams`.
- **Out-of-scope (POS lake) — exclude from connector**: `sync` writes the whole
  `~/.dor/lake/meetgeek/**` tree + cursor `~/.dor/lake/_cursors/meetgeek.json`
  (`meetgeek_cli.py:1150-1192`); `convert` → `~/.dor/lake/meetgeek/uploads-staging`
  (`:513`); `manifest.jsonl` in lake (`:792-797`); `webhook-server` writes lake (`:1254`).
- Drive client **duplicated** inside `meetgeek_cli.py:612-755` (mirrors `drive_cli.py`) — must
  be de-duplicated in migration (shared `h2t_ops/connectors/drive/client.py` import or
  subprocess to `h2t-ops drive`).
- Bug: `cmd_transcript` (`meetgeek_cli.py:386`) passes stub `{"meeting_id": ...}` instead of a
  real `GET /v1/meeting/{id}` — frontmatter loses title/attendees/date.
- Auth: `MEETGEEK_API_KEY` from `~/.dor/secrets.env` (or shell env). Drive sub-flow uses shared
  Google OAuth. Bypasses POS#80 Drive auto-sync re-transcription bug (`SKILL.md:3,205`,
  `meetgeek_cli.py:9`).
- Tests: 35+ skill-local in `plugins/h2t-ops/skills/meetgeek/tests/test_meetgeek_cli.py`
  (mocked HTTP/FS) — port to new module structure.

### Telegram — #135 (split required, session-risk)

- **Raw connector reads (connector scope)**: `auth`, `saved`/`digest`/`tasks`/`chat`/
  `mentions`/`research`/`students` *fetch portion only*, `bootstrap`, `scan-chats` — config
  writes confined to `~/.config/telegram/`.
- **Out-of-scope (POS/interpretation) — exclude**: `cmd_{saved,digest,tasks,research,students}`
  write `DOR_ROOT/context/telegram/*.md` (`telegram_cli.py:252,345,463,858,981`); Gemini
  summarization/extraction; `_create_notion_tasks` subprocess (`:919-924`); `cleanup --archive`
  mutates Telegram account folders (`:1019-1024`).
- Latent `NameError`: `REPO_ROOT` undefined in `cmd_students` (`telegram_cli.py:907-908`).
- Session/auth risk: `~/.config/telegram/session` is a Telethon SQLite full-account
  credential (leak = full account compromise; no rotation/expiry). `api_id`/`api_hash` in
  `~/.config/telegram/config.json` plaintext — **not** `~/.dor/secrets.env` (inconsistency).
  2FA password passed as CLI arg (shell-history exposure). No session-expiry handling in code.
- Tests: 0.

### Research / Exa + fetch ladder — #136 / #137

- 7 modes confirmed (`exa_search.py:74-82`): fast/generic/news/academic/competitor/people/deep;
  plus `crawl` → Exa `/contents` (`exa_search.py:884`, bypasses mode config).
- Sidecars: `~/.h2t/research/*.{sources.json,partial.md}`, `.pending_telemetry.jsonl`
  (`exa_search.py:814-832,667`); `fetch_url.py:1156-1159` similar — **not POS** (never `~/.dor/`).
- Envelope mismatch: `exa_search.py:256-280` `build_envelope()` uses
  `status:OK/DEGRADED/FAILED`; `core/envelope.py:9-17` uses `ok:bool`. Resolution: wrap rich
  envelope as `success_envelope().result`, FAILED → `error_envelope()` (same approach as
  Notion/Gmail).
- Fetch ladder order `direct→jina→playwright→crawl4ai→firecrawl→browserless`
  (`fetch_url.py:745-755`; last 4 are configured stubs). Loop `fetch_via_ladder()`
  (`fetch_url.py:801-1012`): `ProviderHardGate` → stop; permanent/transient → next; DEGRADED
  candidates collected, best-by-`body_chars`. **Belongs under research**: roadmap `:277`
  ("not a top-level `fetch` connector", expose as `h2t-ops research fetch --url`), shared
  `--output-dir`/`--project`, no independent auth (only optional `JINA_API_KEY`).
- fail-loud: both scripts compliant (`EXA_ERROR:*` / `FETCH_ERROR:*` to stderr; silent
  WebSearch fallback explicitly forbidden `SKILL.md:86`). Exit-code divergence: research
  `0=ok,1=args,2=http,3=network,4=preflight,5=gated` vs canonical
  `0,1,2,3,4,5,6` (`errors.py:39-42`) — remap needed. Minor: `test_version_flag` expects
  `0.1.1`, code is `0.1.2`.
- Tests: ~100 (`tests/test_exa_search.py`) + ~80 (`tests/test_fetch_url.py`), mocked.

### Runtime / governance

- **Connector contract**: `registry.discover()` (`registry.py:21`) iterates
  `h2t_ops.connectors` subpackages, reads `CONNECTOR` (frozen `ConnectorSpec`, `:13`, lazy
  `"module:attr"` client string, never imported at registration). `envelope.success_envelope`/
  `error_envelope` (`:9-17`). `secrets.load_secrets()` no-override merge of `~/.dor/secrets.env`
  (`:9,12-24`) + `resolve_notion_token()` (`:27-40`). `cli.dispatch()` priority → `_MIGRATED`
  (`cli.py:18` = `{"notion","gmail"}`) → `_run_connector` → `emit`; else `_legacy` to
  `lib/cli/main.py`. `output.emit()` fail-loud on write error (`output.py:97-112`). Errors:
  `H2TError` → `UsageError/ConfigError/AuthError/ProviderError/NotFoundError/NetworkError`,
  exit table 0-6 (`errors.py:39-42`).
- **Lazy-import risk**: `dev check lazy-registry` (`dev.py:55-56`) guards only `notion_client`
  + `httpx`. Google/telethon/exa SDKs not guarded — a future connector importing them at
  module scope would break `h2t-ops --help`/`connectors`. Extend before #132/#133/#135 land.
- **Auth cross-cutting**: sources = `os.environ` → `~/.dor/secrets.env`
  (`secrets.py:9` `DEFAULT_SECRETS`) → connector-specific (`~/.config/notion/token`;
  `~/.config/google-calendar-mcp/tokens.json`). Gmail OAuth resolution inlined in
  `gmail/client.py:211-258`, not in `secrets.py` — no `resolve_google_credentials()` analogue;
  Calendar/Drive will duplicate. Two dotenv mechanisms coexist: stdlib `load_secrets()` vs
  `python-dotenv` `gmail/client.py:_load_dotenv()` (`:52`, silently skips if dotenv absent).
- **Distribution-without-POS**: grep confirms zero `pos`/`dor.db`/`vault`/`lake` imports across
  `h2t_ops/`. Only external delegation is `lib.cli.main` inside `_legacy()` (`cli.py:48`),
  itself POS-free. Verified runs POS-absent for notion/gmail.
- **Residual legacy `lib/cli/main.py`**: `gather` (session-start/handoff, no h2t_ops
  equivalent), `ingest calendar` (full, #132 target), legacy `_cmd_gmail/_cmd_notion` with
  `bare except Exception: print(...)` (`:239,420`) — not removed, diverge from contract.

---

## 4. "Do next" sequence

1. **#138 runbook baseline** — write before any new connector. Notion+Gmail as reference;
   must include POS-boundary checklist and distribution-independence check. DoD:
   `references/h2t-connector-runbook.md` (file layout, tests, error-map, output contract,
   review checklist).
2. **#132 Calendar** — first connector built by the runbook (lowest risk: shared Google OAuth).
   Delta in §3. In parallel: add shared `resolve_google_credentials()` to `core/secrets.py`
   (else Drive duplicates it again).
3. **Inventory gates Drive/MeetGeek/Telegram** — before code, lock the split: connector =
   pure-API reads only; `sync-meetings` / MeetGeek `sync,convert,webhook` / Telegram
   `digest,tasks,research,students` go to a coordinator layer or POS-owned, **not** the
   connector. De-duplicate the Drive client embedded in `meetgeek_cli.py`.
4. **Auth/session risks** — document Gmail bootstrap dependency in the runbook; decide
   Telegram session-file security posture for distribution; unify Telegram creds into
   `~/.dor/secrets.env`; remove the `_load_dotenv` vs `load_secrets` duplication.
5. **Optional-SDK / lazy-import** — extend `dev check lazy-registry` to `google*`, `telethon`,
   `exa` **before** Calendar/Drive/Telegram land; otherwise `h2t-ops --help`/`connectors`
   risks pulling SDKs.
6. **Write-operation / audit risks** — `gmail send/label`, `calendar create/delete`,
   `telegram cleanup --archive`, `meetgeek upload` mutate without a journal. Until POS
   journal commands exist, emit `proposed_capture` JSON (roadmap rule, `:97-109`); do not
   mutate stores.
7. **POS boundary** — no connector writes `~/.dor/pos.db`/`dor.db`/vault/lake; un-migrated
   scripts do (see §3). On migration, switch default `--output-dir`/`CONTEXT_ROOT` to stdout.
8. **Distribution-without-POS** — core verified clean; runbook gate: a new connector must not
   import POS and must not default-write into `~/.dor/`.

---

## 5. Open questions for the human architect

1. **Coordinator layer**: where do `sync-meetings` / MeetGeek `sync,convert,webhook` /
   Telegram `digest,tasks,research,students` go — a separate `h2t-ops` coordinator package,
   POS-owned, or stay skill-local until a POS journal API exists? Roadmap says emit
   `proposed_capture` — is that the final decision?
2. **`proposed_capture` contract**: is the format specified anywhere, or does it need design
   before Calendar `create/delete` ships?
3. **Notion patch now or later**: fix `video` drop + `find-project-tasks` + secrets regression
   in the already-migrated connector as a patch (before #138), or backlog it?
4. **Shared Google auth**: add `resolve_google_credentials()` to core **before #132**, or
   accept per-connector duplication and refactor later?
5. **Research envelope**: confirm "wrap rich envelope inside `success_envelope().result`" as
   canon, and sign off the exit-code remap table (`0-5` → `0-6`).
6. **Telegram security**: is a persistent full-account session-file acceptable in a
   distributable context? Move `api_id/api_hash` into `~/.dor/secrets.env`?
7. **Daily Brief**: switch Gmail/Notion to `h2t-ops …` now (already migrated) with Calendar
   later, or one PR after #132?
8. **lazy-guard scope**: make extending `dev check lazy-registry` to google/telethon/exa a
   mandatory PR gate before the respective connectors?

---

## 6. Provider API capability vs our command-line — feature gap

Different axis from §3: here the baseline is the **full documented provider API**, not our
existing local code. "Exposed" = reachable today through `h2t-ops` or the legacy `lib/cli`
(grounded in on-disk findings). Provider-side surface is from the public API specs.
Legend: yes = exposed · partial = exposed but limited · NO = provider supports it, our CLI
does not · — = not applicable.

### Gmail (Gmail API v1)

| Capability | Provider API | Our CLI | Note |
|---|---|---|---|
| List / search messages | yes | yes | `list`, `search` (Gmail query syntax) |
| Read message | yes | yes | `read` |
| Send message | yes | yes | `send` |
| Create draft | yes | yes | `draft` |
| Reply **in thread** when sending | yes | **partial** | `--thread-id`/`--reply-to` only on `draft`, NOT on `send` |
| Attachments (outgoing) | yes | yes | `--attach` |
| Download attachment (incoming) | yes | **NO** | no command at any layer |
| Labels list / modify | yes | yes | `labels`, `label --add/--remove` |
| Threads list/get as a unit | yes | **NO** | only per-message |
| Trash / untrash / delete | yes | **NO** | absent everywhere |
| Mark read/unread, star | yes | partial | via `label` modify (UNREAD/STARRED ids), not first-class |
| Watch / push (Pub/Sub) | yes | — | out of scope for CLI |

### Google Calendar (Calendar API v3) — highest-value gap for your use

| Capability | Provider API | Our CLI | Note |
|---|---|---|---|
| List events | yes | yes (legacy) | `list --days N`, primary calendar only |
| Search events | yes | yes (legacy) | `search` |
| Get event | yes | yes (legacy) | `get` |
| Create event | yes | yes (legacy) | `create summary date time` |
| **Invite attendees** | yes | yes (legacy) | `--attendees` (CSV), `sendUpdates=all` set |
| **Google Meet link** (conferenceData) | yes | **NO** | no `conferenceDataVersion`/`createRequest` — cannot auto-attach Meet |
| **Recurring / serial events** (RRULE) | yes | **NO** | no `--recurrence`; single events only |
| Reminders / notifications override | yes | **NO** | no reminder flags |
| Update / patch event | yes | **NO** | only create + delete; no edit/reschedule |
| Delete event | yes | yes (legacy) | `delete --confirm` |
| All-day events (date vs dateTime) | yes | **NO** | only timed events (`date`+`time` required) |
| RSVP / respond to invite | yes | **NO** | no attendee responseStatus update |
| Multiple / shared calendars | yes | **NO** | `calendarId="primary"` hardcoded |
| FreeBusy query | yes | **NO** | absent |
| calendarList (enumerate calendars) | yes | **NO** | absent |
| Move event between calendars | yes | **NO** | absent |
| Guests-can-modify / visibility / colorId | yes | **NO** | not exposed |
| Timezone | yes | partial | `--tz`, default `Asia/Jerusalem` |

This is where most "the CLI can't do that" friction will come from: **Google Meet, recurring
events, event editing, all-day events, multi-calendar, reminders** are all unsupported today.
#132 should be scoped to add them, not just re-wrap the existing thin client.

### Notion (Notion API)

| Capability | Provider API | Our CLI | Note |
|---|---|---|---|
| Get page / blocks | yes | yes | `get`, `blocks` |
| Query database (filter/sort) | yes | partial | `search` supports filter; sort not exposed |
| Get database schema | yes | yes | `get-database` |
| Find databases on page | yes | yes | `find-databases` |
| Create page | yes | yes | `create` (title + markdown) |
| Update page (props/append/replace) | yes | yes | `update` |
| Find project tasks (relation filter) | yes | **NO** | in legacy/skill, dropped in `h2t_ops` |
| **Global search** (`/v1/search`) | yes | **NO** | only DB query, no workspace search |
| Comments (create/list) | yes | **NO** | absent |
| Users list / me | yes | **NO** | absent |
| File / media upload | yes | **NO** | absent |
| `video` block render | yes | **NO** | silently dropped (data loss) |
| Block delete | yes | partial | client method exists, no CLI command |
| Pagination cursors exposed | yes | partial | internal only, not surfaced to caller |

### Google Drive (Drive API v3)

| Capability | Provider API | Our CLI | Note |
|---|---|---|---|
| List / search files | yes | yes | `list`, `search` |
| Download / export | yes | yes | `download`, `export` (text/docx/pdf/csv/xlsx/pptx) |
| Upload (+auto-convert) | yes | yes | `upload --no-convert` |
| List folders | yes | yes | `folders` |
| **Create folder** | yes | **NO** | only inside the duplicated MeetGeek client |
| **Share / permissions** | yes | **NO** | no permission set/get; cannot make public/share |
| Move / copy / rename | yes | **NO** | absent |
| Revisions / version history | yes | **NO** | absent |
| Trash / delete | yes | **NO** | absent |
| Shared drives support | yes | **NO** | absent |

### MeetGeek (MeetGeek Public API v1)

| Capability | Provider API | Our CLI | Note |
|---|---|---|---|
| List meetings (paged/date) | yes | yes | `list` |
| Get meeting metadata | yes | yes | `get` |
| Transcript / summary / highlights / insights | yes | yes | per-resource commands |
| Download recording (signed URL) | yes | yes | `download` |
| Upload recording for transcription | yes | yes | `upload` (coordinator workflow) |
| Teams | yes | yes | `teams` |
| Webhook registration via API | (n/a) | — | MeetGeek has no register API; local receiver only |

MeetGeek read coverage vs the provider API is effectively **complete** — the gaps here are
boundary/workflow (lake writes), not missing API features.

### Telegram (Telethon / MTProto user API)

| Capability | Provider API | Our CLI | Note |
|---|---|---|---|
| Read saved / channel / chat messages | yes | yes | `saved`, `digest`, `tasks`, `chat` |
| Mentions | yes | yes | `mentions` |
| List dialogs / folders | yes | yes | `bootstrap`, `scan-chats` |
| **Send message** | yes | **NO** | no `send` command — large gap for an interactive workflow |
| Edit / delete message | yes | **NO** | absent |
| Download media / files | yes | **NO** | absent |
| Forward messages | yes | **NO** | absent |
| Archive chat | yes | partial | only via `cleanup --archive` (bulk, risky) |
| Mark read | yes | **NO** | absent |

### Research / Exa (Exa API)

| Capability | Provider API | Our CLI | Note |
|---|---|---|---|
| Neural / keyword search (7 modes) | yes | yes | `search --mode` |
| Get contents / crawl | yes | yes | `crawl --url` |
| **Find similar** (`findSimilar`) | yes | **NO** | absent |
| **Answer endpoint** (`/answer`) | yes | **NO** | absent |
| URL fetch ladder (non-Exa) | (n/a) | yes | `fetch_url.py`; firecrawl/playwright = stubs |

### Highest-impact missing features (act on these first)

1. **Calendar — Google Meet attachment** (`conferenceData.createRequest`) — common ask;
   currently impossible from CLI.
2. **Calendar — recurring/serial events** (`recurrence: ["RRULE:..."]`) — impossible today.
3. **Calendar — edit/reschedule event** (`events.patch`) — only create+delete exist.
4. **Calendar — all-day events** — `create` forces a time.
5. **Telegram — send message** — read-only today; no way to reply/post from CLI.
6. **Gmail — reply-in-thread on `send`** — works for `draft` only; one-flag fix.
7. **Notion — global `/v1/search`** and **comments** — frequent workflow needs.
8. **Drive — share/permissions and create-folder** — needed for any "upload then share" flow.

Recommendation: fold these into the migration issues as explicit acceptance items —
**#132 must include Meet + recurrence + patch + all-day + multi-calendar**, not a thin
re-wrap; **#135 must add `telegram send`**; the Gmail thread-on-send and Notion
search/comments can be patches against the already-migrated connectors.

---

## Appendix — agent provenance

Audit produced by 7 read-only Sonnet subagents, one per domain (Notion, Gmail, Calendar,
Drive+MeetGeek, Telegram, Research+fetch-ladder, Runtime/Governance+DailyBrief). Every
non-obvious claim is file:line-cited in the source agent transcripts. No code or repository
changes were made during this audit.
