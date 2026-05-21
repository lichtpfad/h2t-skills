# h2t-ops Telegram Parity Migration - Design (#135)

**Status:** Draft - review-ready  
**Date:** 2026-05-21  
**Author:** lichtpfad  
**Issue:** [#135 Migrate Telegram connector](https://github.com/lichtpfad/h2t-skills/issues/135)  
**Hard non-regression:** [#121 Telethon session schema mismatch](https://github.com/lichtpfad/h2t-skills/issues/121)

---

## Goal

Migrate the pure Telegram/Telethon runtime from
`plugins/h2t-ops/skills/telegram/scripts/telegram_cli.py` into the standard
`h2t_ops` connector architecture, without losing the existing higher-level
workflows (`digest`, `tasks`, `research`, `students`, `sync`).

This is not a rewrite of the whole Telegram skill. It is a boundary split:

- `h2t_ops.connectors.telegram` owns provider-specific Telegram access:
  authentication/session checks, dialogs, folders, messages, saved messages,
  mentions, and entity-cache bootstrap.
- The `h2t-ops:telegram` skill remains a compatibility wrapper while #135
  lands. It may temporarily keep composite workflow entrypoints, but those are
  not the target architecture.
- Portable analytics/workflow scripts own Gemini summaries/classification and
  declared artifact generation.
- POS/coordinator tooling owns the decision to accept captures/tasks/decisions,
  trigger provider writes, promote to journal/KB, and manage durable DOR/POS
  state.
- The Notion connector owns the provider-specific Notion API transport when an
  explicit coordinator action decides to write.

The existing integration is useful and must remain usable. #135 extracts the
stable provider layer underneath it, without blessing the current script as the
long-term boundary.

---

## Authority Order

When this design conflicts with implementation details, follow this order:

1. Connector runbook (`plugins/h2t-ops/references/h2t-connector-runbook.md`)
2. POS operational boundary (`plugins/h2t-ops/references/pos-operational-boundary.md`)
3. Roadmap (`docs/h2t-ops-roadmap.md`)
4. Current Telegram skill code
   (`plugins/h2t-ops/skills/telegram/scripts/telegram_cli.py`)
5. Current Telegram skill docs
   (`plugins/h2t-ops/skills/telegram/SKILL.md`)
6. Telethon official docs:
   - Client reference: `https://docs.telethon.dev/en/stable/quick-references/client-reference.html`
   - Sessions: `https://docs.telethon.dev/en/stable/concepts/sessions.html`

---

## Current State

### Files

| Area | Path | State |
|---|---|---|
| h2t-ops Telegram skill | `plugins/h2t-ops/skills/telegram/SKILL.md` | User-facing wrapper docs |
| h2t-ops Telegram script | `plugins/h2t-ops/skills/telegram/scripts/telegram_cli.py` | Working legacy implementation, ~50k |
| legacy monolith duplicate | `plugins/h2t/skills/telegram/**` | Same script; legacy overlap, not #135 |
| h2t_ops connector | `h2t_ops/connectors/telegram/` | Missing |
| Tests | `tests/connectors/telegram/` | Missing |

### Current Commands

| Legacy command | Current behavior | Telethon/API use | Target layer |
|---|---|---|---|
| `auth` | Two-step login, SMS code, optional 2FA | `send_code_request`, `sign_in`, `get_me` | Connector |
| `chat` | Read a single chat history | `iter_messages`, `iter_dialogs`, `get_me` | Connector |
| `mentions` | Scan selected chats for mentions | `iter_messages`, `iter_dialogs` | Connector read with explicit chat IDs |
| `bootstrap` | Warm Telethon entity cache | `iter_dialogs(limit=None)` | Connector utility |
| `scan-chats --import-folders` | Import Telegram folders into `chats.yaml` | `GetDialogFiltersRequest` | Split: API read in connector, file write in skill |
| `scan-chats` | Interactive Gemini classification to `chats.yaml` | `iter_dialogs` + Gemini | Workflow |
| `saved` | Saved Messages -> Gemini/MD | `iter_messages("me")` + Gemini + file write | Workflow over connector |
| `digest` | Channels -> Gemini/MD | `iter_messages` + Gemini + file write | Workflow over connector |
| `tasks` | Work chats -> Gemini -> Notion | `iter_messages` + Gemini + Notion | POS/coordinator |
| `research` | Saved/channels -> vault/Learning | `iter_messages` + Gemini + file write | POS/coordinator |
| `students` | Student groups -> Gemini -> Notion | `iter_messages` + Gemini + Notion | POS/coordinator |
| `sync` | Runs multiple workflows | Composite | Workflow |
| `cleanup --archive` | Finds dead chats, optionally archives | `iter_dialogs`, `edit_folder` | Separate provider-write follow-up |

### Current Problems

1. `telegram_cli.py` imports heavy optional SDKs at module scope:
   `telethon`, `google.genai`, and dotenv are loaded before command dispatch.
   This violates the lazy-registry rule for `h2t-ops --help` and
   `h2t-ops connectors`.
2. Telethon is not declared in `pyproject.toml`, but the script assumes it is
   present in `~/.h2t/venv`.
3. Telegram session state is a Telethon SQLite session at
   `~/.config/telegram/session`. It is a credential and can become
   incompatible across Telethon versions (#121).
4. Provider reads, AI interpretation, Notion writes, and DOR/POS file writes
   are mixed in one script.
5. No Telegram connector tests exist.
6. `cleanup --archive` is a Telegram account mutation and is not clearly
   separated from read-only cleanup reporting.

---

## Scope

### IN - `h2t_ops/connectors/telegram/`

Create the standard three-file connector:

```text
h2t_ops/connectors/telegram/
  __init__.py     CONNECTOR = ConnectorSpec(...)
  client.py       TelegramClientAdapter / TelegramConnectorClient
  commands.py     argparse subcommands, lazy client import
```

Recommended connector verbs:

| Verb | Purpose | Side effects |
|---|---|---|
| `auth status` | Check config/session/authorization state | None |
| `auth request-code --phone PHONE` | Request Telegram login code | Writes temporary auth state |
| `auth complete --phone PHONE --code CODE [--password PASSWORD]` | Complete login | Writes Telethon session |
| `dialogs` | List dialogs/chats/channels | None |
| `messages ENTITY` | Read messages from chat/channel/user | None |
| `saved-messages` | Read Saved Messages raw items | None |
| `mentions` | Read explicit `--chat-id` values for mentions | None |
| `folders` | Read Telegram dialog filters/folders | None |
| `bootstrap` | Warm Telethon entity cache via `iter_dialogs` | Writes Telethon session cache timestamp |

`bootstrap` is allowed because Telethon session cache warming is provider
runtime state, not POS state. It must not write DOR/vault/lake files.

### OUT - preserved temporarily as legacy workflows

These commands do **not** disappear. They remain in the `h2t-ops:telegram`
skill temporarily for compatibility, then move into portable workflow scripts
or POS/coordinator tooling depending on responsibility. They should call the
new connector for provider reads. #135 preserves availability; it does not make
their current location architecturally correct.

| Legacy command/function | Why not connector | Future shape |
|---|---|---|
| `saved` digest generation | Gemini interpretation + markdown output | Temporary skill workflow over `h2t-ops telegram saved-messages`; later portable workflow script |
| `digest` | Gemini summary + declared output path | Temporary skill workflow; later portable workflow script |
| `tasks` | Gemini extraction + task proposals; optional Notion action | Portable workflow script + POS/coordinator decision |
| `research` | Learning/research synthesis artifact | Portable workflow script + POS/coordinator intake |
| `students` | Gemini extraction + urgent student proposals; optional Notion action | Portable workflow script + POS/coordinator decision |
| `sync` | Composite batch workflow | Portable workflow/orchestrator script; POS owns acceptance/state |
| `scan-chats` interactive classification | Gemini + `chats.yaml` mutation | Temporary skill workflow; later portable workflow script |
| `cleanup --archive` | Mutates Telegram account | Separate explicit provider-write issue |
| Gemini summaries/classification | Interpretation, not provider I/O | Portable workflow scripts |
| Notion task creation | Cross-provider write transport | POS/coordinator decides; Notion connector executes |
| `context/telegram`, vault, lake writes | POS/DOR storage | POS/coordinator |

### Explicit Non-goals

- Do not implement transcript/message interpretation in the connector.
- Do not write POS journal rows, captures, tasks, decisions, or KB entries.
- Do not write to `~/.dor/lake`, `~/.dor/context`, vault, POS SQLite
  (`pos.db`, `dor.db`), or other DOR storage from
  `h2t_ops.connectors.telegram`. Telethon's own credential/session SQLite file
  is the only allowed SQLite write, and only for explicit `auth` and
  `bootstrap` operations.
- Do not migrate legacy `h2t/skills/telegram` in #135.
- Do not remove existing working workflow commands.
- Do not silently delete a broken Telethon session.
- Do not add `cleanup --archive` to the connector in #135.

---

## Telethon API Mapping

The current script already uses a small, stable subset of Telethon:

| Need | Current use | Telethon API |
|---|---|---|
| Create client | `TelegramClient(SESSION_FILE, api_id, api_hash)` | `TelegramClient` |
| Login code | `client.send_code_request(phone)` | `send_code_request` |
| Complete login | `client.sign_in(...)` | `sign_in` |
| 2FA | `SessionPasswordNeededError`, then `sign_in(password=...)` | `sign_in(password=...)` |
| Current user | `client.get_me()` | `get_me` |
| Dialogs | `client.iter_dialogs(limit=...)` | `iter_dialogs` / `get_dialogs` |
| Messages | `client.iter_messages(entity, limit=...)` | `iter_messages` / `get_messages` |
| Saved messages | `client.iter_messages("me")` | `iter_messages("me")` |
| Dialog folders | `client(GetDialogFiltersRequest())` | raw TL request |
| Archive chat | `client.edit_folder(id, folder=1)` | `edit_folder` |

Provider feature expansion that Telethon supports but is not needed for #135:

- media download/upload;
- sending/editing/deleting messages;
- reactions;
- participants/admin actions;
- advanced search/global search;
- account updates.

These should be separate issues if needed.

---

## Auth And Session Model

### Files

Keep the existing machine-local paths for compatibility:

```text
~/.config/telegram/
  config.json          {"api_id": N, "api_hash": "..."}
  session              Telethon SQLite session, credential-bearing
  auth_state.json      temporary phone_code_hash between request/complete
  chats.yaml           workflow configuration, owned by skill/workflow layer
  dialogs_bootstrapped entity-cache timestamp
```

### Secret Handling

The connector must not load `~/.dor/secrets.env` at module scope.

Telegram API credentials are not currently in `h2t_ops.core.secrets`; they are
stored in `~/.config/telegram/config.json`. #135 should preserve this for
parity, but wrap missing config in `ConfigError` with a neutral setup hint.

Suggested hint:

```text
Create ~/.config/telegram/config.json with {"api_id": ..., "api_hash": "..."},
then run h2t-ops telegram auth request-code --phone +...
```

### Session Compatibility (#121)

Telethon sessions are SQLite files and effectively credentials. A session file
created with one Telethon version can fail after a library upgrade.

#135 must include the #121 fix:

- Catch `ValueError`, `sqlite3.OperationalError`, and known Telethon session
  load failures around client connect/authorization/message reads.
- Return a typed error with a clear `SESSION_INCOMPATIBLE` marker.
- Do not delete or overwrite the session automatically.
- Include recovery steps:
  1. move/delete the old session manually if the user chooses;
  2. rerun `auth request-code`;
  3. rerun `auth complete`.
- Add tests for this path.

### Dependency Pinning

Declare Telethon in project dependencies or an equivalent h2t runtime
constraints file. Current #121 suggestion is `telethon>=1.36,<1.43`; current
PyPI has 1.43.x. The implementation plan must choose deliberately:

- conservative: `telethon>=1.36,<1.43` to avoid the observed 1.43 session risk;
- current-compatible: pin/test against `telethon>=1.43,<1.44` only after live
  smoke confirms existing session compatibility;
- exact pin: safest for reproducibility, more maintenance.

Recommendation for #135: conservative upper bound first, then a follow-up issue
to test and unpin/advance.

---

## Output Contracts

All connector commands must support `--json` and emit standard h2t-ops
envelopes through the existing CLI machinery.

### Dialog Row

```json
{
  "id": 123456,
  "title": "Chat title",
  "username": "optional_username",
  "kind": "user|group|channel|bot|unknown",
  "unread_count": 0,
  "is_archived": false
}
```

### Message Row

```json
{
  "id": 123,
  "chat_id": 456,
  "date": "2026-05-21T10:00:00+00:00",
  "sender_id": 789,
  "sender_name": "Name",
  "text": "message text",
  "urls": [],
  "reply_to_msg_id": null
}
```

### Auth Status

```json
{
  "configured": true,
  "session_exists": true,
  "authorized": true,
  "user": {
    "id": 123,
    "username": "username",
    "first_name": "Name"
  }
}
```

### Session Error Envelope

```json
{
  "ok": false,
  "provider": "telegram",
  "error": {
    "type": "auth",
    "message": "SESSION_INCOMPATIBLE: Telethon session file is incompatible with this Telethon version.",
    "hint": "Move ~/.config/telegram/session aside, then run h2t-ops telegram auth request-code --phone +..."
  }
}
```

This intentionally follows the existing `h2t_ops.core.envelope.error_envelope`
shape. Do not change the shared envelope for #135. The stable discriminator is
the `SESSION_INCOMPATIBLE` marker in `error.message`.

---

## Skill Compatibility

`plugins/h2t-ops/skills/telegram/SKILL.md` should be rewritten after connector
landing:

1. Provider reads delegate to `h2t-ops telegram ...`.
2. Existing workflow commands remain documented as legacy compatibility
   commands, not as the target Telegram skill architecture.
3. Troubleshooting documents #121 recovery.
4. POS boundary is explicit:
   - provider messages are evidence, not tasks;
   - Gemini summaries/classifications are analytics outputs and suggestions,
     not truth;
   - Notion task creation is a POS/coordinator action, not Telegram runtime.

Long-term shape:

- Telegram skill: provider access and recovery guidance.
- Portable workflow scripts: digest, classification, summaries, extraction,
  and declared artifact/proposal outputs.
- POS/coordinator layer: decides which proposals become accepted tasks,
  journal/KB entries, or provider writes; owns sync pipelines and durable local
  state.
- Notion connector: executes explicit Notion API writes when a coordinator
  action requests them.

The legacy `telegram_cli.py` can remain temporarily, but its read paths should
move toward invoking or sharing the new connector client instead of importing
Telethon directly.

---

## Portable Workflow Scripts

Some legacy Telegram workflows are useful and should remain scriptable. They
should not disappear into POS, and they should not stay embedded inside the
Telegram provider connector.

Target shape:

- `h2t-ops telegram ...` provides raw provider reads.
- Portable workflow scripts consume connector JSON and produce explicit
  artifacts/proposals.
- Skills are thin entrypoints/docs around those scripts.
- POS/coordinator may consume script outputs, but acceptance into journal, KB,
  tasks, or provider writes remains a POS/coordinator decision.

Examples:

```bash
h2t-ops telegram saved-messages --days 7 --json > saved.json
python scripts/workflows/telegram_digest.py --input saved.json --output digest.md

h2t-ops telegram messages <chat> --days 14 --json > chat.json
python scripts/workflows/telegram_tasks.py --input chat.json --output proposals/
```

Rules:

- Workflow scripts may call Gemini/LLMs explicitly.
- Workflow scripts may write declared output paths.
- Workflow scripts must have explicit input/output arguments.
- Workflow scripts must be runnable from any repo.
- Workflow scripts must not be imported by `h2t-ops --help` or connector
  registry.
- Workflow scripts must not write POS journal/KB directly.
- Workflow scripts must not write Notion unless invoked as an explicit
  coordinator action; when writing, the Notion connector executes transport.
- If producing POS-relevant output, prefer `proposed_capture/v1` or
  provider-neutral communication evidence artifacts.
- Connector code must not read or write `~/.config/telegram/chats.yaml`.
  Workflows may read/write it explicitly when their purpose is chat
  classification or configuration.

---

## Proposed Module Design

### `client.py`

Responsibilities:

- load Telegram config lazily;
- create Telethon client lazily;
- map Telethon/session errors to typed h2t errors;
- expose pure provider methods:
  - `auth_status()`;
  - `request_code(phone)`;
  - `complete_auth(phone, code, password=None)`;
  - `list_dialogs(limit=None, kind=None)`;
  - `list_folders()`;
  - `list_messages(entity, limit=..., days=None)`;
  - `list_saved_messages(limit=..., days=None)`;
  - `list_mentions(chat_ids, days=...)`;
  - `bootstrap_dialogs(force=False)`.

No Gemini, no Notion, no DOR paths, no markdown writes.

### `commands.py`

Responsibilities:

- argparse only;
- no Telethon import at module scope;
- lazy import `TelegramClientAdapter` inside `run()`;
- normalize human vs JSON output;
- keep provider-write actions explicit.

Suggested command surface:

```text
h2t-ops telegram auth status [--json]
h2t-ops telegram auth request-code --phone +... [--json]
h2t-ops telegram auth complete --phone +... --code ... [--password ...] [--json]
h2t-ops telegram dialogs [--limit N] [--kind user|group|channel|bot] [--json]
h2t-ops telegram folders [--json]
h2t-ops telegram messages <entity> [--days N] [--limit N] [--json]
h2t-ops telegram saved-messages [--days N] [--limit N] [--json]
h2t-ops telegram mentions --chat-id ID [--chat-id ID...] [--days N] [--json]
h2t-ops telegram bootstrap [--force] [--json]
```

Open naming detail for implementation plan:

- `messages <entity>` is clearer than legacy `chat --user`.
- The skill can keep a compatibility alias `chat --user` if needed.
- `saved-messages` is intentionally not named `saved`: the user-facing
  `saved` workflow remains the Gemini/markdown digest in the skill layer.
- Passing 2FA via `--password` preserves legacy parity but can leak into shell
  history. Prefer a future `--password-stdin` or prompt-based flow; do not
  expand auth UX in #135 unless needed for the #121 recovery path.

### `__init__.py`

Register:

```python
CONNECTOR = ConnectorSpec(
    name="telegram",
    help="Work with Telegram dialogs and messages",
    client="h2t_ops.connectors.telegram.client:TelegramClientAdapter",
    register=register,
)
```

### `h2t_ops/cli.py`

Add `"telegram"` to `_MIGRATED` only when the connector is complete enough that
`h2t-ops telegram ...` should route to the new runtime.

Do not add `ingest telegram` shims in #135.

---

## Test Plan

### Client Tests

Create `tests/connectors/telegram/test_client.py`.

Cover:

- missing `~/.config/telegram/config.json` -> `ConfigError`;
- missing Telethon dependency -> `ConfigError` with install/setup hint;
- session incompatible `ValueError` -> typed session error;
- `sqlite3.OperationalError` from session load -> typed session error;
- `auth_status()` configured/session/authorized variants;
- `request_code()` stores only expected temporary state;
- `complete_auth()` handles normal login and 2FA path;
- `list_dialogs()` maps Telethon dialog objects into stable rows;
- `list_messages()` maps message objects into stable rows;
- URL extraction from `MessageEntityUrl` / `MessageEntityTextUrl` if retained;
- `bootstrap_dialogs()` refresh behavior and timestamp write.

All Telethon objects should be fakes/mocks. Do not require live Telegram in
unit tests.

### Command Tests

Create `tests/connectors/telegram/test_commands.py`.

Cover:

- command registration and help parse;
- `--json` on all verbs;
- no client import at module scope;
- `auth` nested subcommands parse correctly;
- `messages`, `saved-messages`, `dialogs`, `mentions`, `folders`,
  `bootstrap` dispatch;
- `saved-messages` dispatch exists and is distinct from the legacy `saved`
  workflow name;
- error output path includes `SESSION_INCOMPATIBLE` in `error.message` for
  mocked session error;
- no Gemini/Notion imports in connector command module.
- grep guard: `h2t_ops/connectors/telegram/**` must not contain
  `google.genai`, `notion`, `DOR_ROOT`, `vault`, `lake`, `pos.db`, `dor.db`,
  `context/telegram`, or `chats.yaml` writes.

### Lazy Registry Guard

Every implementation task must preserve:

```text
h2t-ops --help
h2t-ops connectors
h2t-ops doctor
uv run h2t-ops dev check lazy-registry
```

Expected: none of these import `telethon`, `google.genai`, or `yaml`.

### Legacy Workflow Non-regression

Because existing workflows are useful, final closure must smoke:

```text
legacy telegram_cli.py --help
legacy telegram_cli.py saved --help
legacy telegram_cli.py digest --help
legacy telegram_cli.py tasks --help
legacy telegram_cli.py research --help
legacy telegram_cli.py students --help
legacy telegram_cli.py sync --help
```

If argparse does not support per-command help cleanly, use top-level `--help`
plus parser registration tests.

### Live Smoke

Live smoke is read-only unless explicitly approved:

```text
h2t-ops telegram auth status --json
h2t-ops telegram dialogs --limit 5 --json
h2t-ops telegram saved-messages --limit 5 --json
h2t-ops telegram messages <known-entity> --limit 5 --json
```

No `cleanup --archive`, no Notion writes, no DOR writes in live smoke.

---

## Runbook Gate Expectations

Before #135 can close:

1. `h2t-ops connectors` lists `telegram`.
2. `h2t-ops --help` and `h2t-ops connectors` do not import Telethon.
3. Missing Telethon dependency gives typed `ConfigError`, not traceback.
4. Missing Telegram config gives typed `ConfigError`, not traceback.
5. Session schema mismatch gives `SESSION_INCOMPATIBLE` in `error.message`,
   not traceback.
6. Connector code has no `google.genai`, Notion transport, `DOR_ROOT`,
   vault/lake/POS storage references, `context/telegram`, or `chats.yaml`
   writes.
7. Existing workflow commands are still present in the skill/legacy path.
8. Unit tests cover client + commands + lazy import guard.
9. Live read-only smoke passes or is explicitly skipped with reason.

---

## Follow-up Issues

Likely follow-ups after #135:

- Extract Telegram analytics/POS workflows into portable workflow scripts:
  move `digest`, `tasks`, `research`, `students`, `sync`, Gemini prompts, and
  optional Notion actions out of the provider connector/skill internals while
  preserving scriptable entrypoints that agents can run from any repo.
- POS Phase 6: define a provider-neutral communication message intake
  contract (`communication_message_artifact`) for Telegram/Gmail/etc. This is
  not #135.
- Explicit Telegram write verbs:
  `archive`, `send-message`, `delete`, etc. Only if needed, with confirmation.
- Telegram media download support.
- Provider-neutral POS intake for message artifacts/tasks.
- Legacy `h2t/skills/telegram` retirement after split-plugin migration is done.
- Telethon version advance after testing session compatibility with 1.43.x.

---

## Plan Decisions And Remaining Questions

Decisions already locked:

- `mentions` accepts explicit `--chat-id`; connector does not read
  `chats.yaml`.
- Legacy user-facing `saved` remains the markdown/Gemini workflow; connector
  exposes raw rows as `saved-messages`.
- `folders` is read-only in connector; `chats.yaml` updates belong to
  skill/workflow scripts.
- `sync` remains scriptable as a portable workflow/orchestrator, not embedded
  in the connector.

Remaining implementation-plan questions:

1. Dependency policy: conservative `telethon>=1.36,<1.43`, exact pin, or test
   current 1.43.x live before choosing?
2. Auth CLI naming: nested `auth request-code/complete/status` vs flat
   `auth --phone/--code` compatibility?

Recommended defaults:

- conservative Telethon upper bound for #135;
- nested auth commands;
- connector accepts explicit `--chat-id`, skill owns `chats.yaml`;
- connector `saved-messages` returns raw rows only; legacy `saved` remains a
  workflow command;
- `folders` read-only in connector, `chats.yaml` update in skill.
