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
| [Connector architecture spec](superpowers/specs/2026-05-18-h2t-connector-architecture-design.md) | Connector standard, identity decision, CLI contract |
| [TZ-0 implementation plan](superpowers/plans/2026-05-18-h2t-connector-architecture-tz0.md) | Core foundation + Notion walking skeleton |

## Waves

| Wave | Scope | Status | Exit Criteria |
| --- | --- | --- | --- |
| TZ-0 | `h2t-ops` foundation + Notion walking skeleton | Branch ready to merge | 63 tests green; no root `h2t` collision; Notion reference connector |
| Runtime blocker | Local `h2t-ops` install + Notion/Gmail E2E smoke | Blocking TZ-1 validation | `h2t-ops` runs locally; Notion read smoke passes; Gmail read smoke passes |
| TZ-1 | Gmail, Calendar, Drive, MeetGeek, Telegram | Planned | All normal connectors migrated to the Notion pattern |
| TZ-2 | Research + URL fetch ladder | Planned | Provider ladder, `core/http.py`, rich envelope, legacy exit-code remap |
| TZ-3 | Skill docs + connector runbook | Planned | `SKILL.md` usage guides and `references/` runbook for adding connectors |
| Follow-up | `h2t-ai` umbrella bridge | Deferred | `h2t <connector>` delegates to `h2t-ops <connector>` without touching DCC behavior |

## Connector Inventory

| Connector | Current Source | Current CLI | Target CLI | Wave | Risk |
| --- | --- | --- | --- | --- | --- |
| notion | `lib/clients/notion.py` | `h2t ingest notion` | `h2t-ops notion ...` | TZ-0 | Low, done in walking skeleton |
| gmail | `lib/clients/gmail.py` | `h2t ingest gmail` | `h2t-ops gmail ...` | TZ-1 | Medium: Google auth and legacy shim |
| calendar | `lib/clients/calendar.py` | `h2t ingest calendar` | `h2t-ops calendar ...` | TZ-1 | Medium: Google auth and date/time output |
| drive | skill exists; CLI gap | none / skill-local | `h2t-ops drive ...` | TZ-1 | Medium: discover exact source and auth shape |
| meetgeek | standalone script / skill-local | none | `h2t-ops meetgeek ...` | TZ-1 | Medium: upload/transcript workflow boundaries |
| telegram | standalone script / skill-local | none | `h2t-ops telegram ...` | TZ-1 | Medium: optional SDK and session secrets |
| research | `exa_search.py` + `fetch_url.py` | standalone scripts | `h2t-ops research ...` including `research fetch --url ...` | TZ-2 | High: legacy exit codes, retry telemetry, provider envelope, URL fetch ladder |

## GitHub Issue Backlog

Use the repo issue title standard: `skills: [M3] Verb noun`. Put `Wave: TZ-N` in the issue body.

### skills: [TZ-0] Merge h2t-ops foundation

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

### skills: [TZ-1] Migrate Calendar connector

**Context:** Calendar shares Google auth concerns with Gmail but has distinct date/time and event
output contracts.

**What:**
- Create `h2t_ops/connectors/calendar/`.
- Re-wrap existing calendar client logic.
- Add CLI commands, tests, and legacy shim.
- Normalize output shapes for events.

**Why:** Calendar is core to daily brief and scheduling skills.

**Definition of Done:**
- CLI supports the existing practical calendar workflows.
- Tests cover event listing, creation path where applicable, and auth/config errors.
- Existing legacy entrypoint still works.

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

### skills: [TZ-3] Add connector development skill runbook

**Context:** New connectors need an agent-facing recipe that lives with the skill, not under
`docs/superpowers`.

**What:**
- Create or update the connector development skill.
- Put the long runbook under that skill's `references/` directory.
- Keep `SKILL.md` lean and point to the reference only when needed.
- Base the runbook on the final Notion skeleton and TZ-1/TZ-2 lessons.

**Why:** Future connector work should be repeatable without re-reading all specs and plans.

**Definition of Done:**
- Skill follows Claude/Codex skill structure.
- `references/h2t-connector-runbook.md` exists.
- Runbook includes file layout, tests, error mapping, output contract, and review checklist.

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
