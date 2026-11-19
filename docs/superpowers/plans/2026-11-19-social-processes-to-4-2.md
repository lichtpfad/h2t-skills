---
title: "Social processes to 4.2.0"
status: "draft"
date: "2026-11-19"
milestone: "M9: 4.2"
issue: "none"
reason: "stage plan; its steps are issues in milestone M9: 4.2, listed in the plan"
---

# Social processes to 4.2.0

Stage plan, not an implementation plan. Each phase gets its own TDD plan
(`superpowers:writing-plans`) when it starts; that plan may split a phase issue into step
issues. Spec: `docs/superpowers/specs/2026-11-19-social-pipeline-design.md`.

## Release rule (owner, 2026-11-19)

- 4.2.0 ships when all five operating processes work live: insights, communication, content,
  research, ads (spec §4.3, §9 order). Onboarding (spec §4.5) is after 4.2.0.
- Until then each finished phase may ship as a 4.1.x patch. 4.1.1 shipped the first, read-only
  part of insights (#667) with the dependency fix (#669).
- Every issue below sits in milestone **M9: 4.2**.

## Where it stands (2026-11-19, command output in PR #667)

- Built: `h2t-ops social accounts discover|list`, `check`, `run insights`, `journal`; read-only.
- Live: 8 Instagram + 2 Threads accounts answer `check`; `run insights` on
  instagram:hou2touch read 120 posts, journal steps 2→3→4→6 linked.
- Not built or not live-run: Threads insights run, Facebook Page insights, Threads token
  refresh, schedule, account-level metrics, audience, stories, comments text, captions, snapshot
  file (#670); every write process.

## Decisions first (irreversible, `decision.yml`)

| id | question | blocks |
|---|---|---|
| D1 | Snapshot file schema: folder layout, file per data group, columns, format (CSV or JSON), manifest of unavailable metrics. External contract: rejuve scripts read it. | #670 item 6 |
| D2 | Approval flow for outward actions: journal states (spec §9a `pending → approved/denied/expired → done/failed`), the `h2t-ops social approve` surface, what an unattended run does with `ask` (spec §9: stays `pending`), expiry. Lifecycle and failure semantics. | phases 2, 3, 5 |

## Phase 1 — insights complete (read-only)

| id | type | title | acceptance (command → expected) | not in it |
|---|---|---|---|---|
| — | feature | #670 dated Instagram snapshot (existing issue) | per #670 | — |
| S1 | feature | Run insights on Threads accounts live | `h2t-ops social run insights --account threads:hou2touch` → report file + journal steps linked; a fixture with Meta's real response shape goes red when a field is dropped | Threads writes |
| S2 | feature | Facebook Page insights in the insights run | `run insights --account facebook:hou2touch` → report with Page reach/engagement; unavailable metric → journal record with Meta error code | Page posting |
| S3 | feature | Refresh Threads tokens before expiry (~60 days) | `h2t-ops social tokens refresh` → new value written through `secrets.write_env`, journal records key name and new expiry only; expired-token fixture → refresh path taken | Meta user token (long-lived, no refresh) |
| S4 | feature | Scheduled insights run | spec §9a runtime: one-shot command started by Windows Task Scheduler; a documented `schtasks` line in `references/social.md` and a run record per day in the journal with trigger `schedule` | VPS cron (later) |
| S5 | chore | Move Meta/Threads secrets to `secrets/shared` before the legacy fallback goes | keys resolve from `~/.h2t/secrets/shared/{meta,threads}.env`; with the legacy dir renamed, `social check` still answers; old files deleted only after owner's yes | rotating tokens |
| S6 | bug | `social accounts discover --format human` prints JSON | `--format human` → table, not JSON; test red on current code | other commands' formats |

## Phase 2 — communication

| id | type | title | acceptance | not in it |
|---|---|---|---|---|
| S7 | feature | Collect comments, DMs and mentions into the journal | `h2t-ops social run communication --collect` → raw zone + step-2 records per item, no network write (test asserts no POST) | replies |
| S8 | feature | Reply to a comment after approval | needs D2; `run communication` drafts → `pending`; `social approve <id>` → reply posted, remote id in step 5; unattended run leaves it `pending` | DMs reply (separate step issue at phase plan), hiding comments |

## Phase 3 — content

| id | type | title | acceptance | not in it |
|---|---|---|---|---|
| S9 | feature | Publish a post, carousel or reel from Drive staging after approval | needs D2; `run content` for one plan item → `pending`; approve → Instagram media id in step 5; media reached by public Drive URL (spec §4.4) | Threads/FB publishing (step issues at phase plan), scheduling queue |

## Phase 4 — research

| id | type | title | acceptance | not in it |
|---|---|---|---|---|
| S10 | feature | Competitor profiles through business discovery | `run research --profile <handle>` → profile + recent media metrics into the research store (`h2t-ops research`), journal steps 1-3, 6 | hashtag search (limits unverified) |

## Phase 5 — ads

| id | type | title | acceptance | not in it |
|---|---|---|---|---|
| S11 | feature | Read campaign metrics and record recommendations | `run ads` → campaign metrics per account, report; no write call; any budget change is a step-5 `ask` (needs D2) | launching or editing campaigns |

## Order

D1 and D2 go to the owner first (they block code). Phase 1 runs in parallel with D2: it needs
neither. Phases 2-5 in spec order after D2. Each phase: own TDD plan → issues → Codex review
per task → live run → 4.1.x patch.

## Issue map

All in milestone M9: 4.2 (created 2026-11-19).

| id | issue | phase |
|---|---|---|
| D1 | #672 decision: snapshot file schema | decision |
| D2 | #673 decision: approval flow for outward actions | decision |
| — | #670 dated Instagram snapshot | 1 |
| S1 | #674 run insights on Threads accounts | 1 |
| S2 | #675 Facebook Page insights | 1 |
| S3 | #676 refresh Threads tokens | 1 |
| S4 | #677 run insights on a schedule | 1 |
| S5 | #678 secrets to secrets/shared | 1 |
| S6 | #679 bug: discover human format prints JSON | 1 |
| S7 | #680 collect comments, DMs, mentions | 2 |
| S8 | #681 reply to a comment after approval | 2 |
| S9 | #682 publish a post after approval | 3 |
| S10 | #683 competitor profiles via business discovery | 4 |
| S11 | #684 ad campaign metrics and recommendations | 5 |
