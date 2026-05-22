# H2T-SKILLS Roadmap

**Status:** Active closure roadmap
**Date:** 2026-05-22
**Owner:** h2t-skills
**Milestone tag:** `milestone/legacy-h2t-retired-2026-05-21`

This roadmap tracks the remaining work needed to move `h2t-skills` from active
connector migration into a cleaner maintenance mode. The immediate preference is
to fully freeze connector work first, then move to agent profiles and Mac
portability with fewer moving parts.

## North Star

`h2t-ops` owns operational provider connectors only: Notion, Gmail, Calendar,
Drive, MeetGeek, Telegram, and Research.

It does not own:

- POS journal / vault / lake writes;
- meeting or communication interpretation;
- task/decision acceptance;
- cross-provider coordinator workflows;
- the root `h2t` package or DCC runtime.

Skills and agents should call `h2t-ops <connector> ...` directly. A future
`h2t-ai` umbrella bridge may delegate `h2t <connector> ...` to `h2t-ops`, but
that bridge belongs outside this repo.

## Current State

### Completed Connector Migration

The M3 connector migration is complete.

| Area | Issue(s) | State |
| --- | --- | --- |
| Foundation / Notion skeleton | TZ-0, #144 | Done |
| Gmail | #131 | Done |
| Calendar parity | #132 | Done |
| Calendar UX closure | #82 | Done; fixed in `6631f57`, pushed and closed with E2E evidence |
| Drive parity | #133 | Done |
| MeetGeek API connector | #134 | Done |
| Telegram connector | #135, #121 | Done; #121 closed as fixed by typed `SESSION_INCOMPATIBLE` handling |
| Research connector | #136 | Done |
| URL fetch ladder | #137, #100, #103, #114 | Done |
| Connector runbook | #138 | Done |
| Runtime smoke / UTF-8 fixes | #139, #141, #143 | Done |
| MeetGeek local recovery | #149 | Done; kept as skill-layer recovery, not connector runtime |
| MeetGeek listed-meeting 404 | #156 | Done; fixed in `f363746`, live `get` and `transcript` E2E passed |
| Drive `sync-meetings` | #147 | Retired from Drive; semantics moved to future POS/coordinator backlog |
| Duplicate skill entries | #150, #152, #153 cleanup commits | Done for split plugins |
| Legacy `h2t` marketplace plugin | #151 | Retired; split plugins are active entrypoints |

### Active Closure Streams

The migration and connector freeze are done. Only `h2t-core:agent-profile` is
on the active critical path. The concrete #148 security/dev hygiene task and #85
CI/unit-test hygiene task are closed. Remaining hygiene is routine maintenance,
not a closure blocker and not connector or product migration.

| Priority | Issue(s) | Work | Classification |
| --- | --- | --- | --- |
| 1 | #153 | `h2t-core:agent-profile` | Active critical path |
| 2 | #148, #85 | Security/dev hygiene and CI/unit-test hygiene | Done; no active closure blocker |
| 3 | #13, #94, #107, #109, #110, #73, #79, #53 | Platform portability / credential policy | Done or consolidated into policy; routine maintenance only |
| 4 | #112 | Setup wizard backlog | Future onboarding UX, separate from closure |
| 5 | #81, #146, #145 | Provider feature backlog | Product/provider backlog; pull only when explicitly scoped |

## Critical Path Details

### Completed: Connector Freeze + Mac Portability Gate (#155)

Goal: finish connectors as a category before moving to profile/runtime work.

This does not mean implementing every provider feature. It means every known
connector issue is intentionally classified:

- fix now;
- accepted provider/product backlog;
- Mac/setup portability follow-up;
- stale/superseded and closed with evidence.

Definition of done:

- #82/#145 Calendar are resolved into a fix-now scope plus provider backlog;
- #81/#146 Notion are resolved into fix-now or accepted backlog;
- #107/#109/#110/#112/#94/#13 secrets/setup issues are consolidated enough that
  connector credentials can be ported to Mac deliberately;
- #53/#73/#85/#79 cross-platform issues are triaged against h2t-ops connector usage;
- final read-only smoke matrix exists for all seven connectors;
- roadmap no longer lists connector migration as active work.

Status: done. Final T4 smoke passed on 2026-05-22; see
`docs/reports/2026-05-21-h2t-ops-connector-freeze.md`.

### 2. Resolved: MeetGeek Listed-Meeting 404 (#156)

Goal: classify or fix the case where `h2t-ops meetgeek list` shows a meeting
but `get` or `transcript` returns 404 for that meeting id.

Status: done in `f363746`; #156 is closed.

Resolution:

- Markdown artifact commands no longer require singular metadata endpoint
  success; they can format with the known `meeting_id` like the legacy skill.
- `meetgeek get` falls back from `/v1/meeting/{id}` to the matching
  `/v1/meetings` row when the listed meeting exists.
- Live E2E passed for `get`, `transcript --format md`, and
  `transcript --format json --json` on the failing id.

### 3. Resolved: Calendar Closure (#82, #145)

Goal: make `h2t-ops calendar` good enough for real day-to-day querying.

Concrete fix-now scope from #82:

- arbitrary date window: `--from YYYY-MM-DD --to YYYY-MM-DD`;
- configurable limit, default high enough to avoid silent truncation;
- busy/transparency filtering, for example `--busy-only`.

Date-only windows use explicit semantics: `--from` is inclusive at local
00:00, `--to` is an inclusive user-facing date converted to an exclusive
next-day API bound, and query timezone resolves from `--tz` -> `H2T_CALENDAR_TZ`
-> `Asia/Jerusalem`. `--busy-only` filters raw events before normalization:
missing `transparency` means busy; `transparency: transparent` is excluded.

Broader #145 provider features can remain backlog unless pulled in explicitly:
Meet links, recurrence, patch/reschedule, all-day, multi-calendar, reminders, and
FreeBusy. `free-time` is also backlog unless explicitly scoped later.

Status:

- #82 is fixed in `6631f57` and closed with E2E evidence.
- E2E passed for old `--days`, explicit `--from/--to`, `--busy-only`, and
  partial-window validation.
- #145 remains provider backlog, not connector-freeze critical path.

### 4. Notion Closure (#81, #146)

Goal: decide whether Notion needs one more connector pass before freeze.

Known gaps:

- child_database / embedded DB traversal (#81);
- workspace discovery and parent graph (#146).

If these are not required for immediate connector closure, mark them as accepted
provider backlog rather than keeping them on the critical path.

### 5. Secrets / Setup Closure

Goal: make connector credentials understandable and portable before Mac work.

Related issues:

- #107 unified loader rollout;
- #109 MeetGeek secrets migration;
- #110 Telegram/Gemini secrets migration;
- #112 setup wizard;
- #94 canonical `~/.dor/secrets.env`;
- #13 cross-machine credential sync.

Status: consolidated as platform technical debt. See
`docs/credential-sync-policy.md`.

Do not let this expand into a full setup product unless needed for Mac
portability. The closure requirement is narrower: each connector should have a
documented credential source and a credible Mac transfer/setup path. An
interactive setup wizard remains future UX (#112), not connector migration.

### 6. Cross-Platform / Mac Readiness

Goal: make a future Mac port a planned smoke pass, not another migration.

Related issues:

- #53 Mac install notes;
- #73 cross-platform hook dispatch;
- #85 CI/unit-test hygiene;
- #79 per-machine config overrides.

Connector gate:

- normal connector usage cannot require Windows-only shell behavior;
- tests should pass cross-platform or have explicit skip reasons;
- setup instructions should work through `uv` on macOS;
- token/session locations must be configurable or documented.

Status: policy captured in `docs/credential-sync-policy.md`; implementation
work is no longer part of connector closure unless a concrete Mac smoke failure
is found.

### 7. `h2t-core:agent-profile` (#153)

Goal: make plugin loading contextual.

Target shape:

- repo base profile, for example `dev`, `ops`, `creative`, `product`, `marketing`;
- temporary task overlays, so a repo can add capabilities for one session without
  permanently changing its type;
- profile sync between machines;
- doctor/status output showing what profile and overlays are active.

This belongs to `h2t-core`, not `h2t-ops`.

Definition of done:

- profile data model is documented;
- skill command exists or a plan exists with exact files and acceptance gates;
- at least one real repo profile is applied and verified with `/context`;
- rollback path is documented.

### 8. Closed: Security / Dev Hygiene (#148)

Resolved findings:

- tracked `.claude/settings.local.json` no longer ships as repo policy;
- broad local-agent allowlists are kept machine-local / untracked;
- destructive command permissions remain approval-gated rather than tracked;
- `tools/pack-h2t-creative-context.ps1` no longer runs an unpinned
  `npx repomix@latest` fallback by default.

Policy:

- keep personal allowlists untracked or machine-local;
- keep tracked permission config narrow and repo-scoped;
- pin or remove runtime execution of unreviewed `@latest` packages.

Status: closed. Future permission and packer reviews are routine maintenance,
not active closure work.

### 9. Closed: CI / Test Hygiene (#85)

Resolved scope:

- removed hidden local venv and shell assumptions from the unit-test path;
- kept Windows/macOS differences documented or guarded where needed;
- current connector/core test suite passes in the active environment.

Status: closed. Future CI drift is routine maintenance, not connector migration.

### 10. Issue Sweep

Keep open issues only if they represent real future work.

Recommended triage:

| Bucket | Issues | Treatment |
| --- | --- | --- |
| Connector freeze umbrella | #155 | Closed; final smoke gate fixed in `494a947` |
| MeetGeek follow-up | #156 | Closed; fixed in `f363746` |
| Secrets/setup | #107, #112, #94, #109, #110, #13 | Classified as setup/Mac follow-up; avoid piecemeal drift |
| Calendar follow-up | #82, #145 | #82 fixed in `6631f57`, pushed and closed; #145 remains provider backlog unless explicitly widened |
| Notion follow-up | #146, #81 | Accepted provider discovery/dump backlog unless explicitly widened |
| Research backlog | #98, #97, #99, #101, #105, #72, #71, #70 | Keep as research/product backlog, not repo-closure blockers |
| Creative backlog | #119, #83, #88, #89, #90, #91, #92 | Move to creative roadmap; not h2t-ops closure |
| Cross-platform / machine config | #79, #73 | Keep as h2t-core/platform backlog |
| Old graph/session items | #54, #53, #21, #5 | Reclassify, move, or close if superseded |
| Legacy Telegram dedupe | #111 | Re-evaluate after #151: production plugin overlap is gone, but source archive remains |

## Connector Inventory

| Connector | Active CLI | State | Notes |
| --- | --- | --- | --- |
| Notion | `h2t-ops notion ...` | Done | Provider gaps tracked separately in #146/#81 |
| Gmail | `h2t-ops gmail ...` | Done | Normal connector |
| Calendar | `h2t-ops calendar ...` | Done | #82 fixed and closed; #145 remains provider backlog |
| Drive | `h2t-ops drive ...` | Done | `sync-meetings` retired from Drive in #147 |
| MeetGeek | `h2t-ops meetgeek ...` | Done | #156 fixed; local recording recovery remains skill-layer (#149) |
| Telegram | `h2t-ops telegram ...` | Done | Live auth verified; #121 closed |
| Research | `h2t-ops research ...` | Done | URL fetch ladder integrated |

## Boundaries

### POS / DOR Boundary

`h2t-ops` fetches provider artifacts. It does not own:

- meeting interpretation;
- transcript fusion;
- journal writes;
- captures/tasks/decisions;
- POS intake;
- `~/.dor/lake`, `~/.dor/context`, vault, or SQLite state.

Provider summaries, action items, and LLM outputs are evidence or proposals,
not truth.

### Workflow / Coordinator Layer

Workflows that combine providers or write local operational state are not
`h2t_ops/connectors/*`.

Examples:

- MeetGeek `convert`, `upload --from-file`, and local recovery;
- Telegram `digest`, `tasks`, `research`, `students`;
- Daily Brief;
- meeting backfill / transcript intake;
- Notion writes chosen by a coordinator.

Target shape:

```text
provider connector
  -> portable workflow script if needed
  -> artifact/proposal
  -> POS/coordinator review
  -> journal / KB / task system only after acceptance
```

### Meeting Workflow Boundary

Historical meeting skills solved overlapping parts of the same pipeline.
The target split is:

- `h2t-ops drive`: Drive provider I/O only.
- `h2t-ops meetgeek`: MeetGeek provider I/O and provider-specific recovery artifacts.
- portable workflow/converter scripts: DOCX/legacy export conversion, batch discovery,
  explicit input/output transformation runnable from any repo.
- POS transcript intake: canonical artifact registration, provenance, `meeting_key`,
  raw/readable transcript storage.
- POS distillation: summaries, action items, decisions, and captures as proposals with
  review gates.
- surfaces such as Daily Brief/session-start: read POS snapshots; they do not fetch
  or mutate meeting state.

`drive sync-meetings` (#147) is retired as a Drive-owned command. Its useful
semantics are preserved for a future POS/coordinator backlog item: discover
historical meeting artifacts, resolve a weak `meeting_key`, skip already-ingested
items, normalize to readable transcript artifacts, call POS transcript intake, and
write a provenance manifest.

## Outside h2t-ops

### 1. h2t-core

`h2t-core` owns base project/session infrastructure:

- `session-start`;
- `handoff`;
- `init-project`;
- `scaffold-project`;
- `setup`;
- future `agent-profile` (#153).

Plugin profiles belong here: repo base profile + task overlays + cross-machine sync.

### 2. Portable Workflow Scripts

Useful scripted workflows should not disappear into POS and should not stay embedded
inside provider connectors.

They should:

- have explicit input/output arguments;
- be runnable from any repo;
- consume connector JSON where possible;
- produce artifacts/proposals;
- avoid canonical POS state mutation unless invoked by an explicit coordinator action.

### 3. Legacy `h2t` Monolith

The legacy `h2t` plugin is retired from the marketplace in #151.

`plugins/h2t/` remains in the repository as rollback/archive source for now, but it
is no longer an active production plugin. Do not restart migration work from that
source unless a specific missing capability is identified.

### 4. Creative / Arch / Edu / DCC

Separate plugin domains:

- `h2t-creative`: landing/deck/style/design/voice-eval work;
- `h2t-arch`: DrawIO, diagrams, node research;
- `h2t-edu`: transcripts, lessons, YouTube education pipeline;
- `h2t-dcc`: TouchDesigner/Houdini in `C:/dev/h2t-dcc`.

Track these in their own roadmaps. They are not connector-closure blockers.

### 5. Repo / Security / Dev Hygiene

Routine maintenance, not active closure blockers:

- local untracked scratch files such as `.bak` artifacts;
- global/user skill bloat outside this repo;
- future `h2t-core:setup` / secrets wizard UX (#112);
- issue sweep and moving tasks to the correct repositories.

## Practical Order

1. Implement #153 `h2t-core:agent-profile`.
2. Sweep remaining issues into active / backlog / moved / stale-closed.
3. Only then pick the next product stream: Calendar/Notion provider features, research
   product backlog, creative recovery, or POS-side workflow contracts.

## Closure Forecast

Date: 2026-05-22

Calibration note: the previous forecast assumed Telegram, Research/fetch, Daily Brief,
legacy h2t retirement, profiles, and cleanup were still ahead. Since then, Telegram,
Research/fetch, Drive `sync-meetings` retirement, legacy `h2t` retirement, and #121
cleanup finished faster than expected. #155 connector freeze is now also closed:
the final smoke gate passed, the `h2t-ops --help` regression was fixed in
`494a947`, and connector work is no longer the active migration track.

| Remaining block | Optimistic | Realistic | Main risk |
| --- | ---: | ---: | --- |
| #153 `h2t-core:agent-profile` | 1-2 days | 2-3 days | Profile merge semantics, temporary overlays, cross-machine sync |
| Issue sweep / reclassification | 0.5-1 day | 1-2 days | Old issues that need careful "move vs close" decisions |

Remaining estimate to maintenance/closure mode:

- optimistic: 2-3 focused working days;
- realistic: 3-5 focused working days;
- with interruptions: 1-2 calendar weeks.

This excludes broad Calendar/Notion provider enhancements, research product backlog,
creative recovery, and POS-side workflow contracts. Those remain explicit future
streams and should not be silently absorbed into closure work.
