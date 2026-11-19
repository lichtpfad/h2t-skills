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

## Decisions

| id | question | outcome (owner, 2026-11-19) |
|---|---|---|
| D1 | Snapshot file schema (#672) | Outside the connector's boundary; closed. The connector gives an output contract (`run insights --json` with `schema_version`); consumers store it in their own database. #670 item 6 rewritten. |
| D2 | Approval flow (#673) | Chat run: the chat asks, the skill passes an explicit consent flag, step 4 records `approved_by`. No `approve` command, no queue. Unattended (server) runs: designed at the VPS stage; until then no outward action, record stays `pending`. Closed. |
| D3 | Database for the journal and raw data (#686) | A chat run returns data to the chat; a database only when a pipeline or the user stores data: SQLite locally, Postgres at the VPS stage. Journal stays JSONL until the first pipeline run (#677). Blocks nothing. Closed. |

## Rules every row follows

- Acceptance = a command with expected output **and** a red case: a fixture or input that
  makes the named test fail, which the change turns green.
- Network calls in tests are fakes; the live check is the last step of each phase plan.
- "via S13/S14" on a write row means: the action's rule verdict decides (`deny` → refused,
  exit 3; `ask` → refused without `--confirm`, exit 3; `auto` → runs), the per-account limit
  of S14 applies, and step 5 carries `source_ids`. Each such row's red case is "rule `ask`,
  no `--confirm` → no outward call" plus its own fixture.
- Output contract (spec §9 "Storage"): commands return versioned JSON (`schema_version`) to
  the caller. The journal (and its raw bodies) is written on every run. The result data is
  stored only with `--store`, and only into SQLite (S4b); no connector-owned report files.
  Scheduled runs always pass `--store` (S4a).
- Empty result is an error (connector standard, exit codes 0 ok, 1 provider, 2 usage,
  3 config, 4 auth, 5 not found, 6 network): "nothing found" exits 5 with a message, never
  an empty success.
- Cross-cutting uses (repurposing, regular reports, brand monitoring summaries) are skills on
  top of these processes (spec §4.3), not connector work, and not in this milestone.

## Phase 1 — insights complete (read-only)

| id | type | title | acceptance → expected | red case | not in it |
|---|---|---|---|---|---|
| — | feature | #670 account, post, audience data as versioned JSON | `run insights --account instagram:rejuve.healthstudio --json` → `schema_version`, groups 1-5, `unavailable` list with Meta error codes | fixture without `caption` → contract test fails on the missing field | snapshot files (closed #672) |
| S12 | feature | Insights return JSON and write no report file | `run insights --json` → JSON on stdout, journal + raw bodies written, nothing under `<data>/social/insights/` | test asserts no report file and a journal record; red on today's code, which always writes the report file | `--store` into SQLite (S4b) |
| S1 | feature | Insights on Threads accounts | `run insights --account threads:hou2touch --json` → posts + metrics, journal steps 1→2→3→4→6 linked | fixture in Meta's real Threads shape with a field dropped → test fails | Threads writes |
| S2 | feature | Facebook Page insights | `run insights --account facebook:hou2touch --json` → Page reach/engagement | fixture with a Meta permission error (`code 10`) → must land in `unavailable`; remove the handling → test fails | Page posting |
| S3 | feature | Refresh Threads tokens before expiry | `social tokens refresh` → new value via `secrets.write_env`; journal holds key name + expiry only | fixture token 2 days from expiry → refresh taken; fixture 50 days → skipped; a token value in the journal → test fails | Meta user token |
| S4a | feature | Schedule a process with Windows Task Scheduler | `social schedule add insights --daily 07:00` → `schtasks /Query /TN h2t-social-insights /V` shows the command `h2t-ops social run insights --trigger schedule --store`; that run's step 1 says `trigger: schedule` | fake `schtasks` runner: the registered command without `--store` or with a wrong argument order → test fails | VPS cron |
| S4b | feature | Scheduled runs store into SQLite | `run insights --trigger schedule --store` → journal, raw bodies and the report as rows in `<data>/social/social.db`, same schema as the JSONL records; a chat run (no `--store`) keeps JSONL only | round-trip test: write, read back, compare; a dropped column → fails; a scheduled run that leaves no rows → fails | Postgres (VPS stage) |
| S5 | chore | Secrets into `secrets/shared` | after the owner's yes the values are written to `~/.h2t/secrets/shared/{meta,threads}.env` (key names and lengths printed only); `h2t-ops doctor --json` reports per social secret key which place answered (`shared` or `legacy`, spec §9a) and says `shared` for all; `git grep meta-h2t-social-pages h2t_ops/` → no match (Page tokens are fetched per run) | test: shared first, legacy second — a key only in the legacy fixture still resolves and is reported `legacy`; a key in both → `shared` wins | removing the legacy fallback (package-wide, not social); rotation; deleting old files without the owner's yes |
| S6 | bug | `accounts discover --format human` prints JSON | `--format human` → a table | test on the human output, red on today's code | other commands |

## Shared door for outward actions (before phases 2, 3, 5)

| id | type | title | acceptance → expected | red case | not in it |
|---|---|---|---|---|---|
| S13a | feature | Rule check and consent flag in a chat run | `pytest tests/connectors/social/test_door.py -q` → passes with one test per verdict: `deny` → exit 3 "denied by rule <id>"; `ask` without `--confirm` → exit 3 "rule <id> asks: pass --confirm"; `ask` with it and `auto` → the action runs; step 4 records rule id, `approved_by`, time; step 5 without `source_ids` → refused | deleting the consent guard → the `ask` test fails; a rule without `origin` is refused at load (exists since #667, its test stays) | unattended runs (S13b) |
| S13b | feature | Unattended runs perform no outward action | `pytest tests/connectors/social/test_door.py -k unattended -q` → passes: a run with `--trigger schedule` records every outward action, `auto` included, as `pending` and makes no network write, until the VPS design exists (spec §9) | removing the guard → the `auto` case writes → test fails | VPS approval design |
| S14 | feature | Rate limits for writes | `pytest tests/connectors/social/test_limits.py -q` → passes: back-off on Meta rate errors (code 4, 17, 32, 613); per-account cap from config (Instagram 100 posts / 24 h, spec §9a) → the 101st publish exits 1 "cap reached" with a journal record | fixture with 100 publishes in the window → the next one must be refused | call-budget planner |
| S26 | feature | A manual task when the API cannot | `social manual <process> <action> --account … --text …` and any action marked unsupported (music in reels, Facebook Groups, Threads DMs, story stickers/links) → step 1 (trigger: the request), step 3 (the instruction text as the processed item), step 4 `decision: manual`, step 5 with `source_ids` = the step-3 record and the full instruction text; exit 0, no network write | test: an unsupported action must produce this chain, not an error; a step 5 without the step-3 source → refused by the journal | pushing tasks to a task system (spec §9) |

## Phase 2 — communication

| id | type | title | acceptance → expected | red case | not in it |
|---|---|---|---|---|---|
| S7a | feature | Collect Instagram and Facebook comments and mentions | `run communication --collect comments --account instagram:x` and `--collect mentions` (and `facebook:x`) → one raw-zone entry and one step-2 record per item, append-only | tests per kind and network: no POST in the path; a second run appends, never rewrites; an item without a step-2 record → fails | Threads (S7c), DMs |
| S7c | feature | Collect Threads replies and mentions | `run communication --collect comments --account threads:x` and `--collect mentions` → same contract as S7a | same tests as S7a | DMs (Threads has no DM API → S26) |
| S7b | feature | Collect Instagram and Facebook DMs | `run communication --collect dms --account instagram:x` and `--account facebook:x` → conversations + messages, one raw entry and step-2 record per message | same tests as S7a, with one fixture per network | Threads |
| S7d | feature | Poll communication on a schedule | `social schedule add communication --every 15m` (S4a mechanism) → `schtasks /Query /TN h2t-social-communication /V` shows `h2t-ops social run communication --collect comments,mentions,dms --trigger schedule --store`; a run collects only items newer than the last stored one | fake `schtasks` runner: missing `--store` → fails; a second run with no new items stores nothing new (dedupe test) | webhooks (VPS stage) |
| S8 | feature | Reply to a comment on Instagram, Facebook and Threads | via S13/S14: `social reply comment <id> --account <net>:<handle> --text … [--confirm]` → remote id in step 5, one test per network | rule `ask`, no `--confirm` → no outward call; fixture: Meta refuses the reply (comment deleted, code 100) → exit 1, step 5 records the error | DMs |
| S15 | feature | Hide a comment on Instagram, Facebook and Threads | via S13/S14: `social hide comment <id> --account <net>:<handle> [--confirm]` → hidden state read back, one test per network | rule `ask`, no `--confirm` → no outward call; fixture: hidden state still `false` after the call → exit 1, not success | deleting comments |
| S16 | feature | Reply to a DM within Meta's 7-day window | via S13/S14: `social reply dm <thread> --account <net>:<handle> --text … [--confirm]` → message id in step 5; outside the window → exit 3 with the reason | fixture 8 days old → must be refused; rule `ask`, no `--confirm` → no call | Threads, LinkedIn |

## Phase 3 — content

| id | type | title | acceptance → expected | red case | not in it |
|---|---|---|---|---|---|
| S9 | feature | Publish one Instagram image post from Drive staging | via S13/S14: `run content --item <id> [--confirm]` → media id in step 5; step 5's `source_ids` name the step-3 record, which names the content item; staging folder is a config value, files go through `h2t-ops drive` | missing staging config → config error; no public URL → refused; a step 5 without `source_ids` → journal refuses it | carousel, reel |
| S17a | feature | Instagram carousel | via S13/S14: `run content --item <id> [--confirm]` for an item with 2-10 media → carousel media id | fixture child container `ERROR` → run fails loud, journal records it | reel |
| S17b | feature | Instagram reel | via S13/S14: `run content --item <id> [--confirm]` for a video item → reel media id after the processing status is `FINISHED` | fixture status stuck `IN_PROGRESS` past the timeout → loud failure; music → S26 | music (no API → S26) |
| S25 | feature | Instagram story; Facebook Page story checked | via S13/S14: `run content --item <id> [--confirm]` for a story item → story media id; stickers and links → S26 manual task. Facebook Page stories are "unverified" in spec §4.4: the task checks the API live; if it publishes, add it here; if not, the command returns an S26 manual task and §4.4 is corrected | fixture container error → loud failure | stickers/links (manual) |
| S18a | feature | Publish text and image to Threads | via S13/S14: `run content --item <id> --account threads:x [--confirm]` → Threads media id | fixture container error → loud failure | carousel, video (S18b) |
| S18b | feature | Publish a carousel or video to Threads | via S13/S14: same command for a multi-media or video item → Threads media id after the container is `FINISHED` | fixture child container `ERROR` → loud failure | Threads replies |
| S19a | feature | Publish text, photo, multi-photo (carousel) and link to a Facebook Page | via S13/S14: `run content --item <id> --account facebook:x [--confirm]` → post id; a multi-photo item uploads unpublished photos, then one post with `attached_media` | fixture permission error → loud failure; one failed photo upload in a multi-photo item → no post, loud failure | video (S19b) |
| S19b | feature | Publish a video or reel to a Facebook Page | via S13/S14: same command for a video item → video id after upload completes | fixture upload error → loud failure | Groups (no API → S26) |
| S20 | feature | Publish at the planned time (own queue) | `social queue add --item <id> --at 2026-12-01T10:00` → listed by `social queue list`; `social schedule add queue --every 15m` (S4a mechanism) registers `h2t-ops social queue run --trigger schedule --store`; that run marks due items `pending` (S13b) until the VPS design; a chat run `social queue run [--confirm]` publishes each due item once via S13/S14 (each item gets its own rule verdict, step 4 and step 5 with `source_ids`); journal links queue entry → result | a second `queue run` must not publish it again (idempotency test) | native Meta scheduling field |

## Phase 4 — research

| id | type | title | acceptance → expected | red case | not in it |
|---|---|---|---|---|---|
| S10 | feature | Instagram competitor profiles through business discovery | `run research --profile instagram:<handle> --json` → profile + recent media metrics; journal steps 1-3, 6 | unknown handle fixture → `not found` (exit 5), not empty success | storing into the research store (a skill's call) |
| S27 | feature | Threads competitor profiles through profile discovery | prerequisite: the owner adds the Threads profile-discovery permission to the app (spec §4.4, human step); then `run research --profile threads:<handle> --json` → profile + recent posts | fixture permission error → config error naming the missing permission, not empty success | Threads trends |
| S21 | feature | Hashtag, keyword and trend research | `run research --hashtag <tag> --json` (Instagram), `run research --keyword <word> --json` and `run research --trends --json` (Threads) → top/recent media or trending topics. Threads trends are listed in spec §4.4 but not verified live: if the API has no trends endpoint, the command returns a manual task (S26) and spec §4.4 is corrected | Meta's 30-hashtags-per-7-days limit fixture → refused with the reason | trends not offered by any API |
| S22 | feature | Ad Library collection | `run research --ads <page or query>` → ads from `ads_archive` with dates and spend ranges | fixture with an empty result → exit 5 "no ads found for <query>", never an empty success | competitor spend estimates |

## Phase 5 — ads

| id | type | title | acceptance → expected | red case | not in it |
|---|---|---|---|---|---|
| S11 | feature | Read campaign metrics | `run ads --json` → campaigns, ad sets, spend, results per account; no write call | test asserts no POST | recommendations text (a skill's job) |
| S23 | feature | Change a campaign budget | via S13/S14, default `ask`: `social ads budget <campaign> <amount> [--confirm]` → new budget read back | rule `ask`, no `--confirm` → no call; amount above a configured ceiling → exit 3, no call | launching |
| S24 | feature | Launch or pause a campaign | via S13/S14, default `ask`: `social ads status <campaign> active|paused [--confirm]` → state read back | same guards as S23; fixture: campaign in review (`effective_status: IN_PROCESS`) → exit 1 with the status, not success | creating new campaigns from scratch |

## Order

D1, D2 and D3 are decided; nothing blocks code.
1. Phase 1, S12 first (it changes the output contract the others use).
2. S13a, S13b, S14, S26 (the shared door) before any write.
3. Phases 2 → 3 → 4 → 5 in spec order. S20 needs S4a.

Each phase: own TDD plan with a Codex plan gate → tasks with a Codex review each → live run
→ 4.1.x patch. 4.2.0 after phase 5 is live.

## Issue map

All in milestone M9: 4.2 (created 2026-11-19).

| id | issue | phase |
|---|---|---|
| D1 | #672 decision: snapshot file schema — closed, outside the boundary | decision |
| D2 | #673 decision: approval flow for outward actions — closed, decided | decision |
| D3 | #686 decision: database for journal and raw data — closed, decided | decision |
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
