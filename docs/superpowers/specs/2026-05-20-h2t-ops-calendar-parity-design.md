# h2t-ops Calendar Parity Migration — Design

**Status:** Draft for review
**Date:** 2026-05-20
**Issue:** #132
**Model:** procedural index (references authority, does not duplicate it)

**Related authority documents:**

- Connector runbook (`plugins/h2t-ops/references/h2t-connector-runbook.md`)
- API coverage audit (`docs/reports/2026-05-19-h2t-ops-api-coverage-audit.md`) — §3 "Calendar — #132 exact delta", §6 "Highest-impact missing features"
- Roadmap section `### skills: [M3] Migrate Calendar connector (parity) — #132` in `docs/h2t-ops-roadmap.md`
- Provider-features follow-up: #145 (separate scope)
- POS operational boundary (`plugins/h2t-ops/references/pos-operational-boundary.md`)
- Testing plan (`docs/h2t-ops-testing-plan.md`)
- Gmail connector — `h2t_ops/connectors/gmail/` (Google OAuth pattern to factor out)
- Legacy — `lib/clients/calendar.py`, `lib/cli/main.py` (ingest calendar branch)

---

## Goal

Migrate Calendar from the legacy `lib/clients/calendar.py` to the h2t-ops
standard at **parity** with the legacy client (list / search / get / create /
delete, primary calendar only). Provider-feature expansion (Google Meet links,
recurrence, `events.patch`, all-day events, multi-calendar, reminders,
FreeBusy) is tracked in **#145** and explicitly out of scope.

As a prerequisite, extract Google OAuth resolution from Gmail into a shared
`h2t_ops/core/google_auth.py` substrate with a corrected non-interactive policy
and upfront scope validation, then migrate Gmail to use it (so the helper has
two real consumers from day one).

## Authority order

When this design and an authority document disagree, the authority wins:

1. TZ-0 connector architecture spec
2. Connector runbook (#138)
3. API coverage audit (2026-05-19)
4. POS operational boundary
5. Testing plan
6. Gmail connector code + legacy `lib/clients/calendar.py`

## Scope / non-goals

**In scope:**

- `h2t_ops/core/google_auth.py` — single-responsibility Google OAuth substrate
  (resolution, lazy import seams, scope validation, refresh, atomic token
  writeback).
- Gmail migration to consume the shared helper (API byte-identical; the
  30 existing Gmail tests are the regression guard).
- `h2t_ops/connectors/calendar/{__init__.py, client.py, commands.py}` — parity
  surface only.
- `ingest calendar` deprecation shim in `h2t_ops/cli.py` mirroring the Gmail
  §10.2 variant (consumes `--format <val>`: `json` → `--json`, drop others;
  warn on human output, silent under `--json`).
- Extend `dev check lazy-registry` to cover `google*` (audit cross-cutting
  risk; becomes relevant the moment Gmail's imports go through
  `google_auth.py`).
- Tests: Gmail regression + Calendar parity (API + CLI) + **missing-scopes
  upfront detection** + four `_normalize_event` legacy tests migrated.

**Non-goals (explicitly excluded — prevents doc/scope mixing):**

- Provider-feature expansion → **#145**.
- A full `h2t-ops google auth bootstrap` CLI is **NOT** shipped in #132.
  Bootstrap remains an explicit operator action; the legacy gmail skill is the
  current local way to perform it and is **allowed as a present-day workflow,
  but it is not an architectural dependency of `h2t-ops`**. A future dedicated
  bootstrap CLI is a separate follow-up.
- Drive connector migration (later wave).
- POS / storage workflows (`~/.dor/**` writes) — boundary preserved, no
  introduction.
- Architecture rationale → TZ-0 spec; audit findings → audit report; POS ADR
  content → POS repo / boundary reference.

## Auth model (refined from spec §4.1)

TZ-0 spec §4.1 ("no browser OAuth in the connector") stands, with the following
refinement that the audit + Google OAuth identity-protocol docs make explicit:

- **Normal connector commands** (`h2t-ops gmail list`, `h2t-ops calendar list`,
  etc.) MUST NEVER silently open a browser. Unchanged.
- **Explicit bootstrap is allowed** as a separate operator action — today via
  the legacy gmail skill, tomorrow potentially via a dedicated bootstrap CLI.
  The connector itself never triggers bootstrap.
- **Installed apps do NOT support incremental authorization** (Google OAuth
  identity protocol). Scopes must be planned ahead — #132 assumes a **single
  combined token** at the shared OAuth token store path with union scopes for
  Gmail + Calendar (Drive later).
- **Missing scopes are detected upfront** by `resolve_google_credentials()`
  and surface as a typed `ConfigError` with a neutral bootstrap hint. This is
  stricter than the legacy code (which would fail at the Google API call
  layer with a confusing 403). The change is an intentional UX improvement and
  is the reason for a dedicated missing-scopes test case.

## `core/google_auth.py` — helper API

Single-responsibility module, ~120 lines. Public surface:

```python
def resolve_google_credentials(
    service_name: str,          # "gmail" | "calendar"
    required_scopes: list[str],
) -> Credentials:
    """Non-interactive Google OAuth substrate. Never opens a browser.

    Resolution:
      1. Token discovery by service_name (see "Token fallback policy" below).
      2. Load + 'normal' wrap normalize + scope→scopes split (preserves the
         existing legacy file format produced by the bootstrap process).
      3. Validate required_scopes ⊆ token_scopes. If not → ConfigError with
         the neutral bootstrap hint (this is the stricter NEW behavior).
      4. If expired AND refresh_token present: refresh via Request(); else
         AuthError (no browser flow).
      5. Atomic token writeback when refreshed.
    """

def build_google_service(api: str, version: str, creds): ...
```

Plus lazy import seams (`_import_google`, `_request`, `_load_credentials`,
`_install_app_flow`). `_install_app_flow` remains a test-only seam asserting
that the browser flow is NEVER reached during normal commands.

### Token fallback policy (explicit by service)

The folder name `google-calendar-mcp` is a **legacy compatibility path** —
comments and docs call this the **"Google OAuth token store"**; the folder
name is kept only for backward compatibility with existing local installs and
is not a forward architectural commitment.

- `service_name="gmail"`: primary `~/.config/google-calendar-mcp/tokens.json`
  (Google OAuth token store), fallback `~/.config/gmail/token.json`. Matches
  today's Gmail connector behavior; preserved by T1.
- `service_name="calendar"`: primary `~/.config/google-calendar-mcp/tokens.json`
  **only**. No service-specific fallback (legacy `lib/clients/calendar.py` used
  only this path; #132 preserves that). A calendar-specific fallback may be
  added by a future plan if needed, but is not part of #132.

### Bootstrap hint (neutral)

When `resolve_google_credentials()` raises `ConfigError` (missing token,
missing required scopes, or missing `credentials.json`), the hint reads:

> "Run an explicit Google OAuth bootstrap/setup flow to create the Google OAuth
> token store, then retry."

The hint does **not** name `gmail_cli.py`, the legacy gmail skill, or any
specific bootstrap implementation. The legacy gmail skill is the current
operator-facing way to bootstrap and remains allowed for that purpose, but
it is not an architectural dependency of `h2t-ops`. A neutral hint keeps the
door open for a future `h2t-ops google auth bootstrap` CLI without rewriting
connector error messages.

## Calendar connector — parity surface

`h2t_ops/connectors/calendar/__init__.py`:

```python
CONNECTOR = ConnectorSpec(
    name="calendar",
    help="Work with Google Calendar events",
    client="h2t_ops.connectors.calendar.client:CalendarClient",  # lazy ref
    register=register,
)
```

`h2t_ops/connectors/calendar/client.py` — `CalendarClient` with parity methods
(`list_events`, `search_events`, `get_event`, `create_event`, `delete_event`).
`_normalize_event` ported verbatim from legacy `lib/clients/calendar.py`.
`_map_http_error` mirrors `h2t_ops/connectors/gmail/client.py:137`. Lazy import
of google libs via `core/google_auth.py`. Typed errors per `core/errors.py`.

`h2t_ops/connectors/calendar/commands.py` — five argparse subcommands
(`list`, `search`, `get`, `create`, `delete`), each with `--json` and
`--format`. Lazy client import inside `run()`. No envelope construction in
commands (envelope is `emit()`'s job per runbook §6).

`h2t_ops/cli.py` — add `"calendar"` to `_MIGRATED` (currently at line 18);
add `ingest calendar` deprecation shim after the `ingest gmail` shim,
mirroring its `--format <val>` consumption pattern.

## Tests

- **Gmail regression** — existing 30 tests stay green after T1's refactor;
  they are the regression guard for the helper extraction.
- **Calendar API** — happy path + typed error mapping (no libs/creds →
  `ConfigError`; refresh failure → `AuthError`; HTTP 404 → `NotFoundError`;
  HTTP 5xx → `ProviderError`; transport → `NetworkError`).
- **Calendar CLI** — parser registration; `--json` / `--format`; help; ingest
  shim warn-on-human / silent-on-json behavior.
- **Lazy-registry guard** — extended to cover `google*` (T1).
- **Missing-scopes test case (NEW vs legacy)** — token with Gmail scope but
  without Calendar scope → `resolve_google_credentials("calendar", [calendar_scope])`
  raises `ConfigError` with the neutral bootstrap hint.
- **`_normalize_event` × 4** — migrate the legacy tests from
  `tests/clients/test_calendar.py` (timed event, all-day fallback, missing
  fields, the "весь день" Russian-locale string preservation).

## DoD / PR gate (runbook §4 nine-item checklist, #132-specific evidence)

1. **Legacy parity** — list / search / get / create / delete re-wrap, primary
   calendar only.
2. **Provider API gaps** — tracked in #145; not addressed here.
3. **Auth/secrets** — `core/google_auth.py` shared substrate; no inlined OAuth
   duplication; folder name treated as compatibility path.
4. **Lazy imports** — `dev check lazy-registry` covers `google*`; no
   module-level google imports in connector code.
5. **Tests** — Gmail regression 30/30 + Calendar API + Calendar CLI +
   missing-scopes + four normalize.
6. **Live smoke** — `h2t-ops calendar list --days 1 --json`, `--days 7 --json`
   (read-only). Honest "blocked on bootstrap/scope" classification if the
   current local token lacks the Calendar scope — that is OAuth reality, not
   a code failure.
7. **POS boundary** — no `~/.dor` writes; token writeback stays in
   `~/.config/google-calendar-mcp/` per legacy compatibility.
8. **Distribution-without-POS** — connector imports no `pos`/`dor.db`/
   `vault`/`lake`; runs with POS absent.
9. **Write side effects** — `calendar create`, `calendar delete` are explicit
   user-intent CLI verbs (per runbook §7); covered by tests; not
   auto-triggered from workflows.

## Implementation plan outline (4 tasks, mirrors #144's shape)

1. **T1** — Create `h2t_ops/core/google_auth.py`; migrate
   `h2t_ops/connectors/gmail/client.py` to consume it (Gmail API
   byte-identical); extend `dev check lazy-registry` to `google*`. **One
   commit.**
2. **T2** — Create `h2t_ops/connectors/calendar/{__init__.py, client.py}` +
   client-level tests (API + typed errors + 4 `_normalize_event` migration).
   **One commit.**
3. **T3** — Create `h2t_ops/connectors/calendar/commands.py`; wire `cli.py`
   (`_MIGRATED` + `ingest calendar` shim); commands-level tests +
   **missing-scopes test case**. **One commit.**
4. **T4** — Closure: full pytest sweep + runbook §4 9-gate self-review +
   installed-CLI live smoke (`calendar list --days 1 --json`, `--days 7
   --json`) + LOCAL evidence preparation. STOP for maintainer approval —
   no posting, no closing. **Zero commits unless drift surfaces.**

## Review gates

- **Spec self-review (inline)** — placeholders / consistency / scope /
  ambiguity (run before this doc is presented).
- **User review of this design doc** — stop before writing-plans.
- **Implementation plan** produced by `writing-plans` at
  `docs/superpowers/plans/2026-05-20-h2t-ops-calendar-parity.md`.
- **Per-task two-stage review** (spec → quality) during subagent-driven
  execution.
- **Final holistic review** before push (mirrors #138 / #144 flow).
