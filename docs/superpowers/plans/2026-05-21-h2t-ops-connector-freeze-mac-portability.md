# h2t-ops Connector Freeze + Mac Portability Gate — Implementation Plan (#155)

Date: 2026-05-21
Status: ready for review
Design: docs/superpowers/specs/2026-05-21-h2t-ops-connector-freeze-mac-portability-design.md

## Goal

Finish h2t-ops connector closure so connector migration can stop being an
active category of work.

The plan fixes the known fix-now gaps, classifies the remaining provider/setup
issues, and records a Mac portability smoke plan. It does not implement broad
provider backlog or `h2t-core:agent-profile`.

## Authoritative Inputs

| Input | Path / Issue |
| --- | --- |
| Design | `docs/superpowers/specs/2026-05-21-h2t-ops-connector-freeze-mac-portability-design.md` |
| Roadmap | `docs/h2t-ops-roadmap.md` |
| Connector runbook | `plugins/h2t-ops/references/h2t-connector-runbook.md` |
| POS boundary | `plugins/h2t-ops/references/pos-operational-boundary.md` |
| Testing plan | `docs/h2t-ops-testing-plan.md` |
| Umbrella issue | #155 |
| MeetGeek 404 | #156 |
| Calendar UX | #82 |
| Calendar provider backlog | #145 |
| Notion backlog | #81, #146 |
| Secrets/setup backlog | #107, #109, #110, #112, #94, #13 |
| Cross-platform backlog | #53, #73, #85, #79 |

## Hard Constraints

1. Do not revive the legacy `h2t` marketplace plugin.
2. Do not add POS, DOR, vault, lake, or journal writes to connectors.
3. Do not expand this into all Calendar/Notion provider features.
4. Treat MeetGeek `list` → `get/transcript` 404 as fix-now or explicitly classified.
5. Keep SDK imports lazy; `dev check lazy-registry` must stay green.
6. Stage only files named by the current task. The repo has unrelated dirty
   `.claude/*`, `.superpowers/`, `build/`, backup, and packer files.
7. If live provider smoke cannot run because credentials or provider state are
   unavailable, record the reason. Do not fake success.
8. Final closure does not push, close #155, or close related issues without
   explicit approval.

## File Map

Expected code files if fix-now work is implemented:

```text
h2t_ops/connectors/meetgeek/client.py
h2t_ops/connectors/meetgeek/commands.py
tests/connectors/meetgeek/test_client.py
tests/connectors/meetgeek/test_commands.py
plugins/h2t-ops/skills/meetgeek/SKILL.md

h2t_ops/connectors/calendar/client.py
h2t_ops/connectors/calendar/commands.py
tests/connectors/calendar/test_client.py
tests/connectors/calendar/test_commands.py
plugins/h2t-ops/skills/calendar/SKILL.md
```

Expected docs/report files:

```text
docs/reports/2026-05-21-h2t-ops-connector-freeze.md
docs/h2t-ops-roadmap.md
```

No other files are in scope unless a task explicitly updates the file map before
editing.

## T0 — Baseline Freeze Audit

Commit: optional docs/report commit only.

Purpose: record current state before changing connector code.

Steps:

1. Create `docs/reports/2026-05-21-h2t-ops-connector-freeze.md` with sections:

   ```text
   # h2t-ops Connector Freeze Report
   Date:
   Issue:

   ## Connector Inventory
   ## Fix-Now Items
   ## Accepted Backlog
   ## Secrets / Setup / Mac Portability
   ## Smoke Matrix
   ## Final Issue Disposition
   ```

2. Capture current open issues relevant to #155:

   ```bash
   gh issue view 155 --repo lichtpfad/h2t-skills
   gh issue view 156 --repo lichtpfad/h2t-skills
   gh issue view 82 --repo lichtpfad/h2t-skills
   gh issue view 145 --repo lichtpfad/h2t-skills
   gh issue view 81 --repo lichtpfad/h2t-skills
   gh issue view 146 --repo lichtpfad/h2t-skills
   ```

3. Run baseline local gates:

   ```bash
   uv run h2t-ops dev check lazy-registry
   uv run h2t-ops dev pytest tests/connectors -q
   ```

4. Record any failures in the report. Do not fix unrelated failures in T0.

5. Commit only the report if created:

   ```bash
   git add docs/reports/2026-05-21-h2t-ops-connector-freeze.md
   git commit -m "docs(h2t-ops): start connector freeze report (#155)"
   ```

## T1 — MeetGeek Listed-Meeting 404 Triage / Fix (#156)

Commit: one code/test/docs commit if a code fix is needed; otherwise one report
commit documenting the classification.

Purpose: resolve or classify `list` → `get/transcript` 404 before freeze.

Steps:

1. Add or extend tests first.

   Required test contracts:

   - listed raw row can expose all candidate ids without display normalization
     hiding them;
   - `get_meeting()` endpoint shape is asserted;
   - `get_transcript()` endpoint shape is asserted;
   - 404 from transcript/get produces an actionable error or hint after the
     chosen behavior is known.

2. Reproduce or classify live with a listed meeting id.

   Read-only commands:

   ```bash
   uv run h2t-ops meetgeek list --limit 5 --json
   uv run h2t-ops meetgeek get <id> --json
   uv run h2t-ops meetgeek transcript <id> --format json --json
   ```

   Record the raw list item keys for the failing meeting in the report. Do not
   paste API keys or full private transcript content.

3. Decide fix path:

   - If wrong id field: update command/client selection and tests.
   - If wrong endpoint: update endpoint and tests.
   - If transcript not ready/retained: keep endpoint, but improve typed error
     message/hint and document provider limitation.
   - If permission limitation: map to `AuthError` or `ProviderError` as
     appropriate, not generic `NotFoundError`.

4. Run:

   ```bash
   uv run h2t-ops dev pytest tests/connectors/meetgeek -q
   uv run h2t-ops dev check lazy-registry
   ```

5. Update `plugins/h2t-ops/skills/meetgeek/SKILL.md` only if the user-facing
   recovery/error contract changed.

6. Commit scoped files only:

   ```bash
   git add h2t_ops/connectors/meetgeek tests/connectors/meetgeek plugins/h2t-ops/skills/meetgeek/SKILL.md docs/reports/2026-05-21-h2t-ops-connector-freeze.md
   git commit -m "fix(meetgeek): classify listed meeting 404 behavior (#156)"
   ```

## T2 — Calendar UX Closure (#82)

Commit: one code/test/docs commit.

Purpose: make `h2t-ops calendar` good enough for real date-window usage.

Fix-now scope:

- `calendar list --from YYYY-MM-DD --to YYYY-MM-DD`;
- `calendar list --max N` with safe default high enough to avoid silent
  truncation;
- `calendar list --busy-only` filtering out transparent/non-blocking events.

Date-window contract:

- `--from` is inclusive at local 00:00:00 in the query timezone.
- `--to` is inclusive as a user-facing date and converted to an exclusive
  next-day 00:00:00 API bound.
- Query timezone resolution: `--tz`, then `H2T_CALENDAR_TZ`, then
  `Asia/Jerusalem`.
- Backward-compatible `--days` remains available.
- Raw Google events are filtered for `--busy-only` before normalization:
  missing `transparency` means busy; `transparency == "transparent"` is
  excluded.

Out of scope unless explicitly approved:

- Meet links;
- recurrence;
- patch/reschedule;
- all-day mutation expansion;
- multi-calendar;
- reminders;
- full FreeBusy provider integration.
- `free-time` scheduling helper.

Steps:

1. Write failing tests first in `tests/connectors/calendar/`.

   Required test contracts:

   - client can list using explicit `time_min` / `time_max`;
   - commands parse `--from`, `--to`, `--max`, `--busy-only`, `--tz`;
   - date-only `--from` / `--to` use inclusive user-facing dates and an
     exclusive next-day API upper bound;
   - timezone resolution uses `--tz`, then `H2T_CALENDAR_TZ`, then
     `Asia/Jerusalem`;
   - `--days` backward compatibility remains;
   - transparent events are filtered before normalization when `--busy-only` is
     set;
   - missing `transparency` is treated as busy;
   - output still normalizes all-day/timed events;
   - module-level Google import guard remains true.

2. Implement client API without breaking existing callers.

   Suggested shape:

   ```python
   def list_events(
       self,
       days: int = 1,
       max_results: int = 250,
       *,
       time_min: str | None = None,
       time_max: str | None = None,
       tz: str | None = None,
       busy_only: bool = False,
   ) -> list[dict]:
       # implementation follows existing CalendarClient event-listing pattern
   ```

3. Implement CLI parser:

   ```bash
   h2t-ops calendar list --from 2026-05-01 --to 2026-05-21 --tz Asia/Jerusalem --max 250 --busy-only --json
   h2t-ops calendar list --days 7 --json
   ```

4. Update `plugins/h2t-ops/skills/calendar/SKILL.md`.

5. Run:

   ```bash
   uv run h2t-ops dev pytest tests/connectors/calendar -q
   uv run h2t-ops dev check lazy-registry
   ```

6. Optional live read-only smoke:

   ```bash
   uv run h2t-ops calendar list --from 2026-05-01 --to 2026-05-21 --tz Asia/Jerusalem --max 250 --busy-only --json
   ```

7. Commit scoped files only:

   ```bash
   git add h2t_ops/connectors/calendar tests/connectors/calendar plugins/h2t-ops/skills/calendar/SKILL.md docs/reports/2026-05-21-h2t-ops-connector-freeze.md
   git commit -m "feat(calendar): add date-window and busy-only list filters (#82)"
   ```

## T3 — Notion / Secrets / Mac Portability Classification

Commit: one docs/report commit unless a tiny docs-only skill update is needed.

Purpose: prevent #81/#146 and secrets/setup issues from staying ambiguous.

Steps:

1. Inspect Notion issues #81/#146 against current code and tests.

   Decision output for each:

   - `fix-now`;
   - `accepted provider backlog`;
   - `moved to POS/coordinator`;
   - `stale/superseded`.

2. Inspect secrets/setup issues #107/#109/#110/#112/#94/#13.

   For each connector, record:

   | Connector | Credential source | Shared helper? | Mac transfer/setup note |
   | --- | --- | --- | --- |
   | Notion | | | |
   | Gmail | | | |
   | Calendar | | | |
   | Drive | | | |
   | MeetGeek | | | |
   | Telegram | | | |
   | Research | | | |

3. Inspect cross-platform issues #53/#73/#85/#79.

   Classify what blocks h2t-ops connector usage on Mac vs broader repo tooling.

4. Update the freeze report.

5. Comment on issues where classification changed. Do not close issues unless
   the acceptance criteria are truly met.

6. Commit:

   ```bash
   git add docs/reports/2026-05-21-h2t-ops-connector-freeze.md docs/h2t-ops-roadmap.md
   git commit -m "docs(h2t-ops): classify connector freeze follow-ups (#155)"
   ```

## T4 — Final Connector Smoke Matrix and Closure

Commit: final docs/report commit if the report changes.

Purpose: produce final evidence for #155.

Steps:

1. Run local non-provider gates:

   ```bash
   uv run h2t-ops --help
   uv run h2t-ops connectors
   uv run h2t-ops dev check lazy-registry
   uv run h2t-ops dev pytest tests/connectors -q
   ```

2. Run provider help gates:

   ```bash
   uv run h2t-ops notion --help
   uv run h2t-ops gmail --help
   uv run h2t-ops calendar --help
   uv run h2t-ops drive --help
   uv run h2t-ops meetgeek --help
   uv run h2t-ops telegram --help
   uv run h2t-ops research --help
   ```

3. Run read-only live smokes when credentials are available:

   ```bash
   # Notion requires a real known page id. If none is available, record SKIPPED.
   uv run h2t-ops notion blocks REAL_PAGE_ID --limit 1 --json
   uv run h2t-ops gmail list --max 1 --json
   uv run h2t-ops calendar list --days 1 --max 10 --json
   uv run h2t-ops drive list --max 1 --json
   uv run h2t-ops meetgeek auth-check --json
   uv run h2t-ops telegram auth status --json
   uv run h2t-ops research search --query "test" --num-results 1 --json
   ```

   Replace `REAL_PAGE_ID` before running. Do not run placeholder commands; mark
   the provider smoke as skipped if no safe read-only id is available.

4. Update the freeze report with:

   - pass/fail table;
   - skipped live smokes and reasons;
   - fixed issues;
   - accepted backlog;
   - Mac portability plan.

5. Run final status:

   ```bash
   git status --short
   git diff --check
   ```

6. Commit docs if changed:

   ```bash
   git add docs/reports/2026-05-21-h2t-ops-connector-freeze.md docs/h2t-ops-roadmap.md
   git commit -m "docs(h2t-ops): record connector freeze evidence (#155)"
   ```

7. STOP for approval.

   Do not push, close #155, close #156, or close #82 without explicit user
   approval.

## Final Success Criteria

- #156 is fixed or classified.
- #82 fix-now scope is implemented or explicitly narrowed.
- #81/#146 are classified.
- secrets/setup/Mac issues are classified.
- changed connector tests pass.
- all connector help commands pass.
- final smoke report exists.
- #155 can be closed with evidence after approval.
