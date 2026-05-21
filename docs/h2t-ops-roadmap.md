# H2T-SKILLS Roadmap

**Status:** Active closure roadmap
**Date:** 2026-05-21
**Owner:** h2t-skills
**Milestone tag:** `milestone/legacy-h2t-retired-2026-05-21`

This roadmap tracks the remaining work needed to move `h2t-skills` from active
connector migration into a cleaner maintenance mode.

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
| Drive parity | #133 | Done |
| MeetGeek API connector | #134 | Done |
| Telegram connector | #135, #121 | Done; #121 closed as fixed by typed `SESSION_INCOMPATIBLE` handling |
| Research connector | #136 | Done |
| URL fetch ladder | #137, #100, #103, #114 | Done |
| Connector runbook | #138 | Done |
| Runtime smoke / UTF-8 fixes | #139, #141, #143 | Done |
| MeetGeek local recovery | #149 | Done; kept as skill-layer recovery, not connector runtime |
| Drive `sync-meetings` | #147 | Retired from Drive; semantics moved to future POS/coordinator backlog |
| Duplicate skill entries | #150, #152, #153 cleanup commits | Done for split plugins |
| Legacy `h2t` marketplace plugin | #151 | Retired; split plugins are active entrypoints |

### Active Critical Path

The next work is not "more connectors". It is repo/runtime hygiene.

| Priority | Issue(s) | Work | Why it matters |
| --- | --- | --- | --- |
| 1 | #153 | `h2t-core:agent-profile` | Replace global everything-enabled plugin load with repo base profiles, task overlays, and sync between machines |
| 2 | #148 | Harden tracked agent permissions and context packer | Prevent broad local-agent permissions and unpinned `npx repomix@latest` from becoming shipped policy |
| 3 | #85 | Fix lib/unit tests broken in CI | Repo should not be called stable while CI has known infra failures |
| 4 | issue sweep | Reclassify / close stale issues | Keep open issues as real near-term work, not historical noise |

## Critical Path Details

### 1. `h2t-core:agent-profile` (#153)

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

### 2. Security / Dev Hygiene (#148)

Known findings to resolve:

- tracked `.claude/settings.local.json` grants overly broad local-agent access;
- broad read access to user home should not ship as repo policy;
- destructive commands must remain approval-gated;
- `tools/pack-h2t-creative-context.ps1` runs `npx repomix@latest`, which is unpinned.

Policy:

- keep personal allowlists untracked or machine-local;
- keep tracked permission config narrow and repo-scoped;
- pin or remove runtime execution of unreviewed `@latest` packages.

This was intentionally deferred during connector migration. It is now part of
the closure path.

### 3. CI / Test Hygiene (#85)

Fix known CI failures before calling the repo stable:

- hardcoded `~/.h2t/venv` assumptions;
- stale stack assertions;
- any Windows-only assumptions that break Linux/macOS CI.

This is infrastructure work, not connector feature work.

### 4. Issue Sweep

Keep open issues only if they represent real future work.

Recommended triage:

| Bucket | Issues | Treatment |
| --- | --- | --- |
| Secrets/setup | #107, #112, #94, #109, #110, #13 | Consolidate into a smaller setup/secrets roadmap; avoid piecemeal drift |
| Calendar follow-up | #145, #82 | Keep open; #82 is concrete Calendar UX (`--from/--to`, limit, transparency), #145 is broader provider feature work |
| Notion follow-up | #146, #81 | Keep as provider feature backlog |
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
| Calendar | `h2t-ops calendar ...` | Done parity | UX/provider gaps tracked in #82/#145 |
| Drive | `h2t-ops drive ...` | Done | `sync-meetings` retired from Drive in #147 |
| MeetGeek | `h2t-ops meetgeek ...` | Done | Local recording recovery remains skill-layer (#149) |
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

Important for finishing the repository:

- #148 tracked agent permissions + context packer hardening;
- `.claude/settings*` dirty-tree cleanup;
- stale `.bak`, `build/`, `.superpowers/` cleanup;
- global/user skill bloat;
- `h2t-core:setup`, secrets wizard, credential sync;
- issue sweep and moving tasks to the correct repositories.

## Practical Order

1. Implement #153 `h2t-core:agent-profile`.
2. Resolve #148 security/dev hygiene.
3. Fix #85 CI/unit-test hygiene.
4. Sweep issues into active / backlog / moved / stale-closed.
5. Only then pick the next product stream: Calendar/Notion provider features, research
   product backlog, creative recovery, or POS-side workflow contracts.

## Closure Forecast

Date: 2026-05-21

Calibration note: the previous forecast assumed Telegram, Research/fetch, Daily Brief,
legacy h2t retirement, profiles, and cleanup were still ahead. Since then, Telegram,
Research/fetch, Drive `sync-meetings` retirement, legacy `h2t` retirement, and #121
cleanup finished faster than expected. The remaining forecast is therefore only for
repo closure/hygiene, not for product backlog.

| Remaining block | Optimistic | Realistic | Main risk |
| --- | ---: | ---: | --- |
| #153 `h2t-core:agent-profile` | 1-2 days | 2-3 days | Profile merge semantics, temporary overlays, cross-machine sync |
| #148 permissions / context packer hardening | 0.5-1 day | 1-2 days | Separating personal allowlists from tracked repo policy |
| #85 CI/unit-test hygiene | 0.5-1 day | 1-2 days | Hidden platform assumptions |
| Issue sweep / reclassification | 0.5-1 day | 1-2 days | Old issues that need careful "move vs close" decisions |
| Secrets/setup consolidation triage | 0.5 day | 1-2 days if implemented | Scope creep into full setup wizard |

Total estimate to maintenance/closure mode:

- optimistic: 3-5 focused working days;
- realistic: 5-8 focused working days;
- with interruptions: 1-2 calendar weeks.

This excludes Calendar/Notion provider enhancements, research product backlog, creative
recovery, and POS-side workflow contracts. Those are legitimate next streams, but not
required to close the h2t-ops migration chapter.
