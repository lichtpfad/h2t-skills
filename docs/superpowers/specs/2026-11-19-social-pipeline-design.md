---
title: "Social pipeline design"
status: "draft"
owner: "Stanislav Glazov"
date: "2026-11-19"
milestone: ""
issue: "none"
reason: "exploration-stage design; issues filed after the spec is approved and split into tasks"
---

# Social pipeline design

## 1. Intent

Own access to the author's social channels — Instagram, Facebook Pages, Threads, later
LinkedIn — without paid third-party schedulers and without hand-clicking Meta settings each
time. The skills work locally first; the same design moves to the VPS later as a scheduled
pipeline (ETL).

The connector is **delivery only**. Context (brand voice, goals, content plans), content
(assets and their per-channel versions) and decisions (what may happen without the author)
live outside it — the same split as skills / vault / Personal OS today.

Every outward action and every inbound record passes **one door**: a journal that records
what happened, from what, under which rule, with what result (provenance + governance).

## 2. Goals, non-goals, anti-goals

Goals
- One CLI surface (`h2t-ops social …`) for read and write on all connected channels.
- One six-step pipeline shape shared by communication, content, insights, research and ads.
- Approval rules that grow from work ("this kind — do it yourself"), stored as config.
- Nothing hardcoded: accounts, paths, rules, secret references live in config files.
- Where an API cannot do something, the pipeline produces a task for the author instead of
  failing.

Non-goals (this spec)
- Webhooks and real-time inbound (VPS stage).
- LinkedIn connector (research done; separate spec when started).
- Content generation quality, brand voice rules — they belong to skills and vault.
- A UI.

Anti-goals (failure even if it "works")
- The connector decides anything (what to post, whether to reply).
- An outward action with no journal record, or a journal record with no source.
- A token value in a config file, a log line or the journal.
- A rule added with no example of the case that produced it.

## 3. Verified state (2026-11-18/19)

All rows below were confirmed by API calls in the exploration session.

| Channel | Scope | Access |
|---|---|---|
| Instagram | 5 working profiles (@stan_glazov, @glazov_av, @hou2touch, @delicate_balance_of_terror, @rejuve.healthstudio); 3 more visible via Pages | Page tokens; 21 permissions granted incl. messages, comments, insights, contents, engagement, events, ads_read, ads_management |
| Facebook Pages | 14 | Page tokens, no time expiry |
| Threads | @hou2touch, @glazov_av | per-profile tokens from the Threads "User Token Generator"; scopes basic, content_publish, manage_insights, manage_replies, read_replies; ~60 days, refreshable |
| LinkedIn | — | research only (`research-synthesis:71170e433a9740e7e46eee50`) |

Meta app: "H2T Social" `1823599228879273`, dev mode, business Lichtpfad. Standard access is
enough because every account belongs to an app-role holder.

Secrets today sit in `~/.h2t/config/secrets/` (`meta-h2t-social.env`,
`meta-h2t-social-pages.json`, `meta-threads.env`). That is the 3.x location
(`h2t_ops/core/paths.py` `LEGACY["secrets.h2t"]`); 4.0 places are `secrets.shared` /
`secrets.local` under `~/.h2t/secrets/`. Moving them is a task in this work, done with the
author's confirmation.

## 4. Architecture

### 4.1 Layers

| Layer | Holds / does | Owner |
|---|---|---|
| Context | brand voice, goals, audiences, content plans | vault (`H2T_PATH_VAULT`) and POS |
| Content | assets and their per-channel versions, each linked to its plan item and source file | content store (place declared in config) |
| Door (journal + rules) | every outward action and every inbound record, with provenance; rule check before acting | `h2t_ops` social core |
| Delivery | API calls per network; returns ids, URLs, errors | `h2t-ops social` connector |

### 4.2 The pipeline: six steps, same for every process

| Step | What happens | Journal fields written |
|---|---|---|
| 1 Trigger | schedule, author request, or event | trigger kind, who/what started it |
| 2 Collect | connector reads from the network into the raw zone (append-only) | channel, account, endpoint, time |
| 3 Process | a skill with vault context produces a draft, finding or report | input record ids, context documents used |
| 4 Decide | rule check: `auto`, `ask`, or `deny` | rule id matched, who approved, when |
| 5 Act | through the door: connector call, **or a manual task when the API cannot** | result: remote id/URL or error; task id for manual |
| 6 Record | outcome back to the journal and, where useful, to context | link to the produced context note |

Steps 2 and 5 are the only ones that touch a network. Step 4 is the only place a decision
is made.

### 4.3 Processes mapped onto the pipeline

| Process | Trigger | Collect | Process | Act (outward) |
|---|---|---|---|---|
| Communication | new message/comment/mention (poll locally, webhook on VPS) | DMs, comments, mentions | classify, draft reply in the author's voice | reply, hide comment |
| Content | content-plan item due | assets from the content store | adapt per channel (reel, carousel, Threads text) | publish at the planned time |
| Insights | schedule | account and media metrics | compare, report | none; sending a report to a client is outward |
| Research | request | competitor profiles, tags/keywords, Ad Library | synthesis | none; result to the existing research store |
| Ads | schedule or request | campaign metrics | recommendations | budget change or launch — default `ask` |
| Onboarding (setup) | user request | current app state, granted permissions, token validity | gap list: what is missing for the wanted capabilities | change app settings, issue/exchange tokens — see §4.5 |

Cross-cutting uses of these processes, done by skills on top of the pipeline, not by the
connector:
- **Repurposing.** One source item becomes several per-channel versions (reel, IG post,
  Threads text, LinkedIn post); each version links back to the source item.
- **Regular reports.** Insights summaries on a schedule for the author or a client; sending
  one to a client is an outward action through the door.
- **Brand monitoring.** Mentions and tags of the author's accounts collected by the
  communication process and summarized for the author.

### 4.4 Capability map

Where a cell says "manual", step 5 creates a task for the author.

| Capability | IG | FB | Threads | LinkedIn |
|---|---|---|---|---|
| Post, carousel, reel | API | API | API | API (personal) |
| Stories | API publish; stickers/links manual | unverified | — | — |
| Scheduling | own queue | own queue (native field unverified) | own queue | own queue |
| Comments read/reply/hide | API | API | API | company page only |
| DMs | API (Human Agent: 7-day window) | API | — | manual |
| Mentions/tags of us | API | API | API | unverified |
| Own analytics | API (verified) | API | API | API |
| Competitor research | business discovery | — | profile discovery (permission not yet added) | — |
| Tag/keyword research | hashtag search (limits unverified) | — | keyword search, trends | — |
| Ads | API (`ads_*` granted) | API | — | separate access |

Media for Instagram publishing must be reachable by a public URL; a local file is not
accepted. The content layer therefore needs a public staging place (Google Drive for now, §9).

Not available through any official API (checked 2026-11-18): Instagram broadcast channels,
Facebook Groups, LinkedIn direct messages, music in Reels. For these, step 5 is always a
manual task.

### 4.5 Onboarding process (future plan)

The tool both sets up access and then operates it. Setup is a process of its own, planned
after the operating processes; this section records what the exploration session proved.

| Step | Automatable | How it was done on 2026-11-18/19 |
|---|---|---|
| Create Meta app, add use cases, link business | yes | Meta Social Technologies MCP (`devtools_app_create`, `devtools_app_use_cases_manage`, `devtools_app_business_manage`); its confirmation dialogs time out — retry once, then browser |
| Add permissions to a use case | browser only | no MCP tool; agent browser (`gstack browse`) on the "Customize" page, each "will affect other use cases" dialog confirmed |
| Issue a user token | human | Graph API Explorer: agent pre-selects permissions; the author logs in and consents |
| Exchange for a long-lived token, fetch Page tokens | yes | `oauth/access_token?grant_type=fb_exchange_token` with the app secret; `/me/accounts` |
| Create a Facebook Page for an IG account | human | agent attempt hit a Meta rate limit; Pages are created by hand |
| Threads: add tester, accept invite | agent adds, human accepts | App roles → Threads Tester; acceptance on threads.com → Settings → Account → Website permissions, logged in as that profile |
| Threads: issue token | agent clicks, human consents | Threads use case → Settings → User Token Generator; needs a browser where that profile is logged in |
| Verify | yes | read profile + last posts per account |

Human-only steps are always: logins, 2FA codes, consent screens, legal terms. Facts here
are dated; Meta changes its dashboards, so the onboarding plan re-verifies them first.

## 5. Configuration (no hardcode)

All paths resolve through `h2t_ops/core/paths.py` (the only module that knows where data
lives; ratchets in `tests/governance` hold that line). New code adds no `Path.home()`.

| File | Holds | Notes |
|---|---|---|
| `<config>/social/accounts.yaml` | per account: network, handle, remote ids, project id (from `domains.yaml`), secret reference as the **key name** only (e.g. `THREADS_TOKEN_ACME`; the package resolves the file) | never a token value; Page tokens are not stored — fetched each run from `/me/accounts` with the user token |
| `<config>/social/rules.yaml` | approval rules: match (process, action, account, content kind), verdict `auto/ask/deny`, added-on date, origin example | default for every action is `ask` |
| `<config>/paths.yaml` | external places this work needs (content store, public staging) if they are outside `~/.h2t` | via `h2t-ops paths set` |
| `<data>/social/` | raw zone (append-only), journal, queue | class `data` |

Rules grow during work: when the author says "this kind — do it yourself" (as in Telegram
today), the agent proposes one rule line with the triggering example; the author confirms;
the line is written. A rule without an origin example is rejected by the loader.

## 6. Journal and provenance

One record per event, append-only. Minimum fields:
`id, ts, process, step, channel, account, action, source_ids[], context_refs[], rule_id,
decision, approved_by, result{remote_id,url,error}, task_id`.

Invariants (each gets a test, §8):
1. No connector write without a journal record in state `approved` (or rule verdict `auto`).
2. Every journal record of step 5 names at least one source id.
3. No token value appears in the journal, config or logs.
4. Raw zone files are never rewritten.

## 7. Approaches considered

| Approach | Trade-off | Verdict |
|---|---|---|
| A. Fat connector: commands include scheduling, approval, templates | quick start; mixes delivery with decisions, nothing reusable for Gmail/Telegram | rejected |
| B. Thin connector + door core + skills (this spec) | more pieces; decisions and provenance in one place, connectors interchangeable | **chosen** |
| C. Third-party scheduler (Buffer, Later…) + thin glue | no Meta setup; paid, no DMs/ads depth, data outside | rejected earlier ("crazy pricing") |

The door is written so Gmail and Telegram can later route through it; that migration is out
of scope here.

## 8. Testing strategy (to be detailed in the plan)

- Contract tests per network client against recorded responses (no live calls in CI).
- Door invariants §6 as unit tests, each seen red before green.
- Config loader: a rule with no origin, an account with an inline token, an unknown project
  id — each refused.
- One live smoke command per network, run by hand, read-only (profile + last 3 posts), as the
  scratchpad checks did on 2026-11-19.
- Paths ratchet: no new `Path.home()` in the social code.

## 9. Author's answers (2026-11-19)

- **Addressee and date.** The author himself, and the h2t-skills pack (other users install
  it). Date: as soon as possible, no fixed deadline. Consequence: nothing author-specific in
  code or shipped defaults — accounts, places and rules come only from the user's config.
- **Order of processes.** All of them, one after another. First: insights (read-only),
  then communication, content, research, ads; onboarding (§4.5) after the operating
  processes.
- **Approval (`ask`).** When a skill drives the run, the author answers in the chat. Approval
  inside unattended automation is designed separately later; until then an unattended run
  never executes an `ask` action — it leaves it `pending`.
- **Manual tasks.** Outside the connector boundary; the destination is decided later. v1
  writes a journal record with `decision: manual` and the full instruction text; nothing is
  pushed to a task system.
- **Media staging.** Google Drive public links through `h2t-ops drive` for now.
- **Client approval (REjuve).** No such request from the client; out of scope.
- **Approval, refined (2026-11-19, #673).** A skill run from a chat asks the author in the
  chat; after "yes" it calls the connector with an explicit consent flag (the pattern of
  `h2t-ops gmail draft-send --confirm-send`). The connector records `approved_by` and the
  time in the step-4 record. No `approve` command and no queue. Unattended runs on a server
  follow a different principle, designed at the VPS stage; until then they perform no
  outward action and leave the record `pending`.
- **Storage (2026-11-19).** Social data on the author's side lives in a database, not in
  JSONL files; which database is decision #686. Consumers (the rejuve project) store what
  they take in their own database; the connector's side of that seam is an output contract
  (`run insights --json` with `schema_version`), not a file layout (#672 closed as outside
  the boundary).
- **Content store.** Google Drive for now, accessed only through `h2t-ops drive`; the folder
  is a config value, not code. The same place serves as media staging.

## 9a. Designer's calls (from the builder check, open to correction)

- **Door interface:** a Python API inside `h2t_ops` plus a thin CLI over it
  (`h2t-ops social journal|approve|run …`). The door writes journal records for every step,
  including steps with no network call; skills call the CLI.
- **Journal states:** `pending → approved | denied | expired → done | failed`. Superseded in
  part by §9 "Approval, refined": approval in a chat run is a consent flag recorded in
  step 4; `expired` belongs to the unattended (VPS) design.
- **Runtime:** one-shot commands (`h2t-ops social run <process>`), started by Windows Task
  Scheduler locally and cron on the VPS. No long-lived daemon in v1.
- **Rate limits in v1:** back-off on API rate errors, plus one rule-level cap per account
  (Instagram publishes at most 100 posts per 24 h `[B: Meta docs]`). No call-budget planner.
- **Secrets migration:** files move to `secrets.shared` (they sync between the author's
  machines). During the transition the loader reads `secrets.shared` first, then the 3.x
  place, and `doctor` reports which one answered. Superseded by the plan
  (2026-11-19): no JSON secret is referenced; Page tokens are fetched per run, so
  `meta-h2t-social-pages.json` is retired after the migration.
- **Accounts file:** generated by `h2t-ops social accounts discover`, then edited by the
  author. The three Page-visible IG profiles outside the five working ones are listed with
  `enabled: false`.

## 10. Left to the builder

- Module layout inside `h2t_ops/connectors/social/` and the door core.
- ~~Journal storage format (JSONL or SQLite)~~ — taken back by the author 2026-11-19: a
  database (§9 "Storage"); the engine is decision #686. The schema still moves to
  Postgres on the VPS unchanged.
- Token refresh mechanics (Threads `th_refresh_token`, LinkedIn later).
