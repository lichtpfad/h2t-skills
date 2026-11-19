---
title: "Social insights foundation"
status: "draft"
date: "2026-11-19"
milestone: ""
issue: "none"
reason: "issues filed when the author approves the plan"
---

# Social Insights Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `social` connector in h2t-ops that reads Instagram, Facebook Pages and Threads
analytics through one journaled door, driven only by the user's config.

**Architecture:** Thin HTTP clients per network (Meta Graph, Threads Graph) under
`h2t_ops/connectors/social/`; a network-free core in the same package — config loader,
journal with provenance, rule check — that every command goes through. First process:
insights (read-only), run as a one-shot command.

**Tech Stack:** Python ≥3.10, `requests` (lazy import, as dropbox), `pyyaml`, pytest with
recorded JSON responses. All file writes through `h2t_ops.core.store`, all paths through
`h2t_ops.core.paths`, all secrets through `h2t_ops.core.secrets`.

**Spec:** `docs/superpowers/specs/2026-11-19-social-pipeline-design.md`

## Global Constraints

- Nothing author-specific in code, tests or shipped defaults: no handles, ids, page names,
  timezone. Test fixtures use invented ids (`ig_111`, `page_222`) and handles (`acme`).
- Paths: only `paths.config_dir()`, `paths.data_dir()`; no `Path.home()`, no `~` literals
  (governance ratchets in `tests/governance/test_storage_ratchets.py` stay green).
- Writes: only `store.append` / `store.replace` / `store.create` with `place="config"` or
  `place="data"`; `test_no_new_module_writes_outside_store` stays green.
- Secrets: only `secrets.get(KEY)`. Providers `meta` (prefix `META_`) and `threads` (prefix
  `THREADS_`). A token value never appears in config, journal, raw files, logs or CLI output.
- Every network-touching command is read-only in this plan. No POST to any network.
- Network versions and base URLs live in `h2t_ops/resources/social/defaults.yaml`
  (`meta_graph: https://graph.facebook.com/v27.0`, `threads_graph: https://graph.threads.net/v1.0`),
  overridable per user in `accounts.yaml` key `api`.
- Envelope and exit codes per the Connector Standard (0 ok, 1 provider, 2 usage, 3 config,
  4 auth, 5 not found, 6 network).
- Journal is append-only JSONL; raw zone is append-only JSONL; neither is ever rewritten.

**Refinement of spec §5 (secret references):** the spec says `file + variable`. The package
already resolves a key to its file (`secrets.get`), so `accounts.yaml` names the **key only**
(`token_key: THREADS_TOKEN_ACME`). Page tokens are not stored: they are fetched at run time
from `GET /me/accounts` with `META_USER_TOKEN`; the JSON file of page tokens is retired.

**Not in this plan (next plans):** Facebook Page insights (accounts are discovered, metrics
come later); adding rules from chat (`decide()` exists, a `rules add` command comes with the
communication process); any write to a network; Threads token refresh; LinkedIn.

## Review Focus

1. A Meta error code 190 (expired/revoked token) — the user expects exit 4 with "renew the
   token" naming the key, not a stack trace. → Task 4 test `test_expired_token_is_auth_error`.
2. Rate limit (Meta codes 4, 17, 32, 613; HTTP 429) — expects one back-off retry, then exit 1
   with "rate limited, retry later"; never a silent partial report. → Task 4
   `test_rate_limit_retries_once_then_fails`.
3. A post whose insights are unavailable (too old, story, permissions) — expects the report to
   count it as skipped, not to abort, and the skipped count is printed. → Task 6
   `test_media_without_insights_is_skipped_and_counted`.
4. An account with zero posts or an empty metrics answer — expects exit 1 "no data",
   not an empty report presented as success. → Task 6 `test_empty_media_fails_loud`.
5. `online_followers` hours: Meta's timezone for them is unverified — the report labels them
   "hour as reported by Meta" and does not convert. → Task 6
   `test_online_followers_hours_are_not_converted`.

## Spec traceability

Each in-scope spec requirement maps to the test that proves it. A requirement with no test
name here is out of scope for this plan. The executor's completion report reruns these tests
by name and pastes the output.

| Spec | Requirement | Task | Test |
|---|---|---|---|
| §1, §4.1 | connector is delivery only; clients called only inside a journaled run | 7 | `test_no_client_import_outside_run_modules`, `test_discover_and_check_are_journaled` |
| §2 | nothing hardcoded; accounts/rules from config | 2 | `test_missing_accounts_file_is_config_error`, `test_api_base_override` |
| §2 anti-goal, §6 inv. 3 | no token in config, journal, raw, errors, CLI output | 2, 3, 4, 7 | `test_inline_token_is_refused`, `test_secret_value_never_written`, `test_raw_payload_tokens_are_redacted`, `test_registered_runtime_secret_is_refused`, `test_expired_token_is_auth_error`, `test_cli_output_and_errors_never_show_tokens` |
| §1 "every inbound record" | each HTTP response journaled | 4, 7 | `test_raw_has_one_body_per_call`, `test_discover_and_check_are_journaled` |
| §2 anti-goal, §5 | rule without origin refused | 2 | `test_rule_without_origin_is_refused` |
| §4.2 | journal record for every step (5 omitted only on `noop`) | 3, 6 | `test_run_writes_provenance_chain`, `test_decide_defaults_to_ask_and_records_step4` |
| §5 | rule match by process, action, account, kind; default `ask` | 3 | `test_decide_*` |
| §6 inv. 1 | no write without `auto`/`approved` | 3 | `test_require_allowed_refuses_ask_and_deny` |
| §6 inv. 2 | step 5 needs source ids | 3 | `test_step5_without_source_ids_is_refused` |
| §6 inv. 4 | raw and journal append-only | 3 | `test_records_are_appended_never_rewritten` |
| §9 | ships with nothing author-specific | all | Global Constraints; reviewer greps fixtures for real handles/ids |
| §9a | accounts generated by discover, new ones disabled | 7 | `test_discover_merges_and_keeps_enabled` |
| §9a | rate limits: back-off then fail | 4 | `test_rate_limit_retries_once_then_fails` |

Every new test is seen red before green (`.claude/rules/verification.md`).

---

### Task 1: Providers, key listing, defaults file

**Files:**
- Modify: `h2t_ops/core/providers.py` (tables `CONNECTOR_PROVIDERS`, `KEY_PREFIX`)
- Modify: `h2t_ops/core/secrets.py` — add `keys_with_prefix`
- Create: `h2t_ops/resources/social/defaults.yaml`
- Test: `tests/connectors/social/test_providers.py`, `tests/core/test_secrets_keys_with_prefix.py`

**Interfaces:**
- Produces: providers `meta`, `threads`; `CONNECTOR_PROVIDERS["social"] == ("meta", "threads")`.
- Produces: `secrets.keys_with_prefix(prefix: str) -> list[str]` — sorted **names** of keys
  that have a non-empty value in the environment, the new files or the 3.x ladder (same
  sources and order as `get`). Never returns values. This is the only way the social code
  enumerates Threads keys.

- [ ] **Step 1: Write the failing tests**

```python
from h2t_ops.core import providers

def test_social_providers_and_prefixes():
    assert providers.CONNECTOR_PROVIDERS["social"] == ("meta", "threads")
    assert providers.provider_of_key("META_USER_TOKEN") == "meta"
    assert providers.provider_of_key("THREADS_TOKEN_ACME") == "threads"

def test_keys_with_prefix_lists_names_from_new_and_legacy(sandboxed_secrets):
    # shared/threads.env: THREADS_TOKEN_A=x, THREADS_TOKEN_EMPTY=
    # legacy secrets.h2t/other.env: THREADS_TOKEN_B=y
    assert secrets.keys_with_prefix("THREADS_TOKEN_") == ["THREADS_TOKEN_A", "THREADS_TOKEN_B"]
```

`sandboxed_secrets` points `H2T_PATH_ROOT` and `HOME` at `tmp_path` (copy the pattern from
`tests/governance/test_secret_names.py::test_every_secret_write_uses_a_package_name`).

- [ ] **Step 2: Run** `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/social/test_providers.py -v` → FAIL (KeyError `social`).
- [ ] **Step 3: Add the two table entries; create `defaults.yaml` with the two URLs from Global Constraints.**
- [ ] **Step 4: Run** the test and `tests/governance/test_secret_names.py` → PASS.
- [ ] **Step 5: Commit** `feat(social): register meta and threads providers`.

### Task 2: Config loader — accounts and rules

**Files:**
- Create: `h2t_ops/connectors/social/config.py`
- Test: `tests/connectors/social/test_config.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Account(id: str, network: str, handle: str, remote_id: str, page_id: str | None, token_key: str, project: str | None, enabled: bool)` — `network ∈ {"instagram","facebook","threads"}`; `id` is `f"{network}:{handle}"`.
  - `@dataclass(frozen=True) Rule(id: str, process: str, action: str, account: str, kind: str, verdict: str, added: str, origin: str)` — `verdict ∈ {"auto","ask","deny"}`; `account` and `kind` (content kind: `reel`, `carousel`, `dm`, …) may be `"*"`, default `"*"`.
  - `accounts_path() -> Path` = `paths.config_dir()/"social"/"accounts.yaml"`; `rules_path()` likewise `rules.yaml`.
  - `load_accounts() -> list[Account]` — enabled and disabled; ConfigError on any violation.
  - `load_rules() -> list[Rule]`; missing file → `[]`.
  - `api_base(network: str) -> str` — `accounts.yaml` key `api.<meta_graph|threads_graph>` else `defaults.yaml`.

- [ ] **Step 1: Write the failing tests**

```python
def test_missing_accounts_file_is_config_error(social_config):      # exit 3 with hint "h2t-ops social accounts discover"
def test_inline_token_is_refused(social_config):                    # any key named token/access_token, or a value matching ^(EAA|THAA|IGAA)[A-Za-z0-9]{20,}
def test_token_key_must_have_provider_prefix(social_config):        # token_key "FOO" → ConfigError; "META_USER_TOKEN" ok
def test_unknown_project_refused_when_domains_exist(social_config): # domains via settings.resolve("domains").value; empty {} → project unchecked
def test_rule_without_origin_is_refused(social_config):             # origin "" → ConfigError naming the rule id
def test_rule_verdict_must_be_known(social_config):                 # verdict "maybe" → ConfigError
def test_api_base_override(social_config):                          # api.meta_graph in accounts.yaml wins over defaults.yaml
```

`social_config` is a conftest fixture in `tests/connectors/social/conftest.py` that points
`H2T_PATH_ROOT` at `tmp_path` and writes YAML from a dict.

Project ids: `settings.resolve("domains").value` is `{domain_id: {label, color, visible,
projects: [...]}}` (parsed by `build.load_ontology`, the one ontology parser —
`tests/governance/test_one_ontology_parser.py`). A `project` is valid if it equals a domain
id or the `id` of an entry in any domain's `projects`. Read the entry shape from
`load_ontology`; do not parse `domains.yaml` yourself.

- [ ] **Step 2: Run** → FAIL (module missing).
- [ ] **Step 3: Implement `config.py`.** Read YAML with `utf-8-sig`; error messages name the file and the account/rule id.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(social): config loader for accounts and rules`.

### Task 3: Journal and rule check — the door core

**Files:**
- Create: `h2t_ops/connectors/social/journal.py`
- Test: `tests/connectors/social/test_journal.py`

**Interfaces:**
- Consumes: `Rule`, `load_rules()` (Task 2).
- Produces:
  - `journal_path() -> Path` = `paths.data_dir()/"social"/"journal.jsonl"`; `raw_path(process: str, day: str) -> Path` = `.../social/raw/<process>/<day>.jsonl`.
  - `new_run(process: str, trigger: str) -> str` — writes a step-1 record, returns `run_id` (uuid4 hex).
  - `record(run_id: str, step: int, **fields) -> dict` — appends one record with `id, ts (UTC ISO), run_id, step` + fields from spec §6; returns it.
  - `write_raw(run_id: str, process: str, account_id: str, endpoint: str, payload: dict) -> str` — appends to the raw zone, writes a step-2 journal record, returns the raw record id.
  - `decide(run_id: str, process: str, action: str, account_id: str, kind: str = "*") -> str` — step 4: matches rules (exact beats `*`, account first, then kind; no match → `"ask"`), **writes the step-4 record** (`rule_id`, `decision`), returns the verdict. `action == "none"` → decision `"noop"`, no rule lookup.
  - `require_allowed(record: dict) -> None` — the guard every future step-5 call goes through: raises `UsageError` unless the record is a step-4 record with decision `auto`, or `ask` later marked `approved`. No connector write may happen without it.
  - `register_secret(value: str) -> None` — adds a value learned at run time (page tokens) to the set the secret check searches; process-wide, in memory only.
  - `REDACT_FIELDS = ("access_token", "page_token", "token")` — removed from any payload before `write_raw` serializes it.
  - `class SecretInRecord(ConfigError)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_records_are_appended_never_rewritten(social_data):      # two records → file has 2 lines, first line unchanged byte-for-byte
def test_step5_without_source_ids_is_refused(social_data):       # record(run, 5, action="x", source_ids=[]) raises ValueError
def test_secret_value_never_written(social_data, monkeypatch):   # monkeypatch secrets.get to return "EAAsecret123..."; record containing it → SecretInRecord, file unchanged
def test_decide_defaults_to_ask_and_records_step4(social_data):  # no rules.yaml → "ask"; journal has step 4, rule_id None
def test_decide_exact_account_beats_wildcard(social_data):       # rules: * → deny, instagram:acme → auto → "auto" with that rule_id
def test_decide_kind_matches(social_data):                       # rule kind "reel" auto; decide(kind="dm") → "ask"
def test_action_none_is_noop(social_data)
def test_require_allowed_refuses_ask_and_deny(social_data)       # spec §6 invariant 1
def test_raw_write_creates_step2_record(social_data):            # write_raw returns id; journal has step 2 with source id == that id
def test_raw_payload_tokens_are_redacted(social_data)            # payload {"data":[{"id":"1","access_token":"PAGETOK"}]} → raw line has no "PAGETOK"
def test_registered_runtime_secret_is_refused(social_data)       # register_secret("PAGETOK"); write_raw({"x":"PAGETOK"}) → SecretInRecord, raw and journal unchanged
```

Secret check: before writing to the journal **or the raw zone**, the serialized line is
searched for every non-empty value of the `token_key`s in `load_accounts()`, `META_USER_TOKEN`,
`META_APP_SECRET` (values via `secrets.get`) and every `register_secret` value; a hit raises
`SecretInRecord` without writing.

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** with `store.append(path, json.dumps(rec, ensure_ascii=False), place="data")`.
- [ ] **Step 4: Run** → PASS; also `tests/governance/` → PASS.
- [ ] **Step 5: Commit** `feat(social): journal, raw zone and rule check`.

### Task 4: Meta Graph client (read-only)

**Files:**
- Create: `h2t_ops/connectors/social/meta.py`
- Test: `tests/connectors/social/test_meta.py`, fixtures `tests/connectors/social/fixtures/meta_*.json`

**Interfaces:**
- Consumes: `api_base("meta")` (Task 2), `secrets.get`.
- Produces `class MetaClient(user_token_key: str = "META_USER_TOKEN", *, session=None, sleep=time.sleep, retry_after: float = 60.0, timeout: float = 30.0)` — `session` defaults to a lazily created `requests.Session`; tests pass a fake session and a recording `sleep`. Every method also returns, as `raw`, the decoded response pages so the caller can journal them (`(rows, raw)` tuples).
  - `pages() -> tuple[list[dict], list[dict]]` — `GET /me/accounts?fields=id,name,access_token,instagram_business_account{id,username}`, all pages followed; rows `{page_id, name, page_token, ig_id, ig_username}`. Each page token is passed to `journal.register_secret` before it is returned.
  - `ig_profile(ig_id, page_token) -> tuple[dict, list[dict]]` — `username,followers_count,media_count`.
  - `ig_media(ig_id, page_token, limit: int) -> tuple[list[dict], list[dict]]` — `id,timestamp,media_product_type,media_type,like_count,comments_count,permalink`, paging until `limit`.
  - `ig_media_insights(media_id, page_token) -> tuple[dict | None, list[dict]]` — metrics `reach,views,total_interactions`; value `None` when Meta answers that insights are unavailable for this media (error code 100 or 10); the error body is still in `raw`.
  - `ig_online_followers(ig_id, page_token, days: int = 29) -> tuple[dict[int, float], list[dict]]` — hour → mean count, hours as returned.
  - Second tuple element (`raw`) = one decoded JSON body per HTTP call made, in call order.
  - Token values never appear in exception messages, `repr`, or `str` of any object
    (errors name the **key**, not the value).
- Errors: code 190 → `AuthError` (hint names the key and says "renew the token"); codes 4, 17, 32, 613 or HTTP 429 → sleep `retry_after` (default 60 s, injectable for tests) and retry once, then `ProviderError("rate limited, retry later")`; connection errors → `NetworkError`.

- [ ] **Step 1: Write the failing tests** (HTTP mocked at `requests.Session.get` with fixture JSON):

```python
def test_pages_follow_paging_and_keep_tokens_out_of_repr()   # 2 pages of /me/accounts → 3 rows; repr(MetaClient) has no token
def test_media_paging_stops_at_limit()                       # limit=150 over pages of 100 → 150 rows, 2 calls
def test_insights_unavailable_returns_none()                 # error code 100 → None
def test_expired_token_is_auth_error()                       # code 190 → AuthError, exit_code 4, message contains "META_USER_TOKEN", not the token value
def test_raw_has_one_body_per_call()                         # 2 paged calls → len(raw) == 2
def test_rate_limit_retries_once_then_fails()                # two 429s → ProviderError; sleep called once
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(social): read-only Meta Graph client`.

### Task 5: Threads client (read-only)

**Files:**
- Create: `h2t_ops/connectors/social/threads.py`
- Test: `tests/connectors/social/test_threads.py`, fixtures `fixtures/threads_*.json`

**Interfaces:**
- Produces `class ThreadsClient(token_key: str, *, session=None, sleep=time.sleep, retry_after: float = 60.0, timeout: float = 30.0)` — same seams and `(rows, raw)` return shape as `MetaClient`:
  - `me() -> tuple[dict, list[dict]]` — `id,username`.
  - `posts(limit: int) -> tuple[list[dict], list[dict]]` — `GET /me/threads?fields=id,timestamp,media_type,permalink`.
  - `post_insights(post_id) -> tuple[dict | None, list[dict]]` — metrics `views,likes,replies,reposts,quotes`; unavailable → value `None`.
  - `profile_insights(days: int = 30) -> tuple[dict, list[dict]]` — `views,likes,replies,followers_count`.
- Errors: same mapping as Task 4 (Threads uses the same Graph error shape); auth hint names `token_key`.

- [ ] **Step 1: Tests** `test_me`, `test_posts_paging_stops_at_limit`, `test_expired_token_is_auth_error` (hint contains the token_key), `test_post_insights_unavailable_returns_none`.
- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5: Commit** `feat(social): read-only Threads client`.

### Task 6: Insights process

**Files:**
- Create: `h2t_ops/connectors/social/insights.py`
- Test: `tests/connectors/social/test_insights.py`

**Interfaces:**
- Consumes: Tasks 2–5.
- Produces:
  - `summarize(posts: list[dict], tz: str) -> dict` — pure: `{"posts": n, "skipped": k, "median_reach": x, "by_weekday": {"Mon": {"n":…, "median":…, "ratio":…}, …}, "by_hour_band": {"00-10":…, "10-13":…, "13-16":…, "16-19":…, "19-22":…, "22-24":…}, "top": [5 posts by reach with permalink]}`. Metric for Threads posts is `views`, for Instagram `reach`.
  - `run(account_ids: list[str] | None, limit: int, client_factory=None) -> dict` — one run: `new_run("insights", trigger)`, per enabled account collect: every client call is unpacked `value, raw = client.method(...)`, and **each** body in `raw` goes to `write_raw` (its id into `source_ids`); only `value`s go to `summarize`. Then summarize → step-3 record with `source_ids`, `decide(run_id, "insights", "none", account_id)` → step-4 `noop`, step 6 record pointing to the report file (step 5 is not written when step 4 is `noop`); report written to `paths.data_dir()/social/insights/<account_id>/<YYYY-MM-DD>.json` via `store.replace(place="data")`. Returns `{run_id, reports: {account_id: summary}}`.
  - Timezone: `user_config.get("timezone")`; missing → `ConfigError` with hint "set timezone in user.yaml".

- [ ] **Step 1: Write the failing tests**

```python
def test_summarize_bands_and_weekdays()                       # 6 fixed posts in tz "UTC" → exact medians/ratios asserted
def test_media_without_insights_is_skipped_and_counted()      # one post insights None → skipped == 1, posts == 5
def test_empty_media_fails_loud(social_config, social_data)   # account with 0 posts → ProviderError("no data"), exit 1
def test_online_followers_hours_are_not_converted()           # {"0": 5, "13": 9} → report key "online_followers_hour_as_reported" equals input
def test_run_writes_provenance_chain(social_config, social_data)  # journal: step1 → step2 (raw ids) → step3 with those ids → step4 noop → step6 with report path
def test_disabled_accounts_are_skipped(social_config, social_data)
```

- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5: Commit** `feat(social): insights process with provenance`.

### Task 7: CLI, discover, registry entry

**Files:**
- Create: `h2t_ops/connectors/social/__init__.py` (`CONNECTOR = ConnectorSpec(name="social", …)`), `h2t_ops/connectors/social/commands.py`
- Test: `tests/connectors/social/test_commands.py`

**Interfaces:**
- Commands (all with `--json` / `--format md|human`, as dropbox):
  - Every command that touches a network opens a run (`new_run("accounts"|"check", "cli")`) and journals each response through `write_raw` — no client is called outside a run.
  - `h2t-ops social accounts discover [--write]` — builds accounts from `MetaClient.pages()` (instagram + facebook rows) and every key from `secrets.keys_with_prefix("THREADS_TOKEN_")` → `ThreadsClient.me()`. Without `--write` prints the YAML; with it merges into `accounts.yaml` keeping existing `enabled`/`project` values, new accounts `enabled: false`. Writes via `store.replace(place="config")`.
  - `h2t-ops social accounts list`
  - `h2t-ops social check [account_id]` — read-only smoke: profile + last 3 posts per enabled account.
  - `h2t-ops social run insights [--account ID ...] [--limit 120]`
  - `h2t-ops social journal [--run RUN_ID] [--last N]`

- [ ] **Step 1: Tests** `test_discover_merges_and_keeps_enabled`, `test_discover_without_write_changes_nothing`, `test_discover_and_check_are_journaled` (step 1 exists; number of step-2 records == number of fake HTTP calls; raw has no page token), `test_cli_output_and_errors_never_show_tokens` (fake tokens; run discover, check, insights, and an expired-token error with `--json` and human format; captured stdout+stderr contain none of the token values), `test_run_insights_envelope_json` (mocked clients), `test_connector_is_discovered` (`registry.discover()` yields `social`), `test_no_client_import_outside_run_modules` (grep: `MetaClient(`/`ThreadsClient(` appear only in `insights.py` and `commands.py`).
- [ ] **Step 2–4:** fail → implement → pass.
- [ ] **Step 5: Run the CI-scoped suite** `C:/dev/h2t-skills/.venv/Scripts/pytest tests/core tests/connectors tests/governance -q` → all PASS; `C:/dev/h2t-skills/.venv/Scripts/ruff check plugins/ lib/ h2t_ops/ tests/ scripts/` → clean.
- [ ] **Step 6: Commit** `feat(social): CLI for discover, check, insights, journal`.

### Task 8: Skill reference and version

**Files:**
- Create: `plugins/h2t-ops/skills/connectors/references/social.md` — commands, config files, secret keys (`META_USER_TOKEN`, `META_APP_SECRET`, `THREADS_TOKEN_<HANDLE>`), how to obtain tokens (Explorer + exchange; Threads User Token Generator), the six-step journal, what is read-only.
- Modify: the connectors `SKILL.md` index line for `social`; `CHANGELOG` entry.
- Version: `.venv/Scripts/python scripts/bump_plugin.py h2t-ops <next patch>` (read the current version from `plugin.json` first).

- [ ] **Step 1:** write the reference; **Step 2:** `uv run h2t-docs-lint doctor` (exit 1 with findings is normal; no new finding for these files); **Step 3:** bump; **Step 4:** commit `docs(social): connector reference; bump h2t-ops`.

### Task 9: Author's machine — migrate secrets and live smoke (manual, with confirmation)

Not code. Done by the executor with the author present.

- [ ] Show the author the plan: values from `~/.h2t/config/secrets/meta-h2t-social.env` →
  `secrets/shared/meta.env` as `META_USER_TOKEN`, `META_APP_SECRET`; `meta-threads.env` →
  `secrets/shared/threads.env` as `THREADS_TOKEN_GLAZOV_AV`, `THREADS_TOKEN_HOU2TOUCH`. Old
  files stay until the author confirms deletion.
- [ ] After the author's yes: write through `secrets.write_env("meta", …)` /
  `secrets.write_env("threads", …)` from a one-off scratchpad script that prints only key
  names and value lengths.
- [ ] `h2t-ops social accounts discover --write`; author enables the five working IG
  profiles, their Pages as needed, and both Threads accounts.
- [ ] `h2t-ops social check` → every enabled account prints a username and 3 posts.
- [ ] `h2t-ops social run insights --account instagram:hou2touch` → report file exists;
  `h2t-ops social journal --last 10` shows steps 1, 2, 3, 6 with linked ids. Paste both
  outputs into the completion report.
