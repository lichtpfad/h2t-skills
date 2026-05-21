# h2t-ops Connector Freeze Report

Date: 2026-05-22
Issue: #155
Status: draft PR evidence

## Summary

The h2t-ops connector migration is done as a category. The remaining freeze work
is classification and final smoke evidence, not more connector migration.

Fix-now items are resolved:

- #156 MeetGeek listed-meeting 404: fixed in `f363746`, closed with E2E evidence.
- #82 Calendar date-window / max / busy-only gap: fixed in `6631f57`, closed with
  E2E evidence.

Remaining related issues are not connector-freeze blockers unless explicitly
pulled back into scope. They are provider backlog, setup/Mac follow-ups, or repo
hygiene.

## Connector Inventory

| Connector | Active CLI | Credential / state source | Freeze status |
| --- | --- | --- | --- |
| Notion | `h2t-ops notion ...` | `NOTION_API_TOKEN`, `~/.dor/secrets.env`, fallback `~/.config/notion/token` | Frozen; #81/#146 accepted as provider discovery backlog |
| Gmail | `h2t-ops gmail ...` | shared Google OAuth store `~/.config/google-calendar-mcp/`, Gmail fallback token path | Frozen |
| Calendar | `h2t-ops calendar ...` | shared Google OAuth store `~/.config/google-calendar-mcp/` | Frozen; #82 fixed |
| Drive | `h2t-ops drive ...` | shared Google OAuth store `~/.config/google-calendar-mcp/` | Frozen; `sync-meetings` retired in #147 |
| MeetGeek | `h2t-ops meetgeek ...` | `MEETGEEK_API_KEY` via environment / `~/.dor/secrets.env` | Frozen; #156 fixed |
| Telegram | `h2t-ops telegram ...` | `~/.config/telegram/config.json` + Telethon session | Frozen; Mac re-auth/sync remains #13 follow-up |
| Research | `h2t-ops research ...` | `EXA_API_KEY` via env, `H2T_SECRETS_FILE`, `~/.dor/secrets/secrets.env`, or `~/.dor/secrets.env` | Frozen |

## Fixed During Freeze

| Issue | Result | Evidence |
| --- | --- | --- |
| #156 | Fixed and closed | `f363746`; MeetGeek `get` fallback to list row; transcript markdown no longer requires metadata endpoint; live `get` and transcript E2E passed |
| #82 | Fixed and closed | `6631f57`; `calendar list --from/--to`, `--tz`, `--max 250`, `--busy-only`; `tests/connectors` 404 passed; live Calendar E2E passed |

## Accepted Provider / Product Backlog

| Issue | Classification | Rationale |
| --- | --- | --- |
| #145 Calendar provider features | Accepted provider backlog | Meet links, recurrence, patch/reschedule, all-day writes, multi-calendar, reminders, and FreeBusy are provider expansion, not connector migration closure. |
| #81 Notion child_database dump | Accepted Notion discovery/dump backlog | Current connector can read known pages/blocks, query known databases, and find databases on a known page. Recursive workspace dump and automatic embedded DB row extraction are useful, but not required to freeze the connector. |
| #146 Notion workspace discovery / parent graph | Accepted Notion discovery/graph backlog | Workspace graph, parent-chain reconstruction, and teamspace labeling require design and prior-art extraction from `h2t-business`; this is a future read-only provider feature, not a freeze blocker. |

## Setup / Secrets / Mac Follow-ups

| Issue | Classification | Rationale |
| --- | --- | --- |
| #107 unified loader rollout | Setup follow-up | h2t-ops connectors have usable credential paths, but the ecosystem-wide `~/.dor/secrets/` rollout remains broader than connector freeze. |
| #109 MeetGeek secrets migration | Mostly superseded for h2t-ops connector; keep if legacy recovery script still needs migration | `h2t_ops.connectors.meetgeek.client` already calls `load_secrets()`. Legacy `meetgeek_cli.py` / recovery behavior can be handled outside connector freeze. |
| #110 Telegram/Gemini secrets migration | Workflow/legacy follow-up | Telegram connector does not own Gemini analytics. Gemini-based digest/tasks workflows should stay portable workflow scripts or POS/coordinator work. |
| #112 setup secrets wizard | h2t-core setup backlog | Useful for onboarding and Mac setup, but not required to declare connectors frozen. |
| #94 canonical `~/.dor/secrets.env` | Setup convention follow-up | Current connectors already read documented env/secrets paths; full ecosystem unification remains under #107/#112. |
| #13 cross-machine credential sync | Mac/setup follow-up | Google OAuth and Telegram sessions need deliberate per-machine strategy. This is the main future Mac-portability task, not a connector code blocker. |

## Cross-Platform / Repo Hygiene

| Issue | Classification | Rationale |
| --- | --- | --- |
| #53 Mac h2t gather CLI install | h2t-core/Mac setup follow-up | Relevant to Mac onboarding, not h2t-ops connector behavior. |
| #73 legacy h2t hook `.cmd` on macOS/Linux | Stale for h2t-ops freeze | The legacy `h2t` marketplace plugin is retired. Do not block h2t-ops connector freeze on legacy hook cleanup. |
| #85 CI/unit-test hygiene | Repo hygiene follow-up | Important before calling the repo stable, but current connector tests pass locally. |
| #79 machine.yaml overrides | h2t-core / agent-profile follow-up | Per-machine overrides belong with profile/setup work, not connector freeze. |

## Smoke Evidence So Far

Recent verified gates:

```text
uv run h2t-ops dev pytest tests/connectors -q
-> 404 passed

uv run h2t-ops dev check lazy-registry
-> OK
```

Live read-only E2E already verified during fix work:

```text
MeetGeek:
- auth-check OK
- list target id present
- get be7505e5-... --json exit 0
- transcript be7505e5-... --format md exit 0
- transcript be7505e5-... --format json --json exit 0

Calendar:
- calendar --help exit 0
- list --days 1 --max 10 --json OK
- list --from 2026-05-22 --to 2026-05-22 --tz Asia/Jerusalem --max 10 --json OK
- same window with --busy-only OK
- partial --from without --to exits 2
```

Final #155 closure still needs a T4 smoke pass across all connectors.

## Mac Smoke Plan

On a Mac with the plugin installed and credentials configured:

```bash
uv run h2t-ops --help
uv run h2t-ops connectors
uv run h2t-ops dev check lazy-registry
uv run h2t-ops dev pytest tests/connectors -q

uv run h2t-ops notion --help
uv run h2t-ops gmail --help
uv run h2t-ops calendar --help
uv run h2t-ops drive --help
uv run h2t-ops meetgeek --help
uv run h2t-ops telegram --help
uv run h2t-ops research --help
```

Credential expectations:

- Google connectors: create/refresh the Google OAuth store on the Mac.
- Telegram: create a Mac-local Telethon session; do not assume copying the
  Windows session is safe.
- Notion / MeetGeek / Research: environment or `~/.dor/secrets.env` /
  `~/.dor/secrets/secrets.env` as documented.

## Remaining #155 Work

1. Merge this report PR.
2. Run final T4 smoke matrix across all connectors.
3. Update #155 with final status and close it if T4 is green or skipped with
   explicit reasons.
