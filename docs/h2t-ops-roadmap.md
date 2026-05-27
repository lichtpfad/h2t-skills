# H2T-SKILLS Roadmap

**Status:** Post-closure maintenance and backlog roadmap
**Date:** 2026-05-28
**Owner:** h2t-skills
**Milestone tag:** `milestone/legacy-h2t-retired-2026-05-21`

This roadmap tracks the remaining work needed to move `h2t-skills` from active
connector migration into a cleaner maintenance mode. The connector code path is
implemented and mostly stabilized; public shippable validation has been completed
on clean Windows + macOS user runtimes and evidence is attached.

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
| Notion functional completion | #81, #146 | Done; fixed in `4c952d1`, embedded DB and workspace graph E2E passed |
| Calendar provider completion | #145 | Done; fixed in `0acb44b`, CI and live E2E passed |
| Drive `sync-meetings` | #147 | Retired from Drive; semantics moved to future POS/coordinator backlog |
| Duplicate skill entries | #150, #152, #153 cleanup commits | Done for split plugins |
| Legacy `h2t` marketplace plugin | #151 | Retired; split plugins are active entrypoints |

### Shippable Handoff

`h2t-ops` is architecturally shippable for POS/provider use and prepared for
shareability. The final clean-install PASS is done on clean Windows and macOS
user runtimes (Issue #166 evidence).

The operator-facing handoff and quickstart are captured in
`docs/reports/2026-05-22-h2t-ops-shippable-handoff.md`.

POS can consume connector JSON/artifacts. POS still owns canonical state,
interpretation, journal/task/decision acceptance, and long-term registries.

### Closure Status

The migration, connector freeze, clean-install validation, security/dev hygiene,
and CI/platform hardening are complete. `h2t-ops` is no longer in an active
closure phase. The repo is now in maintenance mode with explicit provider and
research backlog streams.

| Priority | Issue(s) | Work | Classification |
| --- | --- | --- | --- |
| 1 | #153 | `h2t-core:agent-profile` configurator and repo profiles | Implemented; future tuning is a new task, not h2t-ops blocker |
| 2 | #161 | Consolidate non-research connector skills into `h2t-ops:connectors` + lazy references | Done — installed-plugin smoke PASS on Mac 2026-05-23; shippable gate cleared |
| 3 | #148, #85 | Security/dev hygiene and CI/unit-test hygiene | Done; no longer an active closure blocker |
| 4 | #13, #94, #107, #109, #110, #73, #79, #53 | Platform portability / credential policy | Done or consolidated into policy; routine maintenance only |
| 5 | #112 | Setup wizard backlog | Closed as separate UX/setup stream, not closure work |

### Active Product Backlog

The current open work is feature/product backlog, not migration/closure.

| Milestone | Issue(s) | Workstream | Notes |
| --- | --- | --- | --- |
| skills-release | #190 | Skills release gate | `#183`, `#185`, `#186`, `#195`, research follow-ups `#192`-`#194`, and connector API P0 `#212`-`#231` are complete; #71 is closed as release-ready/superseded |
| lifecycle-os | #196, #197 | Project lifecycle consolidation | Planned after #195; not required before the immediate skills-release gate unless #190 finds it blocks packaging |
| connector-api-gaps | #208 | Future connector enhancement backlog | Connector API P0 #212-#231 is complete; #208 remains non-release Drive conversion backlog |
| graphs-pos | #21, #54, #70, #72 | Graphs / POS backlog | Deferred graphs, evals, and POS integration stream |
| creative-p2 | #83, #88, #89, #90, #91, #92, #119 | Creative recovery backlog | Separate creative/product stream |
| M6: h2t-arch | #5 | Diagram-node docs enforcement | Legacy arch stream still open |

The backlog is now milestone-driven again:

- `skills-release`
- `graphs-pos`
- `creative-p2`
- `M6: h2t-arch`

Priority labels still matter, but milestone assignment is now the primary
planning surface for open product work.

### Recent Validation Gate

The recent-closure validation sweep was run to normalize evidence standards
after the fast P1/provider pass. Results are recorded in
`docs/reports/2026-05-25-h2t-ops-recent-closure-validation-evidence.md`.

Validation status:

| Issue(s) | Surface | Current state |
| --- | --- | --- |
| #169 | Drive `create-folder` | Live PASS |
| #172 | Gmail thread operations | Read-only live PASS; reply-in-thread still requires a prepared safe thread |
| #173 | Gmail attachment download | Live PASS |
| #181 | Telegram send | Live PASS |
| #176 | Calendar RSVP + move | Closed as implementation-complete; `move` live PASS, RSVP live proof deferred due to lack of a safe invite |

### Research P2 Smoke Evidence (2026-05-26)

Issues #182, #99, #105 closed. Commits: `00f5bff` (exa), `6f32959` (youtube), `52f1941` (fetch dispatch), `67986e0` (author_resolve), `5657d70` (visual-ocr --url), `bf1cd6b` (sidecar fix), `c773e3a` (encoding fix). 822 unit tests pass.

| Command | Result | Notes |
| --- | --- | --- |
| `research similar --url https://derivative.ca` | OK | 9 results, 718ms, Exa findSimilar |
| `research answer --query "TouchDesigner POP operators"` | OK | Full answer + citations, Exa /answer |
| `research fetch --url https://youtube.com/watch?v=dQw4w9WgXcQ` | OK | `provider_used: youtube_transcript`, 61 segments, en |
| `research visual-ocr --url https://alltd.org/pop-starter-pack-touchdesigner/` | OK | screenshot captured, OCR medium confidence; encoding fix c773e3a applied |
| `research resolve-author --name "Acidbourbon" --keywords "TouchDesigner"` | OK | `confidence: likely`, found via alltd.org/uploader/acidbourbon/ |

### Research Ergonomics Status (2026-05-27)

Issue #71 has been split into concrete follow-ups. The core research substrate
is now local, JSON-first, and navigable by agents.

| Issue(s) | Surface | Current state |
| --- | --- | --- |
| #192 | local artifact navigation surface | Closed; `index`, `show`, and `resolve` commands landed with smoke evidence |
| #193 | retention cleanup and index doctor | Closed; `doctor`, `rebuild-indexes`, and dry-run `cleanup` landed with smoke evidence |
| #194 | provider/key readiness routing | Closed; `providers` and `route` commands landed; Exa-backed commands fail before side effects when `EXA_API_KEY` is missing |
| #71 | original umbrella | Closed for skills-release; old `--no-json` wording is superseded by JSON-first artifacts, and literal project multi-key routing is not release-critical |

Non-release research backlog remains in `graphs-pos`: #70 for eval/fork and
h2t-evals integration, and #72 for broader provider/role-boundary design.
Research is release-ready for the current skills pack.

### Connector API Gap Audit (2026-05-27)

Single-file upload dogfooding exposed duplicate-file behavior when an operator
expected upsert semantics. A follow-up pass compared current wrapper surfaces
against common provider API workflows and created explicit gap issues.

| Connector | Issue(s) | Gap |
| --- | --- | --- |
| Drive | #212-#218, #208 | upsert upload, trash/delete, metadata get, docs create/read, docs-tab replace and inline formatting, MD->DOCX convert |
| Gmail | #219, #221, #225 | reply, forward, label create/delete |
| Notion | #220, #223, #227 | database row create/update, archive, append/replace block CLI |
| Telegram | #222, #226, #229 | send-file, forward-message, delete-message |
| MeetGeek | #230, #231 | action-items, date-range list filter |
| Calendar | #224, #228 | create-calendar, list recurring event instances |

These were product coverage gaps, not connector migration blockers. P0 coverage
for #212-#231 is now complete in PRs #233-#238. Remaining connector enhancements,
including #208, should be prioritized by active workflow need.

## Critical Path Details

### Completed: Connector Freeze + Mac Portability Gate (#155)

Goal: finish connectors as a category before moving to profile/runtime work.

This does not mean implementing every provider feature. It means every known
connector issue is intentionally classified:

- fix now;
- completed provider/product closure;
- accepted future product backlog;
- Mac/setup portability follow-up;
- stale/superseded and closed with evidence.

Definition of done:

- #82/#145 Calendar are fixed and closed;
- #81/#146 Notion are fixed and closed;
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

Status:

- #82 is fixed in `6631f57` and closed with E2E evidence.
- E2E passed for old `--days`, explicit `--from/--to`, `--busy-only`, and
  partial-window validation.
- #145 is fixed in `0acb44b` and closed. CI passed, and live E2E passed for
  calendar listing, FreeBusy, all-day events, Google Meet links, recurrence,
  reminders, event update, and cleanup.

### 4. Resolved: Notion Closure (#81, #146)

Goal: complete practical Notion provider functionality before handoff.

Status: done in `4c952d1`; #81 and #146 are closed.

Resolution:

- recursive block scan discovers `child_database` blocks;
- embedded database IDs can be queried and dumped;
- workspace search/graph functionality is available for parent/child discovery;
- sync emits sidecar metadata for machine-readable references.

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

### 7. Resolved: `h2t-core:agent-profile` (#153)

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

Status: implemented in `h2t-core`. Follow-up testing and configurator
refinements should be tracked as new UX/debug tasks, not as connector migration
blockers.

### 8. Connector Skill Surface (#161)

Goal: reduce h2t-ops connector skill bloat without hiding provider capability.

Target shape:

- one active connector navigator skill: `h2t-ops:connectors`;
- lazy references for Calendar, Gmail, Drive, Notion, Telegram, and MeetGeek;
- `h2t-ops:research` remains separate because it has distinct research quality,
  telemetry, template, and POS registration requirements;
- `h2t-ops:daily-brief` remains separate because it is a workflow/surface, not a
  provider connector;
- legacy provider scripts/tests stay in the repo for compatibility and future
  portable workflow extraction; they are not active skill entrypoints.

Status: implemented and PASS on clean Windows/macOS user runtimes. The active
`h2t-ops` surface is:
`h2t-ops:connectors`, `h2t-ops:research`, `h2t-ops:daily-brief`.
Legacy per-connector entries are no longer active in `/context`.

### 9. Resolved: Security / Dev Hygiene (#148)

Planned follow-up (post-shareability):

- tracked `.claude/settings.local.json` no longer ships as repo policy;
- broad local-agent allowlists are kept machine-local / untracked;
- destructive command permissions remain approval-gated rather than tracked;
- `tools/pack-h2t-creative-context.ps1` no longer runs an unpinned
  `npx repomix@latest` fallback by default.

Policy:

- keep personal allowlists untracked or machine-local;
- keep tracked permission config narrow and repo-scoped;
- pin or remove runtime execution of unreviewed `@latest` packages.

Status: closed. Follow-up actions were handled as post-shippable hygiene, not
as an ongoing closure blocker.

### 10. Resolved: CI / Test Hygiene (#85)

Planned scope (post-shareability):

- removed hidden local venv and shell assumptions from the unit-test path;
- kept Windows/macOS differences documented or guarded where needed;
- current connector/core test suite passes in the active environment.

Status: closed. Future CI/platform drift is routine maintenance, not connector
migration.

### 11. Issue Sweep

Keep open issues only if they represent real future work.

Recommended triage:

| Bucket | Issues | Treatment |
| --- | --- | --- |
| Connector freeze umbrella | #155 | Closed; final smoke gate fixed in `494a947` |
| MeetGeek follow-up | #156 | Closed; fixed in `f363746` |
| Secrets/setup | #107, #112, #94, #109, #110, #13 | Classified as setup/Mac follow-up; avoid piecemeal drift |
| Calendar follow-up | #82, #145 | Closed; #82 fixed in `6631f57`, #145 fixed in `0acb44b` |
| Notion follow-up | #146, #81 | Closed; fixed in `4c952d1` |
| Research backlog | #72, #70 | `#99/#105/#182` closed 2026-05-26; `#192/#193/#194` and #71 closed 2026-05-27. #70/#72 stay in `graphs-pos` |
| Connector API gaps | #212-#231, #208 | Explicit feature backlog from API coverage audit; #212 is the only current P0 |
| Provider backlog | none | Connector/provider closure sweep is complete. The former provider items #169, #170, #172, #173, #174, #176, #177, #179, #180, and #181 are now closed; `#176` closed as implementation-complete with deferred RSVP live proof |
| Deploy/operator backlog | #183 | Closed 2026-05-26. `h2t-ops deploy` landed with live `list`, `--dry-run`, and `status` proof plus `h2t-ops:deploy` skill instructions |
| Creative backlog | #119, #83, #88, #89, #90, #91, #92 | Move to creative roadmap; not h2t-ops closure |
| Cross-platform / machine config | #79, #73 | Keep as h2t-core/platform backlog |
| Old graph/session items | #54, #53, #21, #5 | Reclassify, move, or close if superseded |
| Legacy Telegram dedupe | #111 | Re-evaluate after #151: production plugin overlap is gone, but source archive remains |

## Connector Inventory

| Connector | Active CLI | State | Notes |
| --- | --- | --- | --- |
| Notion | `h2t-ops notion ...` | Done | Embedded DB and workspace graph support complete |
| Gmail | `h2t-ops gmail ...` | Done | Normal connector |
| Calendar | `h2t-ops calendar ...` | Done | Calendar UX and provider feature closure complete |
| Drive | `h2t-ops drive ...` | Done | `sync-meetings` retired from Drive in #147 |
| MeetGeek | `h2t-ops meetgeek ...` | Done | #156 fixed; local recording recovery remains skill-layer (#149) |
| Telegram | `h2t-ops telegram ...` | Done | Live auth verified; #121 closed |
| Research | `h2t-ops research ...` | Done | URL fetch ladder + YouTube provider + Exa similar/answer + author resolve + visual-ocr --url |

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

`plugins/h2t/` remains in the repository as rollback/archive source for now, but
it no longer has an active plugin manifest and is no longer an active production
plugin. Do not restart migration work from that source unless a specific missing
capability is identified.

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

1. Use the shippable handoff report when telling POS that the connector stage is
   complete: `docs/reports/2026-05-22-h2t-ops-shippable-handoff.md`.
2. Treat connector migration and closure as done; do not reopen it via piecemeal
   backlog items.
3. Finish the `skills-release` gate with #190 pre-release audit.
4. Finish #190 by merging the pre-release audit and final connector API P0
   evidence.
5. Keep #196/#197 as lifecycle consolidation after #195 unless the pre-release
   audit proves they block packaging.
6. Keep research product work (#70/#72), creative recovery, and POS-side workflow
   contracts out of the immediate release gate.
7. Keep roadmap language honest: open feature gaps are not “migration blockers”
   now that `h2t-ops` is already shippable.

## Closure Forecast

Date: 2026-05-27

Calibration note: the previous forecast assumed Telegram, Research/fetch,
Daily Brief, legacy h2t retirement, profiles, cleanup, and broad Calendar/Notion
features were still ahead. Since then, Telegram, Research/fetch, Drive
`sync-meetings` retirement, legacy `h2t` retirement, #121 cleanup, #155
connector freeze, Notion #81/#146, and Calendar #145 are complete.

`h2t-ops` connector work is no longer the active migration track. #153, #161,
#148, and #85 are closed; connector skill surface and post-shippable hygiene are
complete. The remaining release track is a skills-pack quality gate, not
connector migration.

| Remaining block | Optimistic | Realistic | Main risk |
| --- | ---: | ---: | --- |
| #153 `h2t-core:agent-profile` | Done | Done | Future tuning belongs to new tasks |
| #161 connector skill consolidation | Done | Done | PASS evidence captured in issue #166 and docs/reports/2026-05-23... |
| #148 security/dev hygiene | Done | Done | Routine maintenance only |
| #85 CI/platform hygiene | Done | Done | Routine maintenance only |
| #195 docs-lint enhancement | Done | Done | Closed 2026-05-27 |
| #71 research ergonomics | Done | Done | Closed 2026-05-27; multi-key is deferred unless it becomes operationally important |
| #190 pre-release audit | In review | In review | Final evidence PR closes the release gate |

Remaining estimate to skills-release readiness:

- optimistic: merge current evidence PR;
- realistic: merge current evidence PR after one final review pass.

This excludes connector API coverage gaps, research product backlog, creative
recovery, setup wizard/Mac onboarding, and POS-side workflow contracts. Those
remain explicit future streams and should not be silently absorbed into
h2t-ops connector closure.
