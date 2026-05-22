# H2T Ops Shippable Handoff

**Date:** 2026-05-22
**Scope:** `h2t-ops` provider connector layer
**Status:** Shippable for POS/provider use

## Verdict

The `h2t-ops` connector layer is complete enough to hand off to POS and use as
the provider access surface.

POS may rely on `h2t-ops <connector> ... --json` commands for provider reads and
explicit provider writes. POS still owns canonical state, interpretation,
journal/task/decision acceptance, and long-term registry semantics.

Nothing currently open in `h2t-skills` blocks connector usage. Remaining work is
profile/context UX, setup polish, research product backlog, creative backlog, or
POS-side coordinator contracts.

## Connector Inventory

| Connector | CLI | Status |
| --- | --- | --- |
| Calendar | `h2t-ops calendar ...` | Shippable; provider feature closure passed CI and live E2E |
| Drive | `h2t-ops drive ...` | Shippable; generic Drive I/O only, `sync-meetings` retired |
| Gmail | `h2t-ops gmail ...` | Shippable |
| MeetGeek | `h2t-ops meetgeek ...` | Shippable; listed-meeting 404 fixed and live E2E passed |
| Notion | `h2t-ops notion ...` | Shippable; embedded DB and workspace graph support merged |
| Telegram | `h2t-ops telegram ...` | Shippable; auth/session and read-only provider commands verified |
| Research | `h2t-ops research ...` | Shippable as a separate research workflow connector |

## Operator Quickstart

Use these as low-risk smoke checks before a POS session.

```powershell
uv.exe run h2t-ops doctor
uv.exe run h2t-ops connectors

uv.exe run h2t-ops calendar calendars --json
uv.exe run h2t-ops calendar list --from 2026-05-22 --to 2026-05-22 --max 10 --json

uv.exe run h2t-ops gmail labels --json
uv.exe run h2t-ops drive folders --max 10 --json

uv.exe run h2t-ops notion search-workspace --object all --limit 5 --json
uv.exe run h2t-ops meetgeek auth-check --json

uv.exe run h2t-ops telegram auth status --json
uv.exe run h2t-ops telegram dialogs --limit 5 --json

uv.exe run h2t-ops research preflight --json
```

Use connector-specific `--help` for exact write commands before mutating
provider state:

```powershell
uv.exe run h2t-ops calendar create --help
uv.exe run h2t-ops calendar update --help
uv.exe run h2t-ops gmail draft --help
uv.exe run h2t-ops notion create --help
uv.exe run h2t-ops drive upload --help
uv.exe run h2t-ops meetgeek submit-url --help
```

## POS Boundary

`h2t-ops` is provider I/O. It must not become POS.

Allowed:

- read provider objects and emit JSON/markdown;
- perform explicit provider writes when the caller asks for them;
- produce provider artifacts or staging outputs;
- expose enough metadata for POS/coordinator provenance.

Not owned by `h2t-ops`:

- POS journal, vault, lake, or SQLite state;
- meeting or communication interpretation;
- accepted tasks, decisions, captures, or follow-ups;
- cross-provider workflow ownership;
- Daily Brief truth/state;
- Notion task creation as an implicit side effect of Telegram/meeting analysis.

Target flow:

```text
h2t-ops provider command
  -> JSON/artifact/proposal
  -> POS/coordinator validation and review
  -> canonical POS state only after acceptance
```

## Evidence

- Connector freeze report: `docs/reports/2026-05-21-h2t-ops-connector-freeze.md`
- Notion completion: PR #158, commit `4c952d1`
- Calendar completion: PR #159, commit `0acb44b`
- MeetGeek 404 fix: issue #156, commit `f363746`
- Calendar UX closure: issue #82, commit `6631f57`
- MeetGeek local recovery: issue #149
- Telegram connector/auth closure: issues #135 and #121

## Skill Layout Recommendation

The current per-connector skills are usable, but not optimal for long-term
context budget.

Recommended next shape:

- keep `h2t-ops:research` separate because it has templates, telemetry,
  traceability rules, and richer workflow references;
- keep `h2t-ops:daily-brief` out of connector consolidation because it is a
  workflow/surface, not a provider connector;
- consolidate non-research connector skills into one connector skill with
  lazy references:
  - Calendar
  - Drive
  - Gmail
  - MeetGeek
  - Notion
  - Telegram

Proposed structure:

```text
plugins/h2t-ops/skills/connectors/SKILL.md
plugins/h2t-ops/skills/connectors/references/calendar.md
plugins/h2t-ops/skills/connectors/references/drive.md
plugins/h2t-ops/skills/connectors/references/gmail.md
plugins/h2t-ops/skills/connectors/references/meetgeek.md
plugins/h2t-ops/skills/connectors/references/notion.md
plugins/h2t-ops/skills/connectors/references/telegram.md
```

This would reduce skill-list entries while keeping detailed instructions
loadable on demand. It is not required for shippability and should be done as a
small follow-up refactor with reload/context verification.
