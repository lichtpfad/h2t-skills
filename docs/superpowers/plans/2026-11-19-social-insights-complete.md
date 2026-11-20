---
title: "Social phase1 insights"
status: "draft"
date: "2026-11-19"
milestone: "M9: 4.2"
issue: "689"
---

# Social phase 1 (insights, read-only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `h2t-ops social run insights` returns versioned JSON instead of writing report files, works for Threads, can store scheduled runs into SQLite, can be registered in Windows Task Scheduler, refreshes Threads tokens, and `doctor` says where each social secret was read from.

**Architecture:** The connector stays delivery-only (spec §1). The output contract is a result dict with `schema_version`; the journal (JSONL) is written on every run; `--store` mirrors the same journal, raw and result rows into `<data>/social/social.db` through `store.connect_sqlite`. New modules: `db.py` (SQLite mirror), `schedule.py` (schtasks), `tokens.py` (Threads refresh).

**Tech Stack:** Python 3.12, argparse, stdlib `sqlite3` via `h2t_ops.core.store`, `subprocess` for `schtasks`, pytest with fake HTTP sessions and fake runners.

**Spec:** `docs/superpowers/specs/2026-11-19-social-pipeline-design.md`. Stage plan: `docs/superpowers/plans/2026-11-19-social-processes-to-4-2.md` (rows S12, S1, S6, S4b, S4a, S3, S5).

## Scope of this plan

In: S12 #689, S1 #674, S6 #679, S4b #694, S4a #677, S3 #676, S5 #678 (code part), plus the output-schema section #670 requires in the spec.

Out, to the next plan: #670 items 1-5 (account daily metrics, saves/shares/caption, audience, stories, comment text) and S2 #675 (Facebook Page insights). Their Meta metric names are unverified (#670 says so; Page metrics change often). They need a live read-only probe that records real response shapes as fixtures **before** tests are written. This conflicts with the stage-plan rule "the live check is the last step"; the ruling is: for those two, a live probe comes first and a live check comes last.

Human-gated steps (Task 9): every live run, registering a real scheduled task, writing a refreshed token, moving secrets. Subagents never run them.

## Global Constraints

- Work in worktree `C:/dev/h2t-skills-wt-social-phase1`, branch `feat/social-phase1-insights`. Tests: `C:/dev/h2t-skills-wt-social-phase1/.venv/Scripts/pytest tests/connectors/social tests/governance -q -p no:cacheprovider` (baseline 2026-11-19: 369 passed, 2 skipped). Lint: `.venv/Scripts/ruff check plugins/ lib/ h2t_ops/ tests/ scripts/` → 0 findings.
- `commands.py`: argparse only at module scope; clients, yaml, sqlite and subprocess imported inside handlers.
- Every path through `h2t_ops/core/paths.py`; no `Path.home()`. Every file write through `h2t_ops.core.store`; SQLite only through `store.connect_sqlite(path, place="data")`. Governance ratchets stay at `"writes": 0, "sqlite": 0`.
- Exit codes: 0 ok, 1 provider, 2 usage, 3 config, 4 auth, 5 not found, 6 network. Empty result is an error (exit 5), never an empty success.
- No token value in the journal, config, output or logs (spec §6 invariant 3). A token obtained at runtime is registered with `journal.register_secret` before any body containing it is journaled.
- Tests make no network calls and run no real `schtasks`. Each new test is seen red before green (`.claude/rules/verification.md`).
- Explicit staging: `git add <paths>`, never `-A`. Commit format `type: description (#N)`.
- `schema_version` value: `"h2t_social_insights/v1"` (house style of `KIND_*` in `h2t_ops/setup/legacy.py`). Adding a key keeps v1; removing or renaming a key needs v2.

## Review Focus

1. `--account` with an unknown or disabled id silently filters to nothing and exits 0 with empty results. Expected: exit 5 naming the id. Test in Task 2.
2. One account fails after others succeeded. With stdout-only output the earlier accounts' data is gone. Ruling: the whole run fails loud (non-zero exit, step-6 failure record); the raw bodies already journaled stay. Test in Task 2.
3. "No posts with metrics" raises `ProviderError` (exit 1) today; the stage plan says "nothing found exits 5". Ruling: `NotFoundError` (exit 5). Test in Task 2.
4. A post from Meta missing `id` or `timestamp` crashes with `KeyError`. Expected: `ProviderError` naming the account, post and field. Test in Task 3.
5. `secrets.write_env` replaces the whole provider file. A token refresh that writes one key would delete the other Threads keys. Expected: other keys survive. Test in Task 7.

---

### Task 1: Output contract section in the spec

**Files:**
- Modify: `docs/superpowers/specs/2026-11-19-social-pipeline-design.md` (new section `## 9b. Insights output contract (v1)` after §9a)

- [ ] **Step 1: Write the section.** It states, as a table or list:
  - `result.schema_version = "h2t_social_insights/v1"`; it sits inside the envelope's `result`, not in the envelope.
  - `result.run_id`: the journal run id.
  - `result.accounts`: mapping `<network>:<handle>` → `{network, summary, posts}` and, for Instagram only, `online_followers_hour_as_reported`.
  - `summary`: the output of `insights.summarize` (keys `posts, skipped, median_reach, by_weekday, by_hour_band, top`).
  - `posts`: list of `{id, timestamp, permalink, network, metrics}`; `metrics` is `null` when Meta gave no insights for the post.
  - `result.skipped_accounts`: mapping id → reason.
  - Versioning rule: adding a key keeps v1; removing or renaming one needs v2. #670 adds the groups `account_daily`, `audience`, `stories`, `comments` and the list `unavailable` (`{account, group, metric, code, message}`) as additions to v1.
  - Storage: no report files; `--store` writes rows to `<data>/social/social.db` (Task 5).
- [ ] **Step 2: Verify.** `uv run h2t-docs-lint doctor` reports no new finding for the spec file.
- [ ] **Step 3: Commit.** `git add docs/superpowers/specs/2026-11-19-social-pipeline-design.md docs/superpowers/plans/2026-11-19-social-insights-complete.md` → `docs(social): insights output contract v1 in the spec (#670)`

### Task 2: Insights return versioned JSON, no report file (S12 #689)

**Files:**
- Modify: `h2t_ops/connectors/social/insights.py`
- Test: `tests/connectors/social/test_insights.py`, `tests/connectors/social/test_commands.py` (the `run insights --json` envelope test)

**Interfaces:**
- Produces: `SCHEMA_VERSION = "h2t_social_insights/v1"` in `insights.py`; `insights.run(account_ids, limit, client_factory=None, trigger="cli", store=False) -> dict` returning the §9b shape. `store` is accepted here and used in Task 5.

- [ ] **Step 1: Rewrite the report-file tests as red cases.** In `test_insights.py`, replace the assertions at lines ~167-169 and the test `test_report_write_failure_ends_with_one_step6_record` (~218) with:
  - `test_run_writes_no_report_file`: after a successful run, `(social_data / "social" / "insights").exists()` is `False`; the journal has a step-6 record for the account with `schema_version == "h2t_social_insights/v1"` and `posts == 2`.
  - `test_result_is_versioned`: `out["schema_version"] == "h2t_social_insights/v1"`, `out["run_id"]` equals the journal run id, `out["accounts"]["instagram:acme"]["summary"]["posts"] == 2`, `len(out["accounts"]["instagram:acme"]["posts"]) == 2`.
  - `test_unknown_account_is_not_found`: `run(["instagram:nope"], 5, ...)` raises `NotFoundError` whose message contains `instagram:nope`; same for a disabled account id.
  - `test_no_posts_with_metrics_is_not_found`: all media without insights → `NotFoundError`.
  - `test_second_account_failure_fails_the_run` (regression cover, already green today, not a red case): two accounts, the second client raises `ProviderError` → `run` raises; journal ends with one step-6 failure record for the second account; no result is returned.
  - Update the `run insights … --json` envelope test in `test_commands.py` (it asserts `env_["result"]["reports"]…`) to read `env_["result"]["accounts"]["instagram:acme"]["summary"]["posts"] == 2`.
- [ ] **Step 2: Run, expect red.** `pytest tests/connectors/social/test_insights.py tests/connectors/social/test_commands.py -q` → the new tests FAIL (report file exists, no `schema_version`, `ProviderError` instead of `NotFoundError`).
- [ ] **Step 3: Implement.** In `insights.run`: drop the `store.replace` report write and the `paths`/`json` imports it needed; per account build `{"network", "summary", "posts", ["online_followers_hour_as_reported"]}`; step-6 record carries `schema_version` and `posts` (count), not `report`. Raise `NotFoundError` when `account_ids` names an id that is not an enabled account (before `new_run`) and when no post has metrics. Return `{"schema_version", "run_id", "accounts", "skipped_accounts"}`.
- [ ] **Step 4: Run, expect green.** Same command → PASS; then the full Global-Constraints test command → all pass.
- [ ] **Step 5: Commit.** `feat(social): insights return versioned JSON, no report file (#689)`

### Task 3: Threads insights run, contract on Meta's real shape (S1 #674)

The Threads branch already exists in `insights._collect`; this task pins its contract.

**Files:**
- Modify: `h2t_ops/connectors/social/insights.py` (`_collect`)
- Test: `tests/connectors/social/test_insights.py` (uses `fixtures/threads_posts_1.json`, `fixtures/threads_insights.json` through the real `ThreadsClient` with the `Session` fake pattern of `test_commands.py`)

- [ ] **Step 1: Write tests.**
  - `test_threads_run_links_journal_chain`: one Threads account, real `ThreadsClient` over a fake session serving the two fixtures. Assert the run's journal steps in order are `1, 2…, 3, 4, 6`; the step-3 `source_ids` equal the ids of the step-2 records of that account; `out["accounts"]["threads:acme"]["summary"]["median_reach"]` equals the `views` value in `threads_insights.json`.
  - `test_post_without_timestamp_is_provider_error` (parametrize over `instagram` and `threads`, and over dropped field `id` / `timestamp`): a fixture post without the field → `ProviderError` whose message contains the account id and the field name.
- [ ] **Step 2: Run, expect red** on the dropped-field case (`KeyError` today).
- [ ] **Step 3: Implement** a check in `_collect`: every media row must have `id` and `timestamp`, else `ProviderError(f"{account.id}: post {m.get('id', '?')} has no {field}")`.
- [ ] **Step 4: Run, expect green**, then the full test command.
- [ ] **Step 5: Commit.** `feat(social): Threads insights contract and post field check (#674)`

### Task 4: `accounts discover --format human` prints a table (S6 #679)

**Files:**
- Modify: `h2t_ops/connectors/social/commands.py`
- Test: `tests/connectors/social/test_commands.py`

**Interfaces:**
- Produces: `_discover_table(result: dict) -> str` in `commands.py`.

- [ ] **Step 1: Write the test** `test_discover_human_is_a_table`: run `social accounts discover` (no `--json`, default `--format human`) over the existing `_routes()` session. Assert stdout does not start with `{`, has a header line containing `id`, `enabled` and `token_key`, has one line containing `instagram:acme`, and ends with a line saying the file was not written and to pass `--write`. `--json` output for the same command is unchanged (existing tests).
- [ ] **Step 2: Run, expect red** (stdout is JSON today).
- [ ] **Step 3: Implement.** In `run()`, when `args.accounts_cmd == "discover"` and `not args.as_json and args.fmt == "human"`, return `_discover_table(result)`: rows from `yaml.safe_load(result["yaml"])["accounts"]` as `<network>:<handle>  <enabled>  <token_key>`, then each note, then `written: <path>` or `not written: pass --write to save <path>`. `--format md` keeps today's output.
- [ ] **Step 4: Run, expect green**, then the full test command.
- [ ] **Step 5: Commit.** `fix(social): accounts discover human format prints a table (#679)`

### Task 5: `--store` mirrors scheduled runs into SQLite (S4b #694)

**Files:**
- Create: `h2t_ops/connectors/social/db.py`
- Modify: `h2t_ops/connectors/social/journal.py`, `insights.py`, `commands.py` (`run insights` gets `--trigger {cli,schedule}` default `cli`, and `--store`)
- Test: `tests/connectors/social/test_db.py`; add to `test_insights.py`, `test_commands.py`

**Interfaces:**
- Produces in `db.py`: `db_path() -> Path` (`paths.data_dir() / "social" / "social.db"`); `put_journal(rec: dict) -> None`; `put_raw(rec: dict) -> None`; `put_result(run_id: str, account: str, body: dict) -> None`; `read_journal(run_id: str) -> list[dict]`; `read_raw(run_id: str) -> list[dict]`; `read_results(run_id: str) -> list[dict]`. Tables `journal`, `raw`, `results`, created on first use.
- `journal` table columns: `id TEXT PRIMARY KEY, ts, run_id, process, step INTEGER, channel, account, action, source_ids, context_refs, rule_id, decision, approved_by, task_id, result, extra`. List/dict fields and `extra` (every record key not in that list, e.g. `trigger`, `endpoint`, `schema_version`) are JSON text. `read_journal` returns dicts equal to what `journal.record` returned.
- `raw` table: `id TEXT PRIMARY KEY, ts, run_id, process, account, endpoint, payload` (JSON). `results`: `run_id, account, schema_version, body` (JSON), primary key `(run_id, account)`.
- Produces in `journal.py`: `new_run(process, trigger, store=False)`. A run opened with `store=True` is remembered in a module set; `record` and `write_raw` then also call `db.put_journal` / `db.put_raw` with the same dict, after the JSONL append and its secret check.
- `insights.run(..., store=True)` opens its run with `store=True` and calls `db.put_result` per account.

- [ ] **Step 1: Write tests.**
  - `test_db.py::test_journal_round_trip`: a record with every column filled plus `trigger` and `endpoint` extras → `put_journal` → `read_journal` returns an equal dict. Red case to see once: drop one column from the table definition → this test fails.
  - `test_db.py::test_raw_and_result_round_trip`.
  - `test_insights.py::test_store_run_leaves_rows`: `run(..., trigger="schedule", store=True)` → `read_journal(run_id)` has steps 1, 2, 3, 4, 6; `read_raw(run_id)` non-empty; `read_results(run_id)` has one row with `schema_version == "h2t_social_insights/v1"`; JSONL journal also has the run.
  - `test_insights.py::test_chat_run_writes_no_db`: `store=False` → `db_path()` does not exist.
  - `test_commands.py`: `run insights --trigger schedule --store --json` → step 1 has `trigger: "schedule"`, rows in the db.
- [ ] **Step 2: Run, expect red.**
- [ ] **Step 3: Implement** `db.py` with `store.connect_sqlite(db_path(), place="data")`; wire `journal` and `insights`; add the two CLI flags and forward them in `commands.run`: `insights.run(args.accounts, args.limit, trigger=args.trigger, store=args.store)` (today it passes only `args.accounts, args.limit`).
- [ ] **Step 4: Run, expect green**, then the full test command. If `tests/governance/test_sandbox_covers_every_writer.py` names `connectors/social/db.py`, add a case to `tests/governance/sandbox_cases.py` in the style of the existing ones.
- [ ] **Step 5: Commit.** `feat(social): --store mirrors runs into SQLite (#694)`

### Task 6: Register a process in Windows Task Scheduler (S4a #677)

**Files:**
- Create: `h2t_ops/connectors/social/schedule.py`
- Modify: `h2t_ops/connectors/social/commands.py` (`social schedule add <process> --daily HH:MM`, `social schedule remove <process>`)
- Test: `tests/connectors/social/test_schedule.py`

**Interfaces:**
- Consumes: Task 5 flags `--trigger schedule --store`.
- Produces: `TASK_PREFIX = "h2t-social-"`; `PROCESSES = ("insights",)`; `command(process: str) -> list[str]`; `add(process: str, daily: str, runner=subprocess.run, platform=sys.platform) -> dict`; `remove(process: str, runner=subprocess.run, platform=sys.platform) -> dict`.

- [ ] **Step 1: Write tests** with a fake runner that records argv and returns `returncode=0`:
  - `test_add_registers_store_command`: `add("insights", "07:00", runner=fake, platform="win32")` → argv is `["schtasks", "/Create", "/TN", "h2t-social-insights", "/TR", <tr>, "/SC", "DAILY", "/ST", "07:00", "/F"]`, and `<tr>` ends with `social run insights --trigger schedule --store` in that order. Red case: a `command()` without `--store` or with `--store` before `--trigger` fails it.
  - `test_add_quotes_exe_with_space`: `shutil.which` patched to `C:/Program Files/x/h2t-ops.exe` → `<tr>` starts with `"C:/Program Files/x/h2t-ops.exe"`.
  - `test_bad_time_and_process_are_usage_errors`: `"7am"` and `"25:00"` → `UsageError`; process `"ads"` → `UsageError` listing `insights`.
  - `test_not_windows_is_usage_error`: `platform="linux"` → `UsageError` saying cron comes at the VPS stage; the runner is not called.
  - `test_schtasks_failure_is_provider_error`: runner returns `returncode=1, stderr="Access is denied."` → `ProviderError` containing that text.
  - `test_missing_exe_is_config_error`: `shutil.which` returns `None` → `ConfigError`.
  - `test_remove`: argv `["schtasks", "/Delete", "/TN", "h2t-social-insights", "/F"]`.
- [ ] **Step 2: Run, expect red.**
- [ ] **Step 3: Implement.** `command()` = `[shutil.which("h2t-ops"), "social", "run", process, "--trigger", "schedule", "--store"]`; `/TR` is `subprocess.list2cmdline(command(process))`; `add` returns `{"task", "command", "daily"}`.
- [ ] **Step 4: Run, expect green**, then the full test command.
- [ ] **Step 5: Commit.** `feat(social): schedule a process with Task Scheduler (#677)`

### Task 7: Refresh Threads tokens before expiry (S3 #676)

**Files:**
- Create: `h2t_ops/connectors/social/tokens.py`
- Modify: `h2t_ops/connectors/social/threads.py` (add `refresh`), `commands.py` (`social tokens refresh`)
- Test: `tests/connectors/social/test_tokens.py`

**Interfaces:**
- Produces: `ThreadsClient.refresh() -> tuple[dict, list[dict]]`: GET `<scheme://host of api_base("threads")>/refresh_access_token` with `grant_type=th_refresh_token` and the current token; returns `{"access_token", "expires_in"}`. Registers the new token as a secret (`self._secrets` and `journal.register_secret`) before returning.
- Produces: `THRESHOLD_DAYS = 7`; `expiry_path() -> Path` (`paths.state_dir() / "social" / "token-expiry.json"`, written with `store.replace(..., place="state")`, holds `{key_name: ISO expiry}` only); `refresh(now: datetime | None = None, client_factory=None) -> dict` returning `{"refreshed": [{"key", "expires_at"}], "skipped": [{"key", "expires_at"}]}`.
- Expiry is **not** kept in a secrets file: a `THREADS_TOKEN_*_EXPIRES` key would be read as an account by `secrets.keys_with_prefix`.

- [ ] **Step 1: Write tests** (fake client factory; `secrets.write_env` and `secrets.shared_env_values` patched or pointed at `tmp_path`):
  - `test_refresh_near_expiry`: recorded expiry 2 days ahead → refreshed; `write_env("threads", …)` received the new value under the same key; new expiry = now + `expires_in`.
  - `test_skip_far_from_expiry`: 50 days ahead → skipped, no client call.
  - `test_unknown_expiry_is_refreshed`: no recorded expiry → refreshed and recorded.
  - `test_other_threads_keys_survive`: shared `threads.env` holds `THREADS_TOKEN_A` and `THREADS_TOKEN_B`; refreshing A writes both keys, B unchanged.
  - `test_token_value_never_in_journal`: the journal and the expiry file contain the key name and expiry, not the old or new token value. Red case: put the value into the step-6 record → `SecretInRecord` / test fails.
  - `test_threads_refresh_url`: `ThreadsClient.refresh` with a fake session calls `https://graph.threads.net/refresh_access_token` with `grant_type=th_refresh_token`.
- [ ] **Step 2: Run, expect red.**
- [ ] **Step 3: Implement.** One journal run per call, process `"tokens"`; raw bodies through `journal.keep` (the `access_token` field is redacted by `_redact`); a step-6 record per key with `key` and `expires_at`. Write `{**secrets.shared_env_values().get("threads.env", {}), key: new}` with `secrets.write_env("threads", …)`.
- [ ] **Step 4: Run, expect green**, then the full test command.
- [ ] **Step 5: Commit.** `feat(social): refresh Threads tokens before expiry (#676)`

### Task 8: connectors-check reports where each social secret was read (S5 #678, code part)

Ruling: the stage plan names `h2t-ops doctor --json`, but top-level `doctor` takes no flags and prints a text report by the owner's decision #451 (`h2t_ops/cli.py` `_doctor`). The JSON connector status is `h2t-ops setup connectors-check --json` (`connector_matrix` in `h2t_ops/setup/legacy.py`, kind `h2t_connectors_check/v1`). The social entry goes there; `doctor` is not changed.

**Files:**
- Modify: `h2t_ops/core/secrets.py` (add `source`), `h2t_ops/setup/legacy.py` (`connector_matrix`, next to the `MEETGEEK_API_KEY` / `GRANOLA_API_KEY` entries)
- Test: `tests/core/test_secrets_source.py`, `tests/test_setup_doctor_checks.py` (it covers `connector_matrix`)

**Interfaces:**
- Produces: `secrets.source(key: str) -> str | None` returning `"env"`, `"shared"`, `"legacy"` or `None`, in the same order as `secrets.get`.
- `connector_matrix` gets a `social` entry: `checks` maps each key name (`secret_key("meta_user_token")`, `secret_key("meta_app_secret")`, every `THREADS_TOKEN_*` from `keys_with_prefix`) to its `source` or `"missing"`; `status` is `ready` when the Meta user token or any Threads key is present.

- [ ] **Step 1: Write tests.** `source` with a key only in a legacy fixture → `"legacy"`; in both → `"shared"`; in neither → `None`; in env → `"env"`. `connector_matrix()` for a sandbox with one shared and one legacy social key shows both sources under `social.checks`.
- [ ] **Step 2: Run, expect red.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run, expect green**, then the full test command plus `tests/core tests/setup`. Check `git grep meta-h2t-social-pages h2t_ops/` → no match (true at plan time).
- [ ] **Step 5: Commit.** `feat(social): doctor names the source of each social secret (#678)`

### Task 9: Live checks (human-gated; controller with the owner, not a subagent)

Each line needs the owner's "yes" in the chat first. Run from the worktree with `uv run h2t-ops …`.

- [ ] `social run insights --account instagram:hou2touch --json` → `schema_version`, posts > 0, nothing new under `<data>/social/insights/`.
- [ ] `social run insights --account threads:hou2touch --json` → posts with `views`; `social journal --run <id>` shows steps 1→2→3→4→6.
- [ ] `social accounts discover` → a table.
- [ ] `social run insights --trigger schedule --store --json` → rows in `<data>/social/social.db`.
- [ ] Owner yes: `social schedule add insights --daily 07:00`; `schtasks /Query /TN h2t-social-insights /V` shows the command; after the run, step 1 says `trigger: schedule`. Owner decides whether to keep or `schedule remove` it.
- [ ] Owner yes: `social tokens refresh` → key names and expiry printed, `check` still passes for both Threads accounts.
- [ ] Owner yes: move Meta and Threads secrets to `secrets/shared` (first `h2t-setup sync` dry run, if it covers them; otherwise `write_env` per provider, printing names and lengths only); `h2t-ops setup connectors-check --json` → `shared` for every social key.
- [ ] Ship as a 4.1.x patch per the stage plan.
