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
until the user turns it on, and a ratchet fails when an author value comes back (#581).

**Architecture:** One resolver module (`h2t_ops/core/settings.py`) owns the §15 key table and
answers value + source for each key; `h2t-ops settings` and `setup doctor` print it. Consumers
switch from literals to the resolver PR by PR. A per-file debt ratchet in
`tests/dev/test_no_author_paths_ship.py` lands first and every later PR lowers its counts.

**Tech Stack:** Python 3.11+, stdlib + PyYAML, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-14-setup-wizard.md` §15 — on PR #546
(`docs/setup-wizard-situations`, c9d8bb58), not on main. Issue #581 with its audit comment
(2026-10-22) and the skill-audit comment (2026-11-08).

## Place in M8

Re-verified 2026-11-08 against `origin/main` 84dfe600 by reading every cited line: of ~59 audit
rows in scope, **52 still present, 7 changed, 0 fixed**; ~30 further hits found (listed in the
tasks below). The 2026-10-22 plan on `refactor/author-values` was never pushed and is not used.

Critical path: **PR 1 → #583** (#583 §1 runs "the author-values test from #581"). PR 1 holds
both Done-when tests, so #583 can start as soon as PR 1 merges; PRs 2–8 only lower the ratchet.

Order against the other M8 branches — the #581 slice goes first in each shared file, the other
issue rebases on it:

| PR | must merge before | shared files |
|---|---|---|
| 2 labels/owner | #613 → #626 | `tools/docs/lint.py`, `docs-sync-labels/SKILL.md` |
| 3 domains | #611 → #625 → #632 | `scaffold-project/SKILL.md`, `init-project/SKILL.md` |
| 5 daily-brief | #627 | `daily-brief/SKILL.md`, `connectors/notion/brief.py` |
| 6 skill text | #619, #624, #631 | `meetgeek.md`, `handoff-example.md`, `session-start/SKILL.md`, research refs |
| 7 standards/creative | #614 → #615 → #629 | creative profiles, `style-validate/SKILL.md` |

PRs 2–8 are independent of each other.

## Global Constraints

- §15 rule 1: no author value in code. Missing value → `ConfigError` (exit 3) naming the key and
  where to set it. No silent substitution.
- §15 rule 2: one order for every key — environment variable → file (`user.yaml`, `paths.yaml`)
  → default; a default is neutral (empty, off) or absent.
- §15 rule 3: env vars exist for paths and interfaces only: `H2T_PATH_ROOT`, `H2T_PATH_VAULT`,
  `H2T_PATH_LAKE`, `H2T_PATH_INBOX`, `H2T_PATH_KB`, `H2T_MACHINE_NAME`, `H2T_GITHUB_OWNER`,
  `H2T_NOTION_TASKS_DB`, `H2T_EVALS_SERVICE_URL`. Preferences and switches (language, guards,
  session summaries, timezone) are `user.yaml` keys with no env var (owner comment 2026-10-22).
- §15 rule 5: spending, answer-logging and rule-imposing features default off.
- §15 rule 6: doctor shows value and source (`env`, `file`, `default`, `unset`) per key.
- Owner decision 2026-10-22 #1: the vault default `~/.dor/vault` is **not** changed here
  (waits for lichtpfad/POS#173).
- Hooks stay registered; a switch is checked inside the handler (`.claude/rules/hooks.md`).
- Every new test is seen red on the tree before its fix (`.claude/rules/verification.md`).
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
| **runtime `~/.dor` reads** (`core/secrets.py:63,124,209-215,249`, `core/lake.py:53,250`, `meetgeek/recovery.py:131`, `index/build.py:9,211`, `paths.py:359-366` lake fallback) | **owner decision needed** — see "Open decision" |

## Open decision

#581 says `.dor` reads go "only through an explicit migrate step". The lake fallback in
`paths.py:355-366` is deliberate: before layout 1, a default of `data/lake` would advance the
granola/meetgeek cursors while POS reads the old lake, and the notes synced in that window are
never fetched again. Gating it behind `--from-dor` reintroduces that loss on a non-migrated
machine. Proposal: keep every runtime `.dor` read behind `layout < 1` (as the lake fallback
already is) and list them in the ratchet as debt with that reason. Until the owner answers, the
ratchet records them as debt and no task changes them.

## Review Focus

1. A user with **no `user.yaml` at all** runs `h2t-ops setup doctor`, `h2t-docs-sync-labels`,
   `detect_project` and the daily pass — each gives a neutral result or exit 3 with a hint, never
   a traceback and never the author's value. Test: Task 2 `test_empty_environment_*` and the
   empty-config case in Tasks 3–5.
2. **The author after upgrading** behaves as before — only if O1 (his `user.yaml`) is written
   before installing a build with PRs 3–5. Check: O1 step 3.
3. **An env var set to an empty string** (`H2T_GITHUB_OWNER=`) is "unset", not the value `""`.
   Test: Task 2 `test_empty_env_string_is_unset`.
4. **A target repo with no `origin` remote** and no owner configured: label tools exit 3 and
   name `H2T_GITHUB_OWNER`; they never fall back to any org. Test: Task 3.
5. **`migrate_legacy_labels` without `--repo`** must not run `label delete` anywhere. Test: Task 3.

---

## PR 1 — guard and resolver (unblocks #583)

### Task 1: Author-values ratchet

**Files:**
- Modify: `tests/dev/test_no_author_paths_ship.py`

**Interfaces:**
- Produces: `AUTHOR_DEBT: dict[str, tuple[int, str]]` — path → (hit count, reason). Later
  PRs lower counts or delete entries; nothing may add one without the owner.

- [ ] **Step 1: Add three patterns and the legitimate-use filter**

```python
# `lichtpfad` is the upstream and the marketplace; everything else is the author.
LEGIT_LICHTPFAD = re.compile(
    r"lichtpfad/h2t-(?:skills|snap)\b|@lichtpfad\b|cache/lichtpfad/|marketplace[^\n]*lichtpfad"
    r"|\"name\": \"lichtpfad\"|^author: lichtpfad$")
AUTHOR_OWNER = re.compile(r"\blichtpfad\b")
AUTHOR_NAMES = re.compile(
    r"hou2touch|personal-os|crypto-(?:regime|orchestrator|machine)|rejuve|quant-kb"
    r"|QATAL|Mamuta|Zilberman|Bezalel|AICF|Motion Designer, Berlin|pfad-extension"
    r"|\bh2t-(?:ai|business|client|dcc|evals|factory|infra|landings|tools|transcription"
    r"|vision|voice)\b", re.IGNORECASE)
DOR_HOME = re.compile(r"~/\.dor\b|[\"'/]\.dor[\"'/]|\"\.dor\"")
# Migration code is where `.dor` belongs (§15 rule 4).
DOR_MIGRATION = {"h2t_ops/setup/legacy.py", "h2t_ops/setup/storage_doctor.py",
                 "h2t_ops/core/paths.py", "scripts/storage_map.py"}  # + h2t_ops/setup/layout/*
```

A line counts for `AUTHOR_OWNER` only if `LEGIT_LICHTPFAD` does not match it. Scope:
`CODE_ROOTS`, `SKIP_NAMES` as today.

- [ ] **Step 2: Write the tests with `AUTHOR_DEBT = {}`**

```python
def test_author_values_do_not_grow():
    found = _author_counts()          # path -> hits over the three patterns
    grown = {p: n for p, n in found.items() if n > AUTHOR_DEBT.get(p, (0, ""))[0]}
    assert not grown, ...             # print path, count, first three lines

def test_author_debt_is_not_stale():
    found = _author_counts()
    stale = {p: (n, found.get(p, 0)) for p, (n, _) in AUTHOR_DEBT.items() if found.get(p, 0) < n}
    assert not stale, "lower AUTHOR_DEBT to the new count: ..."

def test_probe_sees_a_planted_value(tmp_path):   # positive control
    (tmp_path / "x.py").write_text('ORG = "lichtpfad"\nURL = "lichtpfad/h2t-skills"\n')
    assert _count_file(tmp_path / "x.py") == 1
```

- [ ] **Step 3: Run — expected RED**, listing the files of the 2026-11-08 recheck
  (`sync_labels.py`, `migrate_legacy_labels.py`, `detect_project.py`, `scaffold-project/SKILL.md`, …).

Run: `.venv/bin/pytest tests/dev/test_no_author_paths_ship.py -v`

- [ ] **Step 4: Fill `AUTHOR_DEBT` from that output**, one reason per entry naming the PR or
  out-of-scope row that removes it (`"PR 2"`, `"#436"`, `"open decision: runtime .dor"`).
  Run again → PASS.

- [ ] **Step 5: Commit** `test: ratchet author values in shipped code (#581)`

### Task 2: Settings resolver, `h2t-ops settings`, doctor

**Files:**
- Create: `h2t_ops/core/settings.py`, `tests/core/test_settings.py`
- Modify: `h2t_ops/core/paths.py:148-156,370-375` (env for lake/inbox/kb), `h2t_ops/connectors/notion/commands.py:260-273`,
  `h2t_ops/lifecycle/eval/session.py:274`, `h2t_ops/lifecycle/eval/status.py:62`,
  `h2t_ops/setup/legacy.py:329` (doctor), `h2t_ops/cli.py` (subcommand)

**Interfaces:**
- Produces:
  - `Key(name: str, env: str | None, file_key: str | None, default: object)` (frozen dataclass)
  - `KEYS: tuple[Key, ...]` — exactly the §15 tables: `path.root`, `path.vault`, `path.lake`,
    `path.inbox`, `path.kb`, `machine.name`, `github.owner`, `notion.tasks_database_id`,
    `evals.service_url`, `language` (default `"en"`), `guards` (default `[]`),
    `sessions.summaries` (default `False`), `timezone` (default `None` = system)
  - `resolve(name: str) -> Resolved(value: object, source: Literal["env","file","default","unset"])`
  - `require(name: str) -> object` — `ConfigError` (exit 3), hint names env var and `user.yaml` key
  - CLI: `h2t-ops settings list [--json]`, `h2t-ops settings get <name> [--json]`
    (`get` on an unset key exits 3); doctor dict gains `"settings": [{"key","value","source"}]`

Path keys delegate to `paths` (`root()`, `vault()`, `place()`), so `paths.py` stays the one
reader of path env vars; `paths.place(name)` reads `H2T_PATH_<NAME>` before `paths.yaml` for
`lake`, `inbox`, `kb`, and `paths.source()` reports that variable.

- [ ] **Step 1: Failing tests against the consumers, not only the new module**

```python
@pytest.mark.parametrize("key", [k for k in settings.KEYS if k.env])
def test_each_interface_key_reads_its_env_var(key, monkeypatch, tmp_path): ...
    # set env → resolve(key.name).source == "env"

def test_lake_place_reads_env(monkeypatch, tmp_path):        # red today: paths.yaml only
    monkeypatch.setenv("H2T_PATH_LAKE", str(tmp_path / "lk"))
    assert paths.place("lake") == tmp_path / "lk"
    assert paths.source("lake") == "H2T_PATH_LAKE"

def test_notion_tasks_db_reads_env(...)                      # red today
def test_evals_url_unset_is_off(...)                         # red today: probes 127.0.0.1:8088
    assert eval_status.service_url({}) is None

def test_empty_environment_gives_neutral_or_config_error(monkeypatch, tmp_path):
    # HOME=tmp, H2T_PATH_ROOT=tmp, no user.yaml, every H2T_* unset
    # value in (None, [], False, "en", <hostname>, tmp root)  — or require() raises exit 3
def test_empty_env_string_is_unset(...)
def test_settings_list_json_names_every_key(...)              # CLI round trip
```

- [ ] **Step 2: Run** `.venv/bin/pytest tests/core/test_settings.py -v` — RED; read that the
  lake/notion/evals tests fail on the value, not on ImportError (import `settings` lazily inside
  the parametrized test only).
- [ ] **Step 3: Implement** `settings.py`; switch the four consumers; add the CLI and the doctor
  field. Evals: unset URL → the eval session/status treat the service as not configured (no probe).
- [ ] **Step 4: Run** `tests/core/ tests/lifecycle/eval/ tests/connectors/notion/ tests/cli/` — PASS.
  Lower `AUTHOR_DEBT` only if it moved (8088 is not in its patterns).
- [ ] **Step 5: Commit** `feat(settings): §15 key table with env → file → default and its source (#581)`

**PR 1 gate:** full suite + `uvx ruff check plugins/ lib/ h2t_ops/ tests/ scripts/`.

---

## PR 2 — GitHub owner and label tooling (before #613/#626)

### Task 3

**Files:** `h2t_ops/tools/docs/{common.py,sync_labels.py,migrate_legacy_labels.py,lint.py,new_doc.py}`,
`plugins/h2t-dev/skills/docs-sync-labels/SKILL.md:12,48,56,67,83`, `plugins/h2t-dev/README.md:57-58`;
tests `tests/tools/docs/test_github_owner.py` (new), `tests/tools/docs/test_repo_manifest.py` (changes:
it pins the bundled fallback today).

**Interfaces:**
- Consumes: `settings.resolve("github.owner")`
- Produces: `common.github_owner(repo_root: Path | None) -> str` — setting, else owner parsed
  from `git remote get-url origin` of `repo_root`, else `ConfigError` naming `H2T_GITHUB_OWNER`.

- [ ] **Step 1: Failing tests**
  - `test_owner_from_setting`, `test_owner_from_origin_remote` (https and ssh URLs),
    `test_no_owner_is_exit_3` (repo without remote, no setting)
  - `test_sync_labels_targets_derived_owner` — `--dry-run` prints `<owner>/<repo>`, never `lichtpfad/`
  - `test_manifest_without_mapping_is_config_error` — replaces the bundled-fallback assertion
  - `test_migrate_requires_repo` — no `--repo owner/name` → exit 2, no `gh` call recorded
  - `test_doc_owner_without_git_user_is_exit_3` for `lint.py:579` and `new_doc.py:65`
- [ ] **Step 2: Run** — RED on each, for the stated reason.
- [ ] **Step 3: Implement.** Delete `ORG`, `_BUNDLED_MANIFEST`, `REPO_EXTRA_DIRS` (per-repo
  `extra_doc_dirs`, `tools/docs/config.py:30`, replaces it). `migrate_legacy_labels` takes
  `--repo owner/name` (required). Skill text: org and "all 16 repos" replaced by "the repos in
  your repo mapping, or the ones you pass"; examples `<repo>`.
- [ ] **Step 4: Run** `tests/tools/` + ratchet — PASS; lower `AUTHOR_DEBT` for every touched file.
- [ ] **Step 5: Commit** `fix(docs-tools): no default org or repo list; owner from setting or remote (#581)`

---

## PR 3 — domains and project registration (before #611)

### Task 4

**Files:** `h2t_ops/lifecycle/detect_project.py:33-37,250-259`, `h2t_ops/lifecycle/gather/user.py:7-13,35,47`,
`plugins/h2t-core/skills/scaffold-project/SKILL.md:64,66,183`, `plugins/h2t-core/skills/init-project/SKILL.md:3,81`,
`plugins/h2t-core/skills/init-project/references/truth-gate.md:3,6`; tests in
`tests/lifecycle/test_detect_project.py`, `tests/lifecycle/gather/test_user.py`.

**Interfaces:**
- Consumes: `settings.resolve("language")`; `_ontology()` (`detect_project.py:274`) for `domains.yaml`
- Produces: `user.yaml` keys `context.by_domain: {domain: [file, ...]}` (default `{}`) and
  `context.strategy: <file>` (default none), read in `gather/user.py`.

- [ ] **Step 1: Failing tests**
  - `test_no_builtin_domain_patterns` — repo path `/x/h2t-foo` with empty `user.yaml` → domain unknown
  - `test_domain_menu_from_domains_yaml` — menu lists the keys of the fixture `domains.yaml`;
    empty file → free-text prompt, and the strings `hou2touch`, `crypto`, `personal-os` absent
  - `test_context_files_from_user_yaml`, `test_language_default_en`
- [ ] **Step 2: Run** — RED.
- [ ] **Step 3: Implement.** `DOMAIN_PATTERNS = []`. Skill text: domains "from your
  `domains.yaml`"; owner default from `gh api user --jq .login`; init-project offers the Notion
  tracker when `h2t-ops settings get notion.tasks_database_id` exits 0 (not on domain name);
  `h2t-factory` → `h2t-core:scaffold-project`; truth-gate private references removed; example
  `h2t-voice` → `my-tool`.
- [ ] **Step 4: Run** `tests/lifecycle/ tests/skills/` + ratchet — PASS, debt lowered.
- [ ] **Step 5: Commit** `fix(projects): domains and owner from the user's config, not the author's (#581)`

---

## PR 4 — off by default: summaries, guards, string logic

### Task 5

**Files:** `h2t_ops/lifecycle/pulse/daily.py:179`, `h2t_ops/lifecycle/pulse/status.py:61-105`,
`h2t_ops/hooks/{grade_guard,plain_guard,structure_guard}.py`, `grade_guard.py:75` ("Approach §1");
tests `tests/lifecycle/pulse/test_daily.py`, `tests/lifecycle/pulse/test_status.py`,
`tests/hooks/test_guards_opt_in.py` (new).

**Interfaces:**
- Consumes: `settings.resolve("sessions.summaries")`, `settings.resolve("guards")` — values
  `grade`, `plain`, `structure`.

- [ ] **Step 1: Failing tests**
  - `test_daily_skips_summaries_by_default` — fake `ask` records zero calls with no `user.yaml`;
    `sessions.summaries: true` → called
  - `test_guard_silent_unless_enabled[grade|plain|structure]` — empty config: no log line, exit 0,
    including structure-guard's `plan_dirs` rule (`structure_guard.py:210`); `guards: [<name>]` → today's behaviour
  - `test_verdict_from_counts_not_text` — monkeypatch the display strings to English; `verdict()`
    still classifies "dirty" (today it matches `"незакоммиченных"`, `status.py:101`)
- [ ] **Step 2: Run** — RED.
- [ ] **Step 3: Implement.** The session record and the daily pass stay on: both are local
  and free (backfill, branch status). Only the model call is gated — that is what spends the
  user's money and sends transcript text out. Handlers return early; hooks.json unchanged. `status.py` computes
  the verdict from the counts and states, then renders. Drop "(Approach §1)".
- [ ] **Step 4: Run** `tests/hooks/ tests/lifecycle/pulse/` — PASS.
- [ ] **Step 5: Commit** `fix: model summaries and answer guards are opt-in (#581)`

---

## PR 5 — daily-brief (before #627)

### Task 6

**Files:** `plugins/h2t-ops/skills/daily-brief/SKILL.md:102-118,186-230`,
`h2t_ops/connectors/notion/brief.py`; test `tests/connectors/notion/test_brief.py`.

**Interfaces:**
- Produces: `brief-tasks` JSON gains `domain: str | None` per task, from `user.yaml`
  `daily_brief.domains: {name: [keyword, ...]}` matched case-insensitively against title and
  project; no map → `null` everywhere.

- [ ] **Step 1: Failing tests** — `test_domain_from_user_map`, `test_no_map_gives_null_domain`.
- [ ] **Step 2: Run** — RED.
- [ ] **Step 3: Implement**; in SKILL.md delete both fallbacks (`notion search` with
  `Status`/`Project`, and the old-schema ranking with `Sample Project` and 90/30/3) — `brief-tasks`
  already exits 3 with the schema example (`brief.py:42`); the skill shows that output. Replace the
  keyword list at :223-230 with "group by `domain`".
- [ ] **Step 4: Run** `tests/connectors/notion/ tests/skills/` + ratchet — PASS.
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

- [ ] **Step 1:** edit; **Step 2:** ratchet — counts drop, lower `AUTHOR_DEBT`; `tests/skills/` PASS
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

- [ ] **Step 1 (outward, confirm with owner first):** issue in `lichtpfad/POS` carrying
  `plugins/h2t-ops/references/pos-operational-boundary.md` as its body — the doc moves there.
- [ ] **Step 2:** delete that file; `h2t-connector-runbook.md:36,60,163-181` → one line linking the
  POS issue/doc. POS lines in skills (`connectors/SKILL.md:29,30,65,161`, `notion.md:37,90`,
  `telegram.md:82`, `meetgeek.md:106`, `research/SKILL.md:146,301,310`,
  `research-artifact-contract.md:36,42`, `templates/{market-research.md:12,technical-decision.md:18}`,
  `traceability-policy.md:13`, `setup/SKILL.md:114,130,134,238,260`, `daily-brief/SKILL.md:37-42`)
  → one phrasing: "a POS-compatible consumer, if configured (contract: #582)"; no dead ADR path,
  no "once available" instruction.
- [ ] **Step 3:** `tests/skills/`, `tests/contracts/` — PASS. **Commit** `docs: POS boundary lives in POS; the pack links it (#581)`

---

## O1 — owner step: the author's values into his `user.yaml` (Done-when 3)

Not code: §15 rule 1 forbids a migration that carries the author's values. On **both** machines
(Mac, Windows), **before** installing a build with PRs 3–5:

- [ ] **Step 1:** `h2t-ops settings list --json` (PR 1) — record today's sources.
- [ ] **Step 2:** add to `~/.h2t/config/user.yaml`: `github.owner`, `domain_patterns` (the three
  rules from `detect_project.py:33-37`), `context.by_domain` (`gather/user.py:7-13`),
  `context.strategy`, `language: ru`, `guards: [grade, plain, structure]`,
  `sessions.summaries: true`, `daily_brief.domains` (`daily-brief/SKILL.md:225-228`),
  `evals.service_url` if the evals service is used. Per-repo `extra_doc_dirs` in the docs-lint
  config of the three repos that `REPO_EXTRA_DIRS` named — the owner's repos, his commit.
- [ ] **Step 3:** after install: `h2t-ops settings list` shows `file` for each; one session start
  shows the guards logging and the daily pass summarising, as before.

## Done when (from #581)

- [ ] `AUTHOR_DEBT` holds only out-of-scope rows, each with its reason — Task 1 + PRs 2–8
- [ ] `test_settings.py` green, seen red first — Task 2
- [ ] O1 done on both machines; behaviour unchanged
