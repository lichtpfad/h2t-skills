---
title: "h2t-ops Connector Freeze + Mac Portability Gate — Design"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-05-21"
milestone: ""
---
# h2t-ops Connector Freeze + Mac Portability Gate — Design

Status: active execution
Date: 2026-05-21
Issue: #155
Related: #82, #145, #156, #81, #146, #107, #109, #110, #112, #94, #13, #53, #73, #85, #79

## Goal

Declare the h2t-ops connector migration finished as a category.

This is not a request to implement every possible provider feature. It is a
freeze gate: every known connector concern must be either fixed now, accepted as
provider/product backlog, or moved into a Mac/setup portability follow-up with
clear ownership.

After this gate, the repo can move to `h2t-core:agent-profile` and broader
runtime hygiene without repeatedly reopening connector migration work.

## Current State

The core connectors exist and are usable through `h2t-ops`:

- `notion`;
- `gmail`;
- `calendar`;
- `drive`;
- `meetgeek`;
- `telegram`;
- `research`.

The legacy `h2t` marketplace plugin is retired (#151). Drive `sync-meetings` is
retired from Drive (#147). Telegram session-rot was fixed by #135/#121.
MeetGeek listed-meeting 404 was fixed and closed in #156.

The remaining problem is closure quality: some known gaps are still mixed
together with backlog, setup, Mac portability, and provider feature requests.

## Definition: Migrated vs Frozen

`Migrated` means a connector has a modern h2t-ops CLI surface, tests, lazy
imports, and typed errors.

`Frozen` means:

1. known operational bugs are fixed or tracked as explicit follow-ups;
2. common user-facing gaps are either fixed or accepted as product backlog;
3. read-only smoke commands are documented for all connectors;
4. credential/setup assumptions are documented enough for a later Mac port;
5. no connector silently depends on POS, DOR state, or legacy `h2t`.

## Fix-Now Candidates

### Resolved: MeetGeek listed-meeting 404 (#156)

Live usage surfaced repeated 404s:

- `h2t-ops meetgeek list` shows a meeting;
- `h2t-ops meetgeek transcript <id>` returns 404;
- `h2t-ops meetgeek get <id>` also needs verification for the same listed id.

This was treated as a legacy-parity regression rather than provider behavior by
default, because the legacy MeetGeek skill path worked reliably for transcript
fetches.

Resolution:

- Markdown artifact commands no longer require `/v1/meeting/{id}` metadata to
  succeed; if metadata 404s, they format with the known `meeting_id`, matching
  legacy behavior.
- `meetgeek get` falls back from singular `/v1/meeting/{id}` to the
  `/v1/meetings` list row when the listed meeting exists but the metadata
  endpoint returns 404.

Fixed in `f363746`; #156 is closed with E2E evidence.

If this class of bug returns, a listed item that cannot be fetched is either:

- wrong endpoint shape;
- wrong id field selected from the list response;
- transcript not ready yet;
- provider retention/permission limitation;
- or acceptable provider behavior with a poor error message.

The freeze pass should preserve this regression coverage, not reopen #156
unless a new failing id contradicts the fixed behavior.

### Resolved Locally: Calendar UX gap (#82)

Calendar parity is complete (#132), but daily use still needs a stronger query
surface:

- explicit date window: `--from YYYY-MM-DD --to YYYY-MM-DD`;
- configurable limit with a safe default;
- `--busy-only` / transparency filtering.

Date-window contract:

- `--from` is inclusive at local 00:00:00 in the query timezone.
- `--to` is inclusive as a user-facing date and converted to an exclusive
  next-day 00:00:00 API bound.
- Query timezone is explicit: `--tz`, then `H2T_CALENDAR_TZ`, then
  `Asia/Jerusalem` as the fallback matching existing create-event defaults.
- Boundary tests must cover timed events, all-day events, and events at the
  start/end of the window.

Busy-only contract:

- Filter raw Google Calendar events before normalization.
- Missing `transparency` means busy.
- `transparency == "transparent"` is excluded when `--busy-only` is set.

Resolution:

- Implemented in `6631f57`.
- `calendar list` now supports `--from YYYY-MM-DD --to YYYY-MM-DD`, `--tz`,
  `--max`, and `--busy-only`.
- `--to` is user-facing inclusive and converted to an exclusive next-day API
  bound.
- `--max` defaults to `250`.
- `tzdata` is a project dependency so IANA timezones such as
  `Asia/Jerusalem` work on Windows as well as macOS/Linux.
- E2E passed for `--days`, explicit date window, `--busy-only`, and partial
  window usage-error behavior.

#82 was pushed and closed with E2E evidence.

The broader #145 feature list remains provider backlog unless explicitly pulled
into this freeze pass:

- Meet links;
- recurrence;
- patch/reschedule;
- all-day create/update expansion;
- multi-calendar;
- reminders;
- FreeBusy.
- `free-time` scheduling helper.

## Classify, Do Not Necessarily Implement

### Notion gaps (#81, #146)

Known Notion follow-ups:

- child_database / embedded database traversal (#81);
- workspace discovery and parent graph (#146).

These are not automatically freeze blockers. The freeze pass decides whether
they are needed for "connector done" or accepted provider backlog.

### Secrets and setup (#107, #109, #110, #112, #94, #13)

The freeze requirement is not a full setup wizard. It is narrower:

- each connector has a documented credential source;
- credentials are resolved through intended shared helpers;
- Mac transfer/setup is credible enough to plan;
- no connector requires undocumented local Windows-only state.

Cross-machine token sync (#13) can remain future work if documented.

### Cross-platform / Mac readiness (#53, #73, #85, #79)

The gate is "Mac-portable enough to plan a port", not "fully tested on Mac in
this pass".

Minimum:

- setup path is expressible through `uv`;
- normal connector commands do not require Windows-only shell syntax;
- tests pass on the current platform and are CI-friendly;
- Mac smoke commands are documented;
- known platform blockers are filed instead of hidden.

## Non-Goals

- Do not revive the legacy `h2t` marketplace plugin.
- Do not implement POS intake, journal writes, transcript fusion, or task
  acceptance.
- Do not implement every Calendar/Notion provider feature.
- Do not fold Telegram/MeetGeek/Drive workflows back into provider connectors.
- Do not implement `h2t-core:agent-profile` in this issue.
- Do not solve creative/arch/edu/dcc roadmap items.

## Required Outputs

### 1. Freeze report

Create a short report:

```text
docs/reports/2026-05-21-h2t-ops-connector-freeze.md
```

It should record:

- connector inventory;
- fix-now decisions;
- accepted backlog decisions;
- Mac portability notes;
- final smoke matrix;
- issue closure/comment links.

### 2. Final smoke matrix

Document read-only commands for each connector:

```bash
h2t-ops connectors
h2t-ops notion --help
h2t-ops gmail --help
h2t-ops calendar --help
h2t-ops drive --help
h2t-ops meetgeek --help
h2t-ops telegram --help
h2t-ops research --help
```

Live provider smokes should be run when credentials are available. If a provider
is unavailable, record the reason and do not fake success.

### 3. Issue disposition

At the end of the freeze:

- close fixed issues with evidence;
- comment on accepted-backlog issues;
- keep true follow-ups open and out of the critical path;
- update #155 with the final status.

## Acceptance

The freeze is accepted when:

1. #156 remains fixed with regression tests and live-smoke evidence.
2. #82 remains fixed in `6631f57`, with push/issue-close evidence recorded.
3. #81/#146 are classified as fix-now or accepted backlog.
4. secrets/setup issues are classified for Mac portability.
5. a Mac smoke plan exists.
6. tests for changed connectors pass.
7. `uv run h2t-ops dev check lazy-registry` passes.
8. roadmap points to no active connector migration work after #155.
