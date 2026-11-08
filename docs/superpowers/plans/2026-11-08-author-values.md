---
title: "Author values"
status: "draft"
date: "2026-11-08"
milestone: "M8"
issue: "581"
---

# Author values Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The release carries no author values: every path and infrastructure interface is read
env → file → neutral default, everything that spends money, logs answers or imposes rules is off
until the user turns it on, setup tells a machine which settings it relied on and has not set,
and a ratchet fails when an author value comes back (#581).

**Architecture:** One resolver module (`h2t_ops/core/settings.py`) owns the key table and
answers value + source for each key; `h2t-ops settings` and `setup doctor` print it. Consumers
switch from literals to the resolver PR by PR. `setup doctor` gains an upgrade check that finds,
from evidence on the machine, every removed default the machine was using. A per-token debt
ratchet in `tests/dev/test_no_author_paths_ship.py` lands first; every later PR lowers it.

**Tech Stack:** Python 3.11+, stdlib + PyYAML, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-14-setup-wizard.md` §15 — on PR #546
(`docs/setup-wizard-situations`, c9d8bb58), not on main. Issue #581 with its audit comment
(2026-10-22) and the skill-audit comment (2026-11-08).

## Place in M8

Re-verified 2026-11-08 against `origin/main` 84dfe600 by reading the cited lines: of ~59 audit
rows in scope, **52 still present, 7 changed, 0 fixed**; ~30 further hits found (listed in the
tasks below). The 2026-10-22 plan on `refactor/author-values` was never pushed and is not used.
Reviewed by Codex 2026-11-08 (round 1: 10 P1, 6 P2 — all addressed below).

Critical path: **PR 1 → #583** (#583 §1 runs "the author-values test from #581"). PR 1 holds
the ratchet and the settings test, so #583 can start as soon as PR 1 merges.

**PR 10 (upgrade check) merges before PRs 3, 4, 5 and 9** — each of those removes a default a
machine may be using, and PR 10 is what tells the machine. PR 2 needs only PR 1.

Order against the other M8 branches — the #581 slice goes first in each shared file, the other
issue rebases on it:

| PR | must merge before | shared files |
|---|---|---|
| 2 labels/owner | #613 → #626 | `tools/docs/lint.py`, `docs-sync-labels/SKILL.md` |
| 3 domains | #611 → #625 → #632 | `scaffold-project/SKILL.md`, `init-project/SKILL.md` |
| 5 daily-brief | #627 | `daily-brief/SKILL.md`, `connectors/notion/brief.py` |
| 6 skill text | #619, #624, #631 | `meetgeek.md`, `handoff-example.md`, `session-start/SKILL.md`, research refs |
| 7 standards/creative | #614 → #615 → #629 | creative profiles, `style-validate/SKILL.md` |

PR 8 depends on an outward step (an issue in `lichtpfad/POS`, owner confirms); #582 is closed.
Otherwise PRs 2–9 do not depend on each other.

## Global Constraints

- §15 rule 1: no author value in code. Missing value → `ConfigError` (exit 3) naming the key and
  the file to set it in. No silent substitution.
- §15 rule 2: env var → file → default; a default is neutral (empty, off) or absent. Two keys
  have no file source, by construction: `path.root` (the files live under it) and
  `machine.name` (config syncs between machines; a file value would give every machine one name).
  Both are env → computed default, and `settings list` says so.
- §15 rule 3: env vars for paths and interfaces only: `H2T_PATH_ROOT`, `H2T_PATH_VAULT`,
  `H2T_PATH_LAKE`, `H2T_PATH_INBOX`, `H2T_PATH_KB`, `H2T_MACHINE_NAME`, `H2T_GITHUB_OWNER`,
  `H2T_NOTION_TASKS_DB`, `H2T_EVALS_SERVICE_URL`. Preferences and switches are file keys with no
  env var (owner comment 2026-10-22).
- §15 rule 5: spending, answer-logging and rule-imposing features default off.
- §15 rule 6: doctor shows value and source (`env`, `file`, `default`, `unset`) per key.
- Owner decision 2026-10-22 #1: the vault default `~/.dor/vault` is **not** changed here
  (waits for lichtpfad/POS#173). It is the one `.dor` read that survives migration.
- Hooks stay registered; a switch is checked inside the handler (`.claude/rules/hooks.md`).
- Every new test is seen red on the tree before its fix (`.claude/rules/verification.md`); a
  test that can only fail on ImportError has not been seen red.
- `plugins/h2t-dev/references/standards/*` and `h2t_ops/resources/docs/standards/*` are edited
  together; `tests/tools/test_resource_copies.py` holds them equal.

## Out of scope (with owner)

| item | where it lives |
|---|---|
| Russian-only output: briefing, pulse page/CLI, hooks, handoff headings, scaffold text | #436 — except `status.py:101`, logic on a display string (Task 5) |
| vault default | lichtpfad/POS#173, then a follow-up |
| `dev-overview` (`lichtpfad`, `~/Projects`, DOR tier) | #612 |
| `design` skill (PFAD, `src/pfad-extension`, domain colours) | #463 |
| `project-audit/SKILL.md:47-55` sibling repo `h2t-landings` | #632 (same file, bookkeeping through commands) |
| renaming the built-in profile ids `h2t-graphs`, `h2t-pfad` | #614 decides; here only their descriptions |

## Decision: runtime `~/.dor` reads (owner, 2026-11-08)

#581 says `.dor` reads go "only through an explicit migrate step". The lake fallback in
`paths.py:355-366` is deliberate: before migration, a default of `data/lake` would advance the
granola/meetgeek cursors while POS reads the old lake, and the notes synced in that window are
never fetched again. Gating it behind `--from-dor` would reintroduce that loss.

Decided: **runtime code reads `.dor` only on a machine that has not migrated** — one gate,
`paths.legacy_read()`, which every runtime reader goes through (PR 9). Migration code keeps
`paths.legacy()`. The vault default is the stated exception (Global Constraints).

## Review Focus

1. A user with **no `user.yaml` at all** runs `h2t-ops setup doctor`, `h2t-docs-sync-labels`,
   `detect_project` and the daily pass — neutral result or exit 3 with a hint, never a
   traceback, never the author's value. Tests: Task 2 `test_empty_environment_*`, empty-config
   cases in Tasks 3–5.
2. **The author after upgrading** behaves as before — only if the PR 10 findings are applied
   on both machines before a build with PRs 3–5, 9 is installed. Test: Task 11 detectors; check:
   Task 12.
3. **An env var set to an empty string** (`H2T_GITHUB_OWNER=`) is unset. Test: Task 2.
4. **A bare repo name with no owner configured**: label tools exit 3 naming `H2T_GITHUB_OWNER`;
   they never use another checkout's remote and never fall back to an org. Test: Task 3.
5. **A migrated machine whose `~/.dor/secrets.env` still holds a key the new store lacks**: PR 9
   stops reading it, so PR 10 must report it first. Test: Task 11 `dor_secrets_not_moved`.

---

## PR 1 — guard and resolver (unblocks #583)

### Task 1: Author-values ratchet

**Files:**
- Modify: `tests/dev/test_no_author_paths_ship.py`

**Interfaces:**
- Produces: `AUTHOR_DEBT: dict[str, tuple[dict[str, int], str]]` — path → (token → count,
  reason). Counted per token, not per line: replacing one author value with another, or adding a
  second on a line that already had one, both change the dict and go red. Later PRs lower or
  delete entries; an entry with reason `"upstream"` is permanent.

- [ ] **Step 1: Patterns**

```python
# Always upstream, wherever they appear.
UPSTREAM = re.compile(r"lichtpfad/h2t-(?:skills|snap)\b|@lichtpfad\b|cache/lichtpfad/")
TOKENS = re.compile(
    r"\blichtpfad\b|hou2touch|personal-os|crypto-(?:regime|orchestrator|machine)|rejuve|quant-kb"
    r"|QATAL|Mamuta|Zilberman|Bezalel|AICF|Motion Designer, Berlin|pfad-extension"
    r"|\bh2t-(?:ai|business|client|dcc|evals|factory|infra|landings|tools|transcription"
    r"|vision|voice)\b|~/\.dor\b|[\"']\.dor[\"']", re.IGNORECASE)
# A runtime read of a 3.x .dor place through the paths API (PR 9 moves these to legacy_read).
DOR_CALL = re.compile(r"\blegacy\(\s*[\"'](?:secrets\.dor|secrets\.dor_old|google\.dor|"
                      r"sessions\.dor|registry\.dor|lake\.dor)[\"']")
# Migration code is where .dor belongs (§15 rule 4): exact files and one prefix.
MIGRATION_FILES = {"h2t_ops/setup/legacy.py", "h2t_ops/setup/storage_doctor.py", "scripts/storage_map.py"}
MIGRATION_PREFIXES = ("h2t_ops/setup/layout/",)
```

`_tokens(path) -> Counter[str]`: per line, strip `UPSTREAM` spans, then count `TOKENS` matches
(lower-cased) and `DOR_CALL` matches (token `"legacy-dor-call"`). `.dor` tokens and
`legacy-dor-call` are not counted in migration files. `core/paths.py` is **not** exempt: its
`LEGACY` table and vault default are debt with reason `"LEGACY table; vault default (D1)"`.
Scope `CODE_ROOTS`, `SKIP_NAMES` as today.

- [ ] **Step 2: Tests with `AUTHOR_DEBT = {}`**

```python
def test_author_values_match_the_debt():
    found = _all_tokens()                         # path -> Counter
    diff = {p: (dict(c), AUTHOR_DEBT.get(p, ({}, ""))[0]) for p, c in found.items()
            if dict(c) != AUTHOR_DEBT.get(p, ({}, ""))[0]}
    gone = [p for p in AUTHOR_DEBT if p not in found]
    assert not diff and not gone, ...             # grown → offending lines; shrunk → "lower AUTHOR_DEBT"

def test_probe_counts_tokens_not_lines(tmp_path):  # positive control
    f = tmp_path / "x.py"
    f.write_text('A = "lichtpfad"; B = "hou2touch"\nURL = "lichtpfad/h2t-skills"\n'
                 'p = paths.legacy("lake.dor")\n')
    assert _tokens(f) == Counter({"lichtpfad": 1, "hou2touch": 1, "legacy-dor-call": 1})
```

- [ ] **Step 3: Run — expected RED**, listing the files of the 2026-11-08 recheck.
  Run: `.venv/bin/pytest tests/dev/test_no_author_paths_ship.py -v`
- [ ] **Step 4: Fill `AUTHOR_DEBT` from that output.** Each entry's reason names the PR or the
  out-of-scope row that removes it (`"PR 2"`, `"#436"`, `"PR 9"`), or `"upstream"` for
  marketplace and plugin identity (`plugin.json` author fields, `setup/{manifest,harness_claude,
  sync,_release}.py`, `scripts/release.py`, `research/fetch.py` User-Agent) — read each of those
  lines before marking it upstream. Run again → PASS.
- [ ] **Step 5: Commit** `test: ratchet author values in shipped code, per token (#581)`

### Task 2: Settings resolver, `h2t-ops settings`, doctor field

**Files:**
- Create: `h2t_ops/core/settings.py`, `tests/core/test_settings.py`, `tests/core/test_settings_consumers.py`
- Modify: `h2t_ops/core/paths.py:148-156` (`source`), `:370-375` (`place`),
  `h2t_ops/connectors/notion/commands.py:260-273`, `h2t_ops/lifecycle/eval/status.py:62`,
  `h2t_ops/lifecycle/eval/session.py:274`, `h2t_ops/setup/legacy.py:329` (doctor), `h2t_ops/cli.py`

**Interfaces:**
- Produces:
  - `Key(name: str, env: str | None, file: str | None, file_key: str | None, default: object)`
    (frozen dataclass); `file` is one of `"user.yaml"`, `"paths.yaml"`, `"repo-mapping.yaml"`,
    `"domains.yaml"`, `None`
  - `KEYS: tuple[Key, ...]`:

    | name | env | file / key | default |
    |---|---|---|---|
    | `path.root` | `H2T_PATH_ROOT` | — | `~/.h2t` |
    | `path.vault` | `H2T_PATH_VAULT` | — | `~/.dor/vault` (D1, unchanged) |
    | `path.lake`, `path.inbox`, `path.kb` | `H2T_PATH_LAKE` / `_INBOX` / `_KB` | `paths.yaml` place | unset (feature off) |
    | `machine.name` | `H2T_MACHINE_NAME` | — | hostname |
    | `github.owner` | `H2T_GITHUB_OWNER` | `user.yaml` `github.owner` | unset |
    | `notion.tasks_database_id` | `H2T_NOTION_TASKS_DB` | `user.yaml` same key | unset |
    | `notion.tasks_schema` | — | `user.yaml` same key | unset (brief without tasks) |
    | `evals.service_url` | `H2T_EVALS_SERVICE_URL` | — | unset (off, no probe) |
    | `repos` | — | `repo-mapping.yaml` | `[]` |
    | `domains` | — | `domains.yaml` | `{}` |
    | `language` | — | `user.yaml` | `"en"` |
    | `timezone` | — | `user.yaml` | unset (system) |
    | `guards` | — | `user.yaml` | `[]` |
    | `sessions.summaries` | — | `user.yaml` | `False` |
    | `domain_patterns`, `context.by_domain`, `context.strategy`, `daily_brief.domains` | — | `user.yaml` | `[]` / `{}` / unset / `{}` |

    The last row's names are new and approved here (§15: "имя утверждается в плане").
  - `resolve(name: str) -> Resolved(value: object, source: Literal["env","file","default","unset"])`;
    an env var set to `""` counts as unset
  - `require(name: str) -> object` — `ConfigError` (exit 3); hint built from the key: the env var
    if any, and `<file_key> in <full path of file>`
  - CLI: `h2t-ops settings list [--json]`, `h2t-ops settings get <name> [--json]` (unset → exit 3);
    doctor dict gains `"settings": [{"key","value","source"}]`
- Path keys delegate to `paths` (`root()`, `vault()`, `place()`), so `paths.py` stays the one
  reader of path env vars: `place(name)` reads `H2T_PATH_<NAME>` before `paths.yaml` for `lake`,
  `inbox`, `kb`; `source()` reports that variable.

- [ ] **Step 1: Consumer tests (existing APIs only — no import of `settings`)** in
  `tests/core/test_settings_consumers.py`:

```python
def test_lake_place_reads_env(monkeypatch, tmp_path):          # paths.yaml only today
    monkeypatch.setenv("H2T_PATH_LAKE", str(tmp_path / "lk"))
    assert paths.place("lake") == tmp_path / "lk"
    assert paths.source("lake") == "H2T_PATH_LAKE"

def test_notion_tasks_db_reads_env(capsys, monkeypatch):       # exit 3 today
    # modelled on tests/skills/daily_brief/test_sections.py:121 (Fake NotionClient):
    # no user.yaml db id, H2T_NOTION_TASKS_DB=db1 → the fake sees a query on db1

def test_evals_status_without_url_is_unconfigured():           # 127.0.0.1:8088 today
    assert get_status(env={})["service_url"] is None

def test_evals_session_without_url_does_not_probe(...)         # session.py:274, pattern of tests/lifecycle/eval/test_session.py
```

- [ ] **Step 2: Run** `.venv/bin/pytest tests/core/test_settings_consumers.py -v` — RED on the
  value in each test (read the four failure lines).
- [ ] **Step 3: Implement** `paths.place/source` env, the notion and evals consumers (evals: no
  URL → service not configured). Run → PASS.
- [ ] **Step 4: Resolver tests** in `tests/core/test_settings.py` — `test_each_env_key_reads_its_var`
  (parametrized over `KEYS` with `env`), `test_file_key_reads_its_file` (each `file` kind, fixture
  under `H2T_PATH_ROOT=tmp`), `test_empty_environment_gives_neutral_or_config_error` (every value
  in the table's default column, or `require` → exit 3), `test_empty_env_string_is_unset`,
  `test_require_hint_names_the_right_file` (`path.lake` → `paths.yaml`, `github.owner` →
  `user.yaml`), `test_settings_list_json_names_every_key` (CLI round trip). Write them against a
  `settings.py` holding only `Key`, `KEYS` and stubs raising `NotImplementedError`; run → RED on
  the stubs, not on import.
- [ ] **Step 5: Implement** `resolve`, `require`, the CLI and the doctor field. Run
  `tests/core/ tests/lifecycle/eval/ tests/skills/daily_brief/ tests/cli/` — PASS.
- [ ] **Step 6: Commit** `feat(settings): key table with env → file → default and its source (#581)`

**PR 1 gate:** full suite + `uvx ruff check plugins/ lib/ h2t_ops/ tests/ scripts/`.

---

## PR 10 — upgrade check in `setup doctor` (before PRs 3, 4, 5, 9)

### Task 11

**Files:** Create `h2t_ops/setup/settings_gaps.py`, `tests/setup/test_settings_gaps.py`; modify
`h2t_ops/setup/legacy.py:329` (doctor), `plugins/h2t-core/skills/setup/SKILL.md` (doctor section:
show the gaps, offer each suggested line).

**Interfaces:**
- Consumes: `settings.resolve`, `paths`, `user_config.path()`
- Produces: `gaps() -> list[Gap]`, `Gap(key: str, evidence: str, suggestion: str | None)`;
  doctor dict gains `"settings_gaps"`. A gap is reported only when the key is unset **and** the
  machine shows it relied on the removed default. The suggestion is derived from the machine,
  never from a literal in code (the ratchet holds this).

Detectors — one per removed default that leaves a trace:

| removed default (PR) | evidence on the machine | suggestion |
|---|---|---|
| org / 16 repos (2) | `repo-mapping.yaml` empty or absent | `h2t-ops paths` hint to register repos |
| `github.owner` (2, 3) | unset, `gh auth status` logged in | `github.owner: <gh api user --jq .login>` |
| doc owner fallback (2) | `git config user.name` empty | `git config --global user.name …` |
| `DOMAIN_CONTEXT_MAP` (3) | files under `config/about-me/`, `context.by_domain` unset | list the files, ask for the mapping |
| `DOMAIN_PATTERNS` (3) | `domains.yaml` non-empty, `domain_patterns` unset | info: new repos will ask for a domain |
| summaries (4) | the session index holds model summaries | `sessions.summaries: true` |
| guards (4) | non-empty `logs/{grade,plain}-guard.jsonl`; any `.h2t/structure.yaml` in a mapped repo | `guards: [<those found>]` |
| evals URL (2) | an `H2T_EVALS_TOKEN` present, URL unset | `H2T_EVALS_SERVICE_URL=<your service>` |
| `.dor` after migration (9) | migrated, and `~/.dor/secrets.env` holds a key the new store lacks (names only, never values); `~/.dor/lake` exists, no `lake` place | `h2t-ops setup secrets …` / `h2t-ops paths set lake …` |

No trace exists for the language (`ru`), the daily-brief keyword groups and `REPO_EXTRA_DIRS`;
doctor lists them as "check by hand" with the key to set.

- [ ] **Step 1: Failing tests** — per detector: evidence + key unset → one gap; key set → none;
  no evidence → none. `test_secret_gap_names_keys_never_values`. `test_doctor_json_has_settings_gaps`.
- [ ] **Step 2: Run** — RED (module stubs, not ImportError).
- [ ] **Step 3: Implement**; skill text shows each gap and its suggested line.
- [ ] **Step 4: Run** `tests/setup/` + ratchet — PASS.
- [ ] **Step 5: Commit** `feat(setup): doctor reports settings a machine relied on and has not set (#581)`

### Task 12: Owner check on both machines (Done-when 3)

- [ ] On Mac and Windows, with the PR 10 build: `h2t-ops setup doctor --json` → apply every
  `settings_gaps` suggestion and every "check by hand" item to `~/.h2t/config/user.yaml`
  (or the named file). Re-run → `settings_gaps` empty.
- [ ] Only then install a build with PRs 3–5 or 9; after it, one session start shows the guards
  logging and the daily pass summarising as before; `h2t-ops settings list` shows `file` for the
  keys just set.

---

## PR 2 — GitHub owner and label tooling (before #613/#626)

### Task 3

**Files:** `h2t_ops/tools/docs/{common.py,sync_labels.py,migrate_legacy_labels.py,lint.py,new_doc.py}`,
`plugins/h2t-dev/skills/docs-sync-labels/SKILL.md:12,48,56,67,83`, `plugins/h2t-dev/README.md:57-58`;
tests `tests/tools/docs/test_github_owner.py` (new), `tests/tools/docs/test_repo_manifest.py`
(its bundled-fallback assertion pins the defect and changes).

**Interfaces:**
- Consumes: `settings.resolve("github.owner")`
- Produces: `common.target(arg: str | None, repo_root: Path) -> str` returning `owner/repo`:
  - `arg` is `owner/repo` → as given;
  - `arg` is a bare name → `<github.owner>/<arg>`; owner unset → `ConfigError` naming
    `H2T_GITHUB_OWNER` (never the remote of `repo_root`: that is another repository);
  - `arg` is `None` (the current checkout) → owner and name from `git remote get-url origin` of
    `repo_root`; no remote → `ConfigError`.

- [ ] **Step 1: Failing tests** — `test_target_owner_repo_as_given`, `test_bare_name_uses_setting`,
  `test_bare_name_without_owner_is_exit_3_even_inside_a_checkout_with_a_remote`,
  `test_current_repo_from_origin` (https and ssh), `test_sync_labels_dry_run_never_prints_lichtpfad`,
  `test_manifest_without_mapping_is_config_error`, `test_migrate_requires_repo` (no `--repo` →
  exit 2, no `gh` call recorded), `test_doc_owner_without_git_user_is_exit_3` (`lint.py:579`,
  `new_doc.py:65`).
- [ ] **Step 2: Run** — RED, each on its value.
- [ ] **Step 3: Implement.** Delete `ORG`, `_BUNDLED_MANIFEST`, `REPO_EXTRA_DIRS` (per-repo
  `extra_doc_dirs`, `tools/docs/config.py:30`, replaces it). `migrate_legacy_labels` requires
  `--repo owner/name`. Skill text: "the repos in your repo mapping, or `owner/repo` you pass";
  examples `<owner>/<repo>`.
- [ ] **Step 4: Run** `tests/tools/` + ratchet — PASS; lower `AUTHOR_DEBT`.
- [ ] **Step 5: Commit** `fix(docs-tools): no default org or repo list; explicit owner/repo (#581)`

---

## PR 3 — domains and project registration (before #611; after PR 10)

### Task 4

**Files:** `h2t_ops/lifecycle/detect_project.py:33-37,211,250-259,307,362`,
`h2t_ops/lifecycle/gather/user.py:7-13,35,47`, `plugins/h2t-core/skills/scaffold-project/SKILL.md:64,66,183`,
`plugins/h2t-core/skills/init-project/SKILL.md:3,81`, `plugins/h2t-core/skills/init-project/references/truth-gate.md:3,6`;
tests `tests/lifecycle/test_detect_project.py`, `tests/lifecycle/gather/test_user.py`.

**Interfaces:**
- Consumes: `settings.resolve("language" | "context.by_domain" | "context.strategy")`; `_ontology()`
  (`detect_project.py:274`) for `domains.yaml`
- Changes: `_build_confirm_message(detected: dict, already_registered: bool, domains: list[str])`
  — both callers (`:307`, `:362`, inside `detect_project()`, which holds `domains_data` from
  `:284`) pass `sorted(domains_data.get("domains", {}))` — the same shape `:128` and `:204` read. Empty list → free-text prompt. A malformed `domains.yaml` keeps today's behaviour
  of `_ontology()`.

- [ ] **Step 1: Failing tests** — `test_no_builtin_domain_patterns` (`/x/h2t-foo`, empty config →
  domain unknown); `test_menu_lists_domains_yaml_keys`; `test_empty_domains_gives_free_text`
  (and `hou2touch`, `crypto`, `personal-os` absent from the message);
  `test_context_files_from_user_yaml`; `test_language_default_en`.
- [ ] **Step 2: Run** — RED.
- [ ] **Step 3: Implement.** `DOMAIN_PATTERNS = []`. Skill text: domains from your
  `domains.yaml`; owner default `gh api user --jq .login`; init-project offers the Notion tracker
  when `h2t-ops settings get notion.tasks_database_id` exits 0; `h2t-factory` →
  `h2t-core:scaffold-project`; truth-gate private references removed; `h2t-voice` → `my-tool`.
- [ ] **Step 4: Run** `tests/lifecycle/ tests/skills/` + ratchet — PASS, debt lowered.
- [ ] **Step 5: Commit** `fix(projects): domains and owner from the user's config (#581)`

---

## PR 4 — off by default: summaries, guards, string logic (after PR 10)

### Task 5

**Files:** `h2t_ops/lifecycle/pulse/daily.py:179`, `h2t_ops/lifecycle/pulse/status.py:61-105`,
`h2t_ops/hooks/{grade_guard,plain_guard,structure_guard}.py`, `grade_guard.py:75` ("Approach §1");
tests `tests/lifecycle/pulse/test_daily.py`, `tests/lifecycle/pulse/test_status.py`,
`tests/hooks/test_guards_opt_in.py` (new).

**Interfaces:**
- Consumes: `settings.resolve("sessions.summaries")`, `settings.resolve("guards")` — values
  `grade`, `plain`, `structure`.

- [ ] **Step 1: Failing tests**
  - `test_daily_skips_summaries_by_default` — `monkeypatch.setattr(daily.summary, "run", spy)`
    (daily calls it through the module attribute, `daily.py:179`); no `user.yaml` → spy not
    called; `sessions.summaries: true` → called once
  - `test_guard_silent_unless_enabled[grade|plain|structure]` — empty config: no log line, exit
    0, including structure-guard's universal rule (`structure_guard.py:207-210`, which applies
    with no `.h2t/structure.yaml`); `guards: [<name>]` → today's behaviour
  - `test_verdict_from_counts_not_text` — monkeypatch the display strings to English; `verdict()`
    still classifies dirty (today it matches `"незакоммиченных"`, `status.py:101`)
- [ ] **Step 2: Run** — RED.
- [ ] **Step 3: Implement.** The session record and the daily pass stay on: both are local and
  free. Only the model call is gated — it spends the user's money and sends transcript text out.
  Handlers return early; hooks.json unchanged. `status.py` computes the verdict from counts and
  states, then renders. Drop "(Approach §1)".
- [ ] **Step 4: Run** `tests/hooks/ tests/lifecycle/pulse/` — PASS.
- [ ] **Step 5: Commit** `fix: model summaries and answer guards are opt-in (#581)`

---

## PR 5 — daily-brief (before #627; after PR 10)

### Task 6

**Files:** `plugins/h2t-ops/skills/daily-brief/SKILL.md:102-118,186-230`,
`h2t_ops/connectors/notion/brief.py:60` (`task`), `:109` (`to_json`); test
`tests/skills/daily_brief/test_sections.py`.

**Interfaces:**
- Produces: each task in `brief-tasks` JSON gains `domain: str | None` — the first name in
  `user.yaml` `daily_brief.domains: {name: [keyword, ...]}` whose keyword occurs
  case-insensitively in the task **title** (the schema has no project field; adding one is not
  in this issue); no map → `null`.

- [ ] **Step 1: Failing tests** — `test_domain_from_title_keyword`, `test_first_matching_domain_wins`,
  `test_no_map_gives_null_domain`.
- [ ] **Step 2: Run** — RED.
- [ ] **Step 3: Implement**; in SKILL.md delete both fallbacks (`notion search` with
  `Status`/`Project`; the old-schema ranking with `Sample Project` and 90/30/3) — `brief-tasks`
  already exits 3 with the schema example (`brief.py:42`) and the skill shows that output.
  Replace the keyword list at :223-230 with "group by `domain`".
- [ ] **Step 4: Run** `tests/skills/` + ratchet — PASS.
- [ ] **Step 5: Commit** `fix(daily-brief): no author schema or domain words; domain from the command (#581)`

---

## PR 6 — examples and references in core/ops skills and code comments

### Task 7 (text only; the ratchet is its test)

Replace with neutral examples (`my-project`, `example.com`, `<service>`, `/Projects/...`) or drop:

- `plugins/h2t-core/skills/handoff/references/handoff-example.md:7,16,20,26-29` — synthetic session; no hostnames, no token fragment
- `plugins/h2t-core/skills/session-start/SKILL.md:145`; `autonomous-run/references/gates.md:4`
- `plugins/h2t-ops/skills/research/{SKILL.md:218, examples.md (11 lines), REPORT-SPEC.md:29,84, reference.md:123}`
- `plugins/h2t-ops/skills/connectors/references/{dropbox.md:13-20,34-42, meetgeek.md:81, notion.md:177}`
- `plugins/h2t-ops/skills/kb/{SKILL.md:44, references/query.md:24}` — `<path-to-your-kb>`
- `plugins/h2t-ops/skills/deploy/SKILL.md:65-66,145-146` — `<service>`, `<target>`
- `plugins/h2t-core/skills/setup/SKILL.md:226`, `h2t_ops/lifecycle/gather/README.md:155-159` —
  `DOR_MACHINE_NAME` named as a legacy read only (`paths.py:444` keeps reading it, #446);
  example domain/repo neutral
- `h2t_ops/connectors/research/visual_ocr.py:240` — hint: "auto-capture needs an `h2t-screenshot`
  command on PATH; pass a screenshot instead" (there is no `ocr` extra; `h2t-tools` is private)
- comments: `pulse/transcript.py:3`, `hooks/reap_codex.py:4`, `tools/docs/common.py:18,48,68,84,201`,
  `lifecycle/scaffold_project.py:30`, `setup/layout/phases.py:24` (fixture ids → describe, not list)

- [ ] **Step 1:** edit; **Step 2:** ratchet — lower `AUTHOR_DEBT`; `tests/skills/` PASS
- [ ] **Step 3: Commit** `docs: neutral examples in shipped skills (#581)`

---

## PR 7 — standards and creative profiles (before #614)

### Task 8 (text only)

- standards, **both copies** (`plugins/h2t-dev/references/standards/`, `h2t_ops/resources/docs/standards/`):
  `git-naming-conventions.md:76-83` repo table, `documentation-structure.md:84-92,129`,
  `api-contracts.md:11`, `code-organization.md:70`, `naming-conventions.md:79` → a neutral
  example table marked as an example
- `plugins/h2t-dev/skills/github-issues/SKILL.md:58-66` — the Phase 5/6/7 table → "milestones of the
  target repo: `gh api repos/<owner>/<repo>/milestones`"
- creative (plugin and resources copies): `profiles/h2t-default/DESIGN.md:26`,
  `recipes/landing-course.yaml:44`, `profiles/h2t-graphs/DESIGN.md:4`, `profiles/h2t-pfad/DESIGN.md:1,4,20`,
  `skills/style-validate/SKILL.md:113` — descriptions say "example profile"; ids unchanged

- [ ] **Step 1:** edit; **Step 2:** `tests/tools/test_resource_copies.py`, `tests/skills/`, ratchet — PASS
- [ ] **Step 3: Commit** `docs: shipped standards and profiles describe examples, not the author's repos (#581)`

---

## PR 8 — POS boundary (owner decision 2026-10-22 #3)

### Task 9

- [ ] **Step 1 (outward, owner confirms first):** issue in `lichtpfad/POS` carrying
  `plugins/h2t-ops/references/pos-operational-boundary.md` as its body — the doc moves there.
- [ ] **Step 2:** delete that file; `h2t-connector-runbook.md:36,60,163-181` → one line linking the
  POS issue. POS lines in skills (`connectors/SKILL.md:29,30,65,161`, `notion.md:37,90`,
  `telegram.md:82`, `meetgeek.md:106`, `research/SKILL.md:146,301,310`,
  `research-artifact-contract.md:36,42`, `templates/{market-research.md:12,technical-decision.md:18}`,
  `traceability-policy.md:13`, `setup/SKILL.md:114,130,134,238,260`, `daily-brief/SKILL.md:37-42`)
  → one phrasing: "a POS-compatible consumer, if configured (contract #582)"; no dead ADR path,
  no "once available" instruction.
- [ ] **Step 3:** `tests/skills/`, `tests/contracts/` — PASS. **Commit** `docs: POS boundary lives in POS; the pack links it (#581)`

---

## PR 9 — `.dor` reads only before migration (after PR 10)

### Task 10

**Files:** `h2t_ops/core/paths.py:347-366`, runtime readers `h2t_ops/core/secrets.py:63,124,215`,
`h2t_ops/core/lake.py:53,250`, `h2t_ops/connectors/meetgeek/recovery.py:131`,
`h2t_ops/lifecycle/gather/sessions_legacy.py:21`; `h2t_ops/setup/layout/secrets_phase.py:30-31`
(orders `dor` first); test `tests/core/test_dor_reads_before_migration.py` (new).
Not touched: `lifecycle/index/build.py:211` reads `records/imports/dor-registry.jsonl`, a new
place — not `.dor`. Migration code (`setup/layout/*`, `setup/legacy.py`) keeps `paths.legacy()`.

**Interfaces:**
- Produces:
  - `paths.migrated() -> bool` — `True` when `layout_file()` exists. A malformed or future
    layout counts as migrated (only migration writes the file); doctor already reports a
    malformed one. `_fallback()` (`paths.py:355`) switches from `_layout() == 1` to `migrated()`.
  - `paths.DOR_KEYS = frozenset({"secrets.dor", "secrets.dor_old", "google.dor", "sessions.dor", "registry.dor", "lake.dor"})`
  - `paths.legacy_read(name: str) -> Path | None` — `None` for a `DOR_KEYS` name on a migrated
    machine, else `legacy(name)`. Every runtime reader above calls it and treats `None` as absent.

- [ ] **Step 1: Failing test** — `test_no_dor_read_after_migration[secrets|google|lake|meetgeek|sessions]`:
  fixture `~/.dor` with a secret, a google credentials file, a lake dir with a cursor, a meetgeek
  staging dir, a sessions dir; layout file present → each reader ignores `.dor`; layout file
  absent → today's behaviour (control, must pass before and after).
  `test_future_layout_counts_as_migrated` (`{"layout": 2}`), `test_malformed_layout_counts_as_migrated`.
- [ ] **Step 2: Run** — RED on the migrated cases only.
- [ ] **Step 3: Implement**; `secrets_phase.py` puts `.dor` last.
- [ ] **Step 4: Run** `tests/core/ tests/setup/ tests/connectors/meetgeek/ tests/lifecycle/gather/` —
  PASS; ratchet: `legacy-dor-call` debt → 0 outside migration files; lower `AUTHOR_DEBT`.
- [ ] **Step 5: Commit** `fix: read ~/.dor only on a machine not yet migrated (#581)`

---

## Done when (from #581)

- [ ] `AUTHOR_DEBT` holds only out-of-scope and `"upstream"` entries, each with its reason — Task 1 + PRs 2–9
- [ ] `test_settings.py` and `test_settings_consumers.py` green, each seen red first — Task 2
- [ ] Task 12 done on both machines; behaviour unchanged
