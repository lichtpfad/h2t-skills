# H2T-OPS Roadmap

**Status:** Active baseline
**Date:** 2026-05-19
**Owner:** h2t-skills

This is the canonical roadmap for moving operational connectors from ad-hoc skill scripts to
the `h2t-ops` distribution and `h2t_ops` Python package.

## North Star

`h2t-ops` owns operational connectors only: Notion, Gmail, Calendar, Drive, MeetGeek,
Telegram, and research. It does not own the root `h2t` command or Python package.
Those remain owned by `h2t-ai` for DCC, registry, graph, vision proxy, and related platform
namespaces.

Skills and agents call `h2t-ops <connector> ...` directly. A future `h2t-ai` umbrella bridge
may delegate `h2t <connector> ...` to `h2t-ops`, but that bridge is not part of the connector
foundation.

## Baseline Decisions

| Decision | Current State |
| --- | --- |
| Distribution name | `h2t-ops` |
| Python package | `h2t_ops` |
| Console script | `h2t-ops` |
| Root `h2t` ownership | `h2t-ai` only |
| Execution contract | `uv run h2t-ops ...` in repo plans; `h2t-ops ...` after tool install |
| Connector standard | `ConnectorSpec`, lazy registry, `client.py` API logic, `commands.py` CLI adapter |
| Output contract | human / `--format md` / `--json` universal envelope |
| Exit codes | 0 ok, 1 provider, 2 usage, 3 config, 4 auth, 5 not found, 6 network |
| Lockfile policy | Commit `uv.lock` for reproducible `uv run` execution |

## Source Documents

| Document | Purpose |
| --- | --- |
| [H2T-OPS testing plan](h2t-ops-testing-plan.md) | Runtime, CLI, and live E2E acceptance gates |
| [Connector architecture spec](superpowers/specs/2026-05-18-h2t-connector-architecture-design.md) | Connector standard, identity decision, CLI contract |
| [TZ-0 implementation plan](superpowers/plans/2026-05-18-h2t-connector-architecture-tz0.md) | Core foundation + Notion walking skeleton |
| [POS operational boundary](../plugins/h2t-ops/references/pos-operational-boundary.md) | Skill-facing rules for respecting POS ADR-0006 without duplicating the ADR |
| [API coverage audit](reports/2026-05-19-h2t-ops-api-coverage-audit.md) | Read-only audit: per-connector legacy parity, provider API feature gaps, POS-boundary risks, and the "do next" sequence |
| [Connector development runbook](../plugins/h2t-ops/references/h2t-connector-runbook.md) | Procedural-index recipe for adding/migrating a connector to the h2t-ops standard |

## Waves

| Wave | Scope | Status | Exit Criteria |
| --- | --- | --- | --- |
| TZ-0 | `h2t-ops` foundation + Notion walking skeleton | Done | Foundation merged; no root `h2t` collision; Notion reference connector |
| Runtime blocker | Local `h2t-ops` install + Notion/Gmail E2E smoke | Done | Canonical installed CLI smoke passed for Notion and Gmail |
| TZ-1 | Gmail, Calendar, Drive, MeetGeek, Telegram | In progress | Gmail done; remaining normal connectors migrated to the Notion/Gmail pattern |
| TZ-2 | Research + URL fetch ladder | Planned | Provider ladder, `core/http.py`, rich envelope, legacy exit-code remap |
| TZ-3 | Skill docs + connector runbook | Planned / pull forward | `SKILL.md` usage guides and `references/` runbook for adding connectors |
| Follow-up | `h2t-ai` umbrella bridge | Deferred | `h2t <connector>` delegates to `h2t-ops <connector>` without touching DCC behavior |

## Connector Inventory

| Connector | Current Source | Current CLI | Target CLI | Wave | Risk |
| --- | --- | --- | --- | --- | --- |
| notion | `lib/clients/notion.py` | `h2t ingest notion` legacy shim | `h2t-ops notion ...` | TZ-0 | Done (patch debt: `secrets.env` regression, `video` block drop, missing `find-project-tasks`) |
| gmail | `lib/clients/gmail.py` | `h2t ingest gmail` legacy shim | `h2t-ops gmail ...` | TZ-1 | Done |
| calendar | `lib/clients/calendar.py` | `h2t ingest calendar` | `h2t-ops calendar ...` | TZ-1 | Medium: parity vs provider-features split; shared Google auth helper is a prerequisite |
| drive | skill exists; CLI gap | none / skill-local | `h2t-ops drive ...` | TZ-1 | Medium: discover exact source and auth shape |
| meetgeek | standalone script / skill-local | none | `h2t-ops meetgeek ...` | TZ-1 | Medium: upload/transcript workflow boundaries |
| telegram | standalone script / skill-local | none | `h2t-ops telegram ...` | TZ-1 | Medium: optional SDK and session secrets |
| research | `exa_search.py` + `fetch_url.py` | standalone scripts | `h2t-ops research ...` including `research fetch --url ...` | TZ-2 | High: legacy exit codes, retry telemetry, provider envelope, URL fetch ladder |

## GitHub Issue Backlog

Use the repo issue title standard: `skills: [M3] Verb noun`. Put `Wave: TZ-N` in the issue body.

### Current Status

- Closed: #131 Gmail connector, #139 local runtime smoke, #141 UTF-8 core output.
- Open: #132 Calendar, #133 Drive, #134 MeetGeek, #135 Telegram, #136 research,
  #137 research URL fetch ladder, #138 connector development runbook,
  #143 plugin bump script UTF-8.
- New from the API coverage audit (2026-05-19): a Notion patch-debt issue
  (`skills: [M3] Patch Notion connector coverage gaps`) and a Calendar
  provider-features follow-up issue, kept separate from #132 parity scope.
- Recommended next sequence: #138 runbook baseline first (now carrying the
  API coverage checklist), then #132 Calendar **parity** as the first
  runbook-driven migration, with a shared Google auth helper as its
  prerequisite.

### Current Execution Sequence

1. **#138 Connector development runbook.** Write the procedure before adding more
   connectors. The runbook must use Notion and Gmail as reference implementations
   and must include POS-boundary and distribution-independence checks, plus the
   API coverage checklist (see the #138 backlog section) as a required review
   gate for every connector PR.
2. **Shared Google auth helper (prerequisite for #132).** Add
   `resolve_google_credentials()` / token-refresh reuse to `core/secrets.py`
   before or inside #132, so Calendar/Drive/Gmail stop duplicating inlined OAuth
   resolution. Without it, Drive will duplicate the same auth code again.
3. **Extend `dev check lazy-registry`.** Before Calendar/Drive/Telegram land,
   extend the lazy-import guard from `notion_client` + `httpx` to `google*`,
   `telethon`, and `exa`; otherwise `h2t-ops --help` / `connectors` risk
   importing heavy SDKs. Treat as a mandatory gate in the runbook.
4. **#132 Calendar — parity migration only.** First connector built by following
   the runbook (lowest risk: shares Google OAuth with Gmail, feeds Daily Brief).
   Scope is parity with the legacy client only (list/search/get/create/delete,
   shared Google auth, typed errors, tests, legacy shim). Provider-feature
   expansion (Meet links, recurrence, patch/reschedule, all-day, multi-calendar,
   reminders/freebusy) is a **separate follow-up issue**, not #132, unless the
   architect explicitly approves widening #132.
5. **Notion patch debt.** Fix the audit-identified regressions in the already
   migrated Notion connector: missing `load_dotenv(~/.dor/secrets.env)`
   (`secrets.env` regression), `video` block silent data loss, and missing
   `find-project-tasks`. Tracked as a dedicated patch issue; its sequence
   relative to #132 is the architect's call.
6. **Inventory gate for Drive, MeetGeek, Telegram.** Before implementation,
   document exact skill-local CLI surfaces, write/file side effects, optional
   SDKs, and POS-boundary risks. These connectors mix pure-API reads with
   workflow/storage side effects (MeetGeek lake writes — CRITICAL; Telegram
   DOR + Notion writes — HIGH; Drive `sync-meetings` DOR writes — HIGH). The
   connector scope is pure-API reads only; side-effecting subcommands go to a
   coordinator / POS-owned layer, not the connector. De-duplicate the Drive
   client embedded in `meetgeek_cli.py`. Only then migrate each connector.
7. **#136/#137 Research wave.** Keep research and URL fetch ladder in TZ-2.
   They are provider/strategy connectors with richer telemetry and legacy exit
   code remapping, not normal TZ-1 connectors.
8. **Daily Brief update.** After Calendar parity is migrated, update Daily Brief
   to use `h2t-ops calendar/gmail/notion` reads. Daily Brief remains a synthesis
   workflow, not a POS journal writer.

### Distribution Independence

`h2t-ops` skills must remain usable without Personal OS installed. POS boundary
rules define what skills must not mutate, but POS is not a runtime dependency for
read-only connector usage.

- External reads must work through `h2t-ops` plus provider credentials.
- POS CLI/API calls are allowed only for optional capture/decision/task/lesson
  writes when POS is present.
- If POS journal commands are unavailable, skills emit structured proposed
  captures instead of failing or mutating local stores.
- Connector runbook and connector PRs must include this check explicitly.

### skills: [TZ-0] Merge h2t-ops foundation

**Status:** Done.

**Context:** The connector foundation is implemented on `worktree-feat+tz0-connector-skeleton`
with the corrected `h2t-ops` / `h2t_ops` identity.

**What:**
- Push the branch and open a PR into `main`.
- Keep `uv.lock` committed.
- Verify CI and PR review.

**Why:** TZ-1 should build on a merged baseline, not a parked worktree branch.

**Definition of Done:**
- PR merged into `main`.
- `h2t-ai` root `h2t` ownership remains untouched.
- `uv run h2t-ops dev pytest tests/core tests/connectors -v` is green.

### skills: [M3] Fix local h2t-ops runtime smoke

**Status:** Done (#139).

**Context:** TZ-0 passed CI and mocked connector tests, but local runtime adoption was not proven.
On the current machine, `h2t-ops` is not on PATH, `uv` is not on PATH, the existing root `h2t`
trampoline fails, and one discovered worktree `.venv` points at a missing Python. Direct Notion
REST with the stored token works, so the blocker is the local CLI/runtime layer, not Notion access.

**What:**
- Repair or install the local `h2t-ops` runtime.
- Define the canonical setup/repair path (`uv tool install`, `/h2t-core:setup`, or equivalent).
- Run read-only live E2E smoke for Notion through `h2t-ops`, not direct REST.
- Run read-only live E2E smoke for Gmail through `h2t-ops` before accepting the Gmail connector.
- Capture exact commands and results in the issue.

**Why:** Connector migrations are not complete if they only pass mocked tests and CI. Agents need
the installed local CLI to work on the real machine.

**Definition of Done:**
- `uv --version` or the chosen supported installer path works.
- `h2t-ops --version` exits 0.
- `h2t-ops doctor` exits 0 and reports connectors/secrets without crashing.
- `h2t-ops notion get 10adbc1e61d04d13aa6f17210b77e0d3 --json` exits 0.
- `h2t-ops notion blocks 10adbc1e61d04d13aa6f17210b77e0d3 --limit 3 --json` exits 0.
- A Gmail read-only smoke command exits 0 through `h2t-ops gmail ...`.
- GitHub issue #131 records the Gmail smoke result before merge.

### skills: [TZ-1] Migrate Gmail connector

**Status:** Done (#131).

**Context:** Gmail currently works through legacy skill/client code and must move to the
connector standard without breaking existing `h2t ingest gmail` usage.

**What:**
- Create `h2t_ops/connectors/gmail/`.
- Wrap existing Gmail API logic in `client.py`.
- Add `commands.py`, `CONNECTOR`, tests, and legacy shim.
- Preserve config/auth behavior with typed `ConfigError` / `AuthError`.

**Why:** Gmail is a normal connector and should prove the second migration after Notion.

**Definition of Done:**
- API tests cover happy path and typed error mapping.
- CLI tests cover `--json`, human output, help, and shim behavior.
- Lazy registry test remains green.

### skills: [M3] Patch Notion connector coverage gaps

**Status:** Backlog. Created from the API coverage audit (2026-05-19 §3 "Notion — partial").

**Context:** Notion migrated in TZ-0, but the audit found three concrete gaps versus the legacy
client/skill that make the connector partial, not full.

**What:**
- **`secrets.env` regression** — the connector's `resolve_notion_token()` reads only
  `os.environ` → `~/.config/notion/token`; the legacy `lib/clients/notion.py` did
  `load_dotenv(~/.dor/secrets.env)` at import. If the token lives only in `secrets.env` and
  `load_secrets()` is not called upstream, the connector raises `ConfigError` where the legacy
  client worked. Restore equivalent secrets resolution.
- **`video` block silent data loss** — `video` blocks are rendered as a link in the skill
  (`notion_cli.py`) but return `""` in the connector (`client.py`), dropping data silently
  (also present in the legacy lib client). Render `video` instead of dropping it.
- **Missing `find-project-tasks`** — present in `lib/cli/main.py` and the legacy Notion skill
  script, dropped in `h2t_ops`. Restore the CLI command (relation-filter query).

**Why:** A migrated connector rated "partial" undermines the parity guarantee the runbook will
enforce; these are regressions, not new features.

**Definition of Done:**
- Token resolves from `~/.dor/secrets.env` parity with the legacy client (typed `ConfigError`
  only when genuinely absent).
- `video` blocks are rendered (no silent `""`), with a test.
- `find-project-tasks` CLI command restored with a test.
- No connector code outside Notion is touched; POS boundary unaffected.

### skills: [M3] Migrate Calendar connector (parity) — #132

**Status:** Next after #138 runbook baseline. **Scope: parity only.**

**Context:** Calendar shares Google auth concerns with Gmail but has distinct date/time and event
output contracts. The API coverage audit (2026-05-19 §3 "Calendar — #132 exact delta") shows the
legacy client is primary-calendar-only with no Meet/recurrence/patch/all-day/multi-calendar. #132
must not silently become a thin re-wrap that also drops the provider-feature gap on the floor —
the parity migration and the provider-feature expansion are explicitly separated below.

**Prerequisite (shared Google auth helper):** Before or inside #132, add a shared
`resolve_google_credentials()` / token-refresh reuse helper to `core/secrets.py`. Gmail's OAuth
resolution is currently inlined in `gmail/client.py`; without the shared helper, Calendar (and
later Drive) duplicate it. This prerequisite is part of #132's required subtasks.

**What (parity scope only):**
- Create `h2t_ops/connectors/calendar/` (template: `h2t_ops/connectors/gmail/`).
- Re-wrap the existing legacy `lib/clients/calendar.py` logic: `list / search / get / create /
  delete`, primary calendar only — byte-equivalent behavior, no new provider features.
- Use the shared Google auth helper (path `~/.config/google-calendar-mcp/tokens.json`, shared
  with Gmail — no separate bootstrap).
- Typed errors: missing libs/creds → `ConfigError` (browser never launched); refresh failure →
  `AuthError`; HTTP → `_map_http_error` mirroring `gmail/client.py`.
- Add `commands.py`, `CONNECTOR`, tests, and legacy shim; normalize event output shapes.

**Why:** Calendar is core to Daily Brief and scheduling skills, and is the lowest-risk first
runbook-driven migration.

**Definition of Done:**
- Parity CLI: `calendar list/search/get/create/delete` with `--json` / `--format`.
- Tests cover event listing, the create path, auth/config errors (no browser launch), and the
  lazy-import guard; migrate the 4 `_normalize_event` tests from `tests/clients/test_calendar.py`.
- Existing legacy entrypoint still works.
- Shared Google auth helper landed and used (no duplicated inline OAuth).

**Audit-trail note:** The API coverage audit §6 recommended folding the provider features into
#132 ("not a thin re-wrap"). Architect direction is to keep #132 **parity-only** and track the
provider features as the separate follow-up below. Re-open this only if the architect explicitly
widens #132.

### skills: [M3] Calendar provider features follow-up

**Status:** Backlog (separate from #132). Created from the API coverage audit (§6, §"Highest-impact
missing features").

**Context:** The legacy Calendar client — and therefore the #132 parity connector — exposes only
primary-calendar single timed events. The Google Calendar API v3 supports substantially more, and
this gap is where most "the CLI can't do that" friction will come from.

**What (each may be its own issue/PR; do not fold into #132 without explicit approval):**
- Google Meet links (`conferenceData.createRequest`, `conferenceDataVersion`).
- Recurring / serial events (`recurrence: ["RRULE:..."]`).
- Patch / reschedule (`events.patch`) — currently only create + delete exist.
- All-day events (date vs dateTime).
- Calendar-id / multi-calendar (currently `calendarId="primary"` hardcoded) + `calendarList`.
- Reminders / notification overrides and FreeBusy query.

**Why:** These are the highest-impact missing capabilities for real scheduling use; they need
explicit acceptance items rather than being lost between parity and "done".

**Definition of Done:**
- Each provider feature has a typed-error path, tests, and `--json` output.
- The runbook's provider-API-gap checklist item is satisfied for Calendar.

### skills: [TZ-1] Migrate Drive connector

**Context:** Drive has a skill surface but is not represented cleanly in the current CLI inventory.

**What:**
- Locate the canonical Drive code path.
- Define the minimal TZ-1 command surface.
- Create `h2t_ops/connectors/drive/` with client, commands, `CONNECTOR`, and tests.
- Document any intentionally deferred Drive workflows.

**Why:** Drive is a dependency for transcript and MeetGeek workflows, so it needs a stable agent
CLI surface.

**Definition of Done:**
- Source-of-truth code path is documented.
- Minimal CLI works through `h2t-ops drive ...`.
- Tests cover auth/config and output shape.

### skills: [TZ-1] Migrate MeetGeek connector

**Context:** MeetGeek is currently script/skill-local and needs a connector boundary before it can
be used reliably by agents and workflows.

**What:**
- Locate the standalone MeetGeek implementation.
- Define upload/transcript command boundaries.
- Create `h2t_ops/connectors/meetgeek/` with tests.
- Add SKILL.md usage updates where needed.

**Why:** MeetGeek workflows should not depend on script discovery or local path assumptions.

**Definition of Done:**
- Minimal useful MeetGeek CLI exists.
- Tests cover command contract and typed failures.
- Secrets and file-path behavior are explicit.

### skills: [TZ-1] Migrate Telegram connector

**Context:** Telegram likely needs optional SDK/session handling and must not break registry
laziness.

**What:**
- Locate the current Telegram script/skill code.
- Create `h2t_ops/connectors/telegram/`.
- Keep optional SDK imports lazy and convert missing dependencies to `ConfigError`.
- Add CLI and tests.

**Why:** Telegram should become a first-class connector without forcing heavy dependencies into
registry/help calls.

**Definition of Done:**
- `h2t-ops connectors` and `--help` do not import Telegram SDKs.
- Missing SDK/session cases produce typed errors.
- CLI tests cover output and exit codes.

### skills: [TZ-2] Migrate research connector

**Context:** `exa_search.py` has legacy exit codes and a richer provider-status envelope. It should
not be mixed into the normal TZ-1 connector wave.

**What:**
- Split research into connector modules and providers where needed.
- Add `core/http.py` if retry/backoff becomes shared.
- Remap legacy exit codes to the canonical table.
- Preserve rich provider telemetry under `result`/`meta`.

**Why:** Research is high-value but architecturally thicker than Gmail/Notion-style connectors.

**Definition of Done:**
- Legacy research skill docs reflect the new error table.
- Provider envelope tests cover OK / DEGRADED / FAILED.
- Existing research workflows still have a documented migration path.

### skills: [M3] Integrate URL fetch ladder into research connector

**Context:** `fetch_url.py` is not a standalone business connector. It is a research capability:
after `exa_search.py` finds a URL, the fetch ladder retrieves the full page content with
machine-readable status, content gate detection, provider telemetry, and fallbacks.

**What:**
- Move URL fetching into `h2t_ops/connectors/research/`, not a top-level `fetch` connector.
- Expose it as `h2t-ops research fetch --url ...` if the CLI surface is needed.
- Model the provider ladder explicitly (`direct`, `jina`, future browser providers).
- Reuse or introduce shared HTTP retry/backoff only when needed.
- Add CLI and tests for direct/Jina/fallback behavior.

**Why:** URL fetching should remain part of research, while becoming reproducible and testable
instead of a standalone script discovered through plugin paths.

**Definition of Done:**
- Tests cover provider fallback order.
- `--json` exposes enough metadata for agents to reason about degraded results.
- Network and provider failures map to canonical exit codes.

### skills: [M3] Add connector development skill runbook — #138

**Status:** Next (must land before any further connector migration).

**Context:** New connectors need an agent-facing recipe that lives with the skill, not under
`docs/superpowers`. The API coverage audit (2026-05-19) showed that without an explicit checklist,
a migration can silently regress (Notion `secrets.env` / `video` / `find-project-tasks`) or ship a
thin re-wrap that ignores the provider-API gap.

**What:**
- Create or update the connector development skill.
- Put the long runbook at `plugins/h2t-ops/references/h2t-connector-runbook.md`
  (plugin-level references; no new skill scaffold).
- Keep `SKILL.md` lean and point to the reference only when needed.
- Base the runbook on the final Notion skeleton and TZ-1/TZ-2 lessons.
- Embed the **API coverage checklist** (below) as a mandatory per-connector review gate.

**API coverage checklist (required gate for every connector PR):**

1. **Legacy parity** — every legacy `lib/`/skill-script method and subcommand is matched
   1:1; any intentionally dropped capability is documented, not silent.
2. **Provider API gaps** — the connector is checked against the full documented provider
   API; missing high-value capabilities are filed as explicit follow-up issues, not lost.
3. **Auth/secrets** — credential resolution goes through the shared helper(s)
   (`resolve_*_credentials()`); no inlined per-connector OAuth/dotenv duplication; no
   `secrets.env` regression vs the legacy client.
4. **Lazy imports** — heavy SDKs import lazily; `dev check lazy-registry` covers this
   connector's SDK; `h2t-ops --help` / `connectors` never import it.
5. **Tests** — API happy path + typed error mapping + CLI contract (`--json`, human,
   help, shim) + lazy-registry guard; legacy normalize tests migrated.
6. **Live smoke** — read-only live E2E through the installed CLI, evidence recorded in
   the issue (per the testing plan).
7. **POS boundary** — no connector writes `~/.dor/pos.db` / `dor.db` / vault / lake;
   side-effecting subcommands are excluded from the connector scope.
8. **Distribution-without-POS** — the connector imports no `pos`/`dor.db`/`vault`/`lake`
   and does not default-write into `~/.dor/`; it works with POS absent.
9. **Write side effects** — mutating operations (send/label/create/delete/upload/archive)
   are enumerated; until POS journal commands exist they emit structured proposed
   captures, never silent store mutation.

**Why:** Future connector work should be repeatable without re-reading all specs and plans,
and must not regress parity or boundary guarantees.

**Definition of Done:**
- Skill follows Claude/Codex skill structure.
- `plugins/h2t-ops/references/h2t-connector-runbook.md` exists (plugin-level
  references, beside `pos-operational-boundary.md` — no separate skill is
  scaffolded; this satisfies the original "references/h2t-connector-runbook.md"
  intent).
- Runbook includes file layout, tests, error mapping, output contract, review checklist,
  and the 9-item API coverage checklist above as a required gate.

### ai: Add h2t-ops umbrella bridge

**Context:** `h2t-ai` owns root `h2t`. Internal UX may later want `h2t notion ...` while keeping
`h2t-ops` as the connector distribution.

**What:**
- Add a delegating subcommand in `h2t-ai`, not in `h2t-skills`.
- Delegate selected connector namespaces to `h2t-ops`.
- Preserve existing `td`, `registry`, `graph`, `vision`, `transcribe`, `enrich`, and `eval`
behavior.

**Why:** This restores one-command internal ergonomics without recreating the package/script
collision.

**Definition of Done:**
- `h2t notion --help` delegates to `h2t-ops notion --help`.
- Existing `h2t td`, `h2t registry`, and `h2t vision` tests/smokes stay green.
- Missing `h2t-ops` produces clear setup guidance.

## Operating Rules

- Keep TZ-1 normal connectors separate from TZ-2 thick provider connectors.
- Do not claim `h2t` package or script in `h2t-skills`.
- Preserve legacy entrypoints until their users are migrated.
- Every connector PR must include API tests, CLI contract tests, and a lazy-registry check.
- SKILL.md is a usage guide; long contributor instructions belong in `references/`.
- Skills and agents must follow the POS operational boundary: h2t-ops owns connector
  runtime; POS owns journal, sync state, interpretation, privacy/routing, and daily
  loop. Skills must not write directly to `~/.dor/pos.db`, the existing `dor.db`,
  vault, or lake.
- Until POS journal commands exist, skills should emit structured proposed captures
  instead of mutating stores.
- POS is not required for read-only connector usage. h2t-ops skills must degrade
  gracefully when POS journal commands are unavailable.
