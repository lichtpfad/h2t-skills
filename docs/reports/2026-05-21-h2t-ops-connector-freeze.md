# h2t-ops Connector Freeze Report

Date: 2026-05-22
Issue: #155
Status: final local evidence

## Summary

The h2t-ops connector migration is done as a category. The remaining related
work is classified as provider backlog, setup/Mac follow-up, or repo hygiene,
not more connector migration.

Fix-now items are resolved:

- #156 MeetGeek listed-meeting 404: fixed in `f363746`, closed with E2E evidence.
- #82 Calendar date-window / max / busy-only gap: fixed in `6631f57`, closed with
  E2E evidence.
- Top-level `h2t-ops --help` regression discovered during final T4 smoke: fixed
  in the final #155 closure commit with regression coverage.

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
| #155 T4 help regression | Fixed | `h2t-ops --help` now renders the `h2t-ops` parser instead of falling through to legacy `h2t`; `tests/cli/test_h2t_ops_cli.py` added |

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

## Final T4 Smoke Evidence

Date: 2026-05-22

Local gates:

```text
uv.exe run h2t-ops --help
-> exit 0; renders h2t-ops parser

uv.exe run h2t-ops connectors
-> exit 0; lists calendar, drive, gmail, meetgeek, notion, research, telegram

uv.exe run h2t-ops dev check lazy-registry
-> OK lazy-registry

uv.exe run h2t-ops dev pytest tests/connectors tests/cli/test_h2t_ops_cli.py -q
-> 406 passed
```

Provider help gates:

```text
notion --help      -> exit 0
gmail --help       -> exit 0
calendar --help    -> exit 0
drive --help       -> exit 0
meetgeek --help    -> exit 0
telegram --help    -> exit 0
research --help    -> exit 0
```

Live/read-only smoke matrix:

```text
notion blocks 10adbc1e61d04d13aa6f17210b77e0d3 --limit 1 --json -> PASS
gmail list --max 1 --json                                           -> PASS
calendar list --days 1 --max 10 --json                              -> PASS
drive list --max 1 --json                                           -> PASS
meetgeek auth-check --json                                          -> PASS
telegram auth status --json                                         -> PASS
telegram dialogs --limit 5 --json                                   -> PASS
research fetch --url https://www.iana.org/domains/reserved \
  --provider direct --timeout-ms 30000 --min-body-chars 20 --json    -> PASS
research preflight --json                                           -> PASS
```

Note: `research fetch --url https://example.com --provider direct` timed out in
this environment. The Research connector itself passed against IANA and Exa
preflight, so the `example.com` timeout is treated as endpoint/network flake,
not a connector freeze blocker.

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

## #155 Closure Disposition

#155 can be closed after the final closure commit is pushed and this evidence is
posted to the issue.
