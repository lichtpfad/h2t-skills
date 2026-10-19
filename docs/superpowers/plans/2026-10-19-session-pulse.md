---
title: "Session pulse"
status: "draft"
date: "2026-10-19"
milestone: ""
issue: "566"
---

# Session pulse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every own Claude/Codex session is recorded on its own, and `h2t-ops sessions` lists them by
domain → project → repo → branch with a summary, a work status and a resume command.

**Architecture:** One hook handler (`session-pulse`) writes a session record keyed by the program's
session UUID on `SessionStart`/`SessionEnd`, in Claude and in Codex. `handoff` enriches the same file.
A daily pass backfills missed sessions from transcripts, computes branch status, writes model
summaries and runs `audit_map.py`. The index (`state/index.sqlite`, schema v2) serves a terminal
command and a static HTML page. Files stay the truth; the index is rebuilt from them.

**Tech Stack:** Python 3.11+, stdlib + PyYAML (already a dependency), sqlite3, `git`, `gh`,
`claude -p` for summaries. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-19-session-pulse.md` (#566). Storage rules it builds on:
`docs/superpowers/specs/2026-10-17-storage-and-governance.md` (#548).

## Global Constraints

- Truth is the record file `records/sessions/<machine>/<project>/<session_id>.md`; every write goes
  through `h2t_ops.core.store` with `place="records.sessions"`. No second database.
- The index is derived: new columns/tables go into `h2t_ops/lifecycle/index/schema.py` with
  `SCHEMA_VERSION = 2` (a mismatch rebuilds).
- A session outside the ontology gets project `unregistered` (spec §3).
- Subagent sessions, `codex exec` calls and empty sessions never appear (spec §2 anti-goals).
- Codex live originators: `codex-tui`, `Codex Desktop`. Machine: `codex_exec`, `Claude Code`,
  `codex_sdk_ts`. Anything else → `origin: unknown`, hidden unless `--all` (spec §5.2, §7).
- Resume commands (spec §7): Codex `codex resume <UUID> -C "<cwd>"`; Claude
  `cd "<cwd>"; claude --resume <UUID>`.
- Status labels, verbatim (spec §5.4): `готово`, `ждёт PR`, `не отправлено`, `брошено с изменениями`.
- A hook never blocks and never fails the session: every exception is swallowed into
  `~/.h2t/logs/hooks.jsonl` by the existing `h2t-hook` runner; the handler returns an empty `Reply`.
- No author paths in package code (`tests/release/test_ratchets.py`): `audit_map.py` is reached
  through `user_config.get("sessions.audit_map")` (an argv list), never a literal path.
- One command per Bash call; explicit `git add <paths>`; tests and lint as in `CLAUDE.md`
  "Key Commands", run from this checkout's own `.venv`; lint paths
  `plugins/ lib/ h2t_ops/ tests/ scripts/`.

## Review Focus

1. A session resumed, compacted or `/clear`ed fires `SessionStart` again → the record must be updated
   in place (one file per UUID, `started_at` keeps the earliest value). Test in Task 3.
2. `handoff` resolves a different project than the hook did (hook saw `unregistered`, handoff got
   `--project x`) → still one file: handoff writes into the existing UUID file wherever it lies.
   Test in Task 4.
3. The `cwd` of a session is gone (worktree removed) → status shows `нет копии`, the command does not
   crash, the resume line still prints. Test in Task 7.
4. A transcript with a truncated last line or a non-UTF-8 byte → the reader skips the line, never
   raises. Test in Task 2.
5. The summarizer's own `claude -p` run must not become a session in the pulse. Test in Task 9.

---

## File Structure

| File | Responsibility |
|---|---|
| `h2t_ops/lifecycle/pulse/__init__.py` | package marker, no logic |
| `h2t_ops/lifecycle/pulse/transcript.py` | read a Claude/Codex transcript: header, origin, stamps, user messages |
| `h2t_ops/lifecycle/pulse/record.py` | locate, merge and write the UUID-keyed session record; git facts of a cwd |
| `h2t_ops/hooks/session_pulse.py` | the `session-pulse` hook handler |
| `h2t_ops/lifecycle/pulse/backfill.py` | records for sessions the hook missed |
| `h2t_ops/lifecycle/pulse/status.py` | work status per (repo, branch) into the index |
| `h2t_ops/lifecycle/pulse/summary.py` | 1–3 line model summary per session |
| `h2t_ops/lifecycle/pulse/daily.py` | the daily pass and its once-a-day trigger; `audit_map` run |
| `h2t_ops/lifecycle/pulse/view.py` | query + filters + terminal rendering + resume line |
| `h2t_ops/lifecycle/pulse/page.py` | static HTML page from the same query |
| `h2t_ops/lifecycle/pulse/cli.py` | `h2t-ops sessions ...` argument parsing |
| Modify `h2t_ops/lifecycle/session_record.py` | new FIELDS |
| Modify `h2t_ops/lifecycle/index/schema.py`, `build.py` | v2 columns, `branch_status` table |
| Modify `h2t_ops/lifecycle/handoff.py` | write into the UUID record when the program id is known |
| Modify `h2t_ops/hooks/__init__.py`, `plugins/h2t-core/hooks/hooks.json` | register the hook |
| Modify `h2t_ops/cli.py` | route `sessions` |
| Modify `plugins/h2t-core/references/version-check.md:81` | Codex runs hooks |
| Create `plugins/h2t-core/references/session-pulse.md` | Codex hook install + trust, daily pass, commands |

---

### Task 1: Probes that the plan depends on

No code. Results go into spec §7 as a new "Результаты проб (план)" block; commit the spec.

- [ ] **Step 1: Codex hook payload and `codex exec`.** Write a throwaway hook (in the session
  scratchpad, not the repo) that appends its stdin to a scratch file, register it in
  `~/.codex/hooks.json` for `SessionStart` and `SessionEnd`. **Ask the author before editing
  `~/.codex/hooks.json`** and to trust it via `/hooks`. Run one `codex` TUI session and one
  `codex exec --skip-git-repo-check "say ok"`.
  Record: does `codex exec` fire the hook; does the transcript at `transcript_path` already hold the
  `session_meta` line with `originator` when `SessionStart` fires; the exact `cwd`/`session_id` shape.
- [ ] **Step 2: Codex session id inside its shell.** In the TUI session, run `env` filtered to names
  only: `env | cut -d= -f1 | grep -i -E "codex|thread|session"`. **Never print values.** Record
  the variable name that carries the
  session UUID, if any.
  Also in a Claude hook: confirm the hook process inherits `CLAUDE_CODE_ENTRYPOINT` (log the name
  and value of that one variable only).
- [ ] **Step 3: Claude entrypoint of a headless run.** `claude -p --no-session-persistence "say ok"`
  then `claude -p "say ok"`; for the second, read `entrypoint` from its transcript. Record the value
  (expected `sdk-cli`, unverified).
- [ ] **Step 4: Claude `SessionEnd` on window close.** Open a Claude session in a new terminal with a
  temporary `SessionEnd` logger (same scratch hook), close the window with the X. Record yes/no.
- [ ] **Step 5: Remove the scratch hook entries** from `~/.codex/hooks.json` and Claude settings; show
  the diff to the author.
- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-10-19-session-pulse.md
git commit -m "docs: session pulse — probe results for the plan (#566)"
```

Rulings that depend on the probes (carry them into the ledger):
- Step 1 says `codex exec` does not fire hooks → the origin filter in Task 3 stays, as a guard.
- Step 1 says `originator` is not yet written at `SessionStart` → Task 3 writes `origin: unknown`
  for Codex at start; Task 8's `settle_open()` re-derives it from the transcript before every
  list, so a live Codex session is visible within a minute (spec §8), not only after it ends.
- Step 2 says the hook does not inherit `CLAUDE_CODE_ENTRYPOINT` → Claude origin at start falls
  back to the transcript and `settle_open()`, as for Codex.
- Step 2 finds no variable → Task 4 finds the Codex record by `record.find_open("codex", cwd)`;
  only when that returns `None` does handoff fall back to the slug record.
- Step 3 value replaces `HEADLESS_ENTRYPOINTS` in Task 2.

---

### Task 2: Transcript reader

**Files:**
- Create: `h2t_ops/lifecycle/pulse/__init__.py`, `h2t_ops/lifecycle/pulse/transcript.py`
- Test: `tests/lifecycle/pulse/__init__.py`, `tests/lifecycle/pulse/test_transcript.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Info: tool: str; session_id: str; cwd: str; origin: str; start: str; end: str; user_msgs: int; path: str`
    (`origin` ∈ `"live" | "machine" | "unknown"`; `start`/`end` ISO strings or `""`)
  - `def origin_of(tool: str, path: Path) -> str` — reads only until the first line that decides it
  - `def read(tool: str, path: Path) -> Info | None` — `None` for a file with no timestamps
  - `def user_messages(tool: str, path: Path) -> list[str]` — user-voice texts in order
  - `def last_assistant_text(tool: str, path: Path) -> str`
  - `def is_subagent(path: Path) -> bool` — `agent-*` name or a `subagents` parent
  - constants `LIVE_ORIGINATORS = ("codex-tui", "Codex Desktop")`,
    `MACHINE_ORIGINATORS = ("codex_exec", "Claude Code", "codex_sdk_ts")`,
    `HEADLESS_ENTRYPOINTS = ("sdk-cli",)` (value from Task 1 Step 3)

Port the parsing of `C:/dev/docs/standards/scripts/repo_audit/session_catalog.py`
(`iter_json`, `is_user_voice`, `claude_text`, `claude_session`, `codex_session`) — copy, do not import
across repos. Claude origin: `entrypoint` in `HEADLESS_ENTRYPOINTS` → `machine`; any `isSidechain:
true` record → `machine`; missing entrypoint → `unknown`; else `live`.

- [ ] **Step 1: Write the failing tests** (fixtures written into `tmp_path` by the test)

```python
def test_codex_tui_is_live(tmp_path): ...            # session_meta originator "codex-tui" → read(...).origin == "live"
def test_codex_exec_is_machine(tmp_path): ...        # "codex_exec" → "machine"; "Claude Code" → "machine"
def test_unknown_originator_is_unknown(tmp_path): ...# "something-new" → "unknown"
def test_claude_cli_is_live_and_counts_user_voice(tmp_path): ...
    # entrypoint "cli", 2 user text msgs + 1 "<command-name>" msg → user_msgs == 2, session_id == file stem
def test_claude_headless_is_machine(tmp_path): ...   # entrypoint "sdk-cli" → "machine"
def test_broken_lines_are_skipped(tmp_path): ...     # truncated last line + b"\xff" byte → no exception, end == last good timestamp
def test_subagent_paths(tmp_path): ...               # proj/u1/subagents/agent-a1.jsonl → True; proj/u1.jsonl → False
def test_no_timestamps_is_none(tmp_path): ...        # read(...) is None
```

- [ ] **Step 2: Run** `pytest tests/lifecycle/pulse/test_transcript.py -v` — Expected: FAIL, `ModuleNotFoundError: h2t_ops.lifecycle.pulse`
- [ ] **Step 3: Implement** `transcript.py` per the Interfaces block. Open files with
  `encoding="utf-8", errors="replace"`.
- [ ] **Step 4: Run** the same command — Expected: 8 passed
- [ ] **Step 5: Commit** `feat(pulse): read Claude and Codex transcripts (#566)` with the four files.

---

### Task 3: UUID-keyed record and the `session-pulse` hook

**Files:**
- Create: `h2t_ops/lifecycle/pulse/record.py`, `h2t_ops/hooks/session_pulse.py`
- Modify: `h2t_ops/lifecycle/session_record.py:15-16` (FIELDS), `h2t_ops/hooks/__init__.py:49-64`,
  `plugins/h2t-core/hooks/hooks.json`
- Test: `tests/lifecycle/pulse/test_record.py`, `tests/hooks/test_session_pulse.py`

**Interfaces:**
- Consumes: `transcript.origin_of`, `transcript.is_subagent`
- Produces:
  - `session_record.FIELDS` gains, after `"session_id"`: `"name", "tool", "origin", "cwd", "repo",
    "worktree", "started_at", "ended_at", "user_msgs", "transcript"`; after `"artifacts"`:
    `"summary", "summary_source", "summary_stamp"`. Existing order otherwise unchanged.
  - `def git_facts(cwd: str) -> dict` → `{"branch", "repo", "worktree"}`; `repo` = parent of
    `git rev-parse --path-format=absolute --git-common-dir`, `worktree` = `--show-toplevel`; all `""`
    outside git or when git fails (5 s timeout each).
  - `def project_of(cwd: str) -> tuple[str, str]` → `identify_project(cwd)`; empty or `"unknown"` id →
    `("unregistered", "")`.
  - `def find(session_id: str, machine: str) -> Path | None` — glob `records/sessions/<machine>/*/<id>.md`.
  - `def upsert(session_id: str, fields: dict, *, body: bytes | None = None, keep_earliest=("started_at",)) -> Path`
    — under `store.locked(paths.state_dir() / "locks" / f"session-{session_id}.lock", place="state")`:
    existing file → merge (new non-empty values win, except `keep_earliest` keys keep the smaller
    value), write with `store.replace`; none → `store.create` at
    `session_record.session_path(machine, project, session_id)`. A record is never moved or
    removed: `store.remove` refuses `records.sessions` (`h2t_ops/core/store.py:497`). When the
    merged `project` differs from the file's directory, the file stays and its frontmatter
    `project` changes; the index reads the project from frontmatter (`build._session_row`), so
    queries follow it. Ruling to ledger — cost if wrong: a record under `unregistered/` whose
    frontmatter names a project; a later migration can move it.
  - `def find_open(tool: str, cwd: str) -> str | None` — the session id of the single record on
    this machine with this `tool` and `cwd`, no `ended_at`, newest `started_at`; `None` when there
    are none or several. Body: given body, else the existing
    body, else `b""`. `machine` defaults to `get_machine_name()`; `updated_at` and `date` set on every
    write.
- `session_pulse.handle(event: dict) -> Reply` — always `Reply()`.

Hook logic: skip when `os.environ.get("H2T_PULSE_SKIP")`, when `session_id` is empty, or
`transcript.is_subagent(Path(transcript_path))`. Tool = `"codex"` when `transcript_path` contains
`/.codex/` or `\.codex\`, else `"claude"`. Origin for Claude: `CLAUDE_CODE_ENTRYPOINT` in
`HEADLESS_ENTRYPOINTS` → `machine`, any other non-empty value → `live`; for Codex, or when the
variable is absent: `origin_of(tool, path)` if the file exists, else `"unknown"`. `machine` origin →
return without writing. `SessionStart` sets `started_at`; `SessionEnd` sets `ended_at` and
`user_msgs` (from `transcript.read`). Both set `tool, origin, cwd, transcript, branch, repo, worktree,
project, domain`. On `SessionStart` also call `daily.maybe_spawn()` — added in Task 8; until then
the call is absent.

hooks.json: add to `SessionStart` and `SessionEnd` a second entry
`bash "${CLAUDE_PLUGIN_ROOT}/hooks/run" session-pulse 9`, `"timeout": 10`. HANDLERS:
`"session-pulse": _lazy("session_pulse")`.

- [ ] **Step 1: Write the failing tests**

```python
# test_record.py  (H2T_MACHINE_NAME=test-machine; home is isolated by conftest)
def test_upsert_creates_then_merges_one_file(tmp_path, monkeypatch):
    p1 = record.upsert("u1", {"project": "unregistered", "started_at": "2026-10-19T10:00:00Z", "cwd": "C:/x"})
    p2 = record.upsert("u1", {"project": "unregistered", "started_at": "2026-10-19T11:00:00Z", "ended_at": "2026-10-19T12:00:00Z"})
    assert p1 == p2
    meta, _ = session_record.parse(p2.read_bytes())
    assert meta["started_at"] == "2026-10-19T10:00:00Z" and meta["ended_at"] == "2026-10-19T12:00:00Z" and meta["cwd"] == "C:/x"
def test_upsert_finds_record_in_another_project_dir(...):
    # created under unregistered/, upsert with project "x" → same file, meta["project"] == "x"
def test_project_of_unknown_is_unregistered(...)
def test_git_facts_of_a_worktree(tmp_path):
    # git init repo, git worktree add wt -b feat → git_facts(wt) == {"branch": "feat", "repo": str(repo), "worktree": str(wt)} (paths compared resolved)
def test_git_facts_outside_git_is_empty(tmp_path)

# test_session_pulse.py
def test_start_then_end_writes_one_record(...):   # codex transcript with originator codex-tui
def test_codex_exec_writes_nothing(...)            # originator codex_exec → no file under records/sessions
def test_subagent_writes_nothing(...)
def test_skip_env_writes_nothing(...)              # H2T_PULSE_SKIP=1
def test_handler_never_raises_on_missing_transcript(...)  # Codex transcript_path to a missing file → record with origin "unknown"
def test_claude_origin_from_entrypoint_without_transcript(...)  # CLAUDE_CODE_ENTRYPOINT=cli, no file → origin "live"
def test_end_records_user_msgs(...)                # SessionEnd on a transcript with 2 user msgs → meta["user_msgs"] == 2
def test_project_change_keeps_the_file(...)         # in test_record.py: unregistered/u1.md stays, meta["project"] == "x", index row project == "x"
def test_find_open(...)                             # one open codex record in C:/r → its id; two → None; ended → None
def test_registered_in_handlers_and_hooks_json():
    # "session-pulse" in HANDLERS; hooks.json SessionStart and SessionEnd both name it
```

- [ ] **Step 2: Run** `pytest tests/lifecycle/pulse/test_record.py tests/hooks/test_session_pulse.py -v` — Expected: FAIL on import
- [ ] **Step 3: Implement** `record.py`, `session_pulse.py`, the FIELDS change, HANDLERS, hooks.json.
- [ ] **Step 4: Run** the same command — Expected: all pass. Then the hook suites that pin hooks.json
  and the wrapper: `pytest tests/hooks tests/lifecycle/test_session_record.py -q` — Expected: pass
  (if `test_hooks_json.py` pins the entry count, extend it — record a ruling).
- [ ] **Step 5: Commit** `feat(pulse): record every session by its program UUID on start and end (#566)`

---

### Task 4: handoff writes into the UUID record

**Files:**
- Modify: `h2t_ops/lifecycle/handoff.py:131-237` (`write_handoff`),
  `h2t_ops/lifecycle/gather/sessions.py:40-53` (`_rows`)
- Test: `tests/lifecycle/pulse/test_handoff_uuid.py`

**Interfaces:**
- Consumes: `record.find`, `record.upsert`
- Produces: `def program_session() -> tuple[str, str] | None` in `record.py` —
  `CLAUDE_CODE_SESSION_ID` → `("claude", id)`; the Codex variable from Task 1 Step 2 →
  `("codex", id)`; no variable but `CODEX_*`-style marker of a Codex shell (from Task 1 Step 2) →
  `("codex", record.find_open("codex", os.getcwd()))` when that is not `None`; else `None`.

When `program_session()` returns an id: the record is `upsert(id, {...}, body=<the markdown body>)`
with `session_id=id`, `name=<the slug passed as --session-id>`, `tool`, plus the existing meta
(`domain`, `project`, `branch`, `commits`, `done`, `remains`, `artifacts`). The spool row keeps the
slug (`log_session_end` unchanged). The response JSON gains `"session_uuid"`. When it returns `None`:
today's path, unchanged.

- [ ] **Step 1: Write the failing tests**

```python
def test_handoff_with_claude_id_enriches_the_hook_record(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "u1")
    hook_path = record.upsert("u1", {"project": "unregistered", "started_at": "2026-10-19T10:00:00Z"})
    res = handoff.write_handoff("dev-x-topic-2026-10-19", "dev", "x", "- did", "- [ ] next", ["commit:abc1234"])
    assert res["markdown"] == str(hook_path) and res["session_uuid"] == "u1"
    meta, body = session_record.parse(hook_path.read_bytes())
    assert meta["name"] == "dev-x-topic-2026-10-19" and meta["started_at"] == "2026-10-19T10:00:00Z"
    assert meta["done"] == "- did" and b"## What Was Done" in body
    assert len(list(paths.records("sessions").rglob("*.md"))) == 1
def test_handoff_without_program_id_keeps_the_slug_file(...):
    # no env var → file named <slug>.md, session_id == slug (today's behaviour)
```

- [ ] **Step 2: Run** `pytest tests/lifecycle/pulse/test_handoff_uuid.py -v` — Expected: FAIL (`KeyError: 'session_uuid'`)
- [ ] **Step 3: Implement** `program_session` and the branch in `write_handoff`.
- [ ] **Step 4: Run** it, then `pytest tests/lifecycle tests/core/test_handoff_identity_from_cwd.py tests/core/test_session_identity_roundtrip.py -q` — Expected: pass (gather tests that seed records without `done` and expect them as "latest" need `done` added — a ruling each)
- [ ] **Step 5: Commit** `feat(handoff): write into the session's UUID record when the program id is known (#566)`

**Also in this task — keep session-start's "Previous Session" on the last handoff.** After Task 3
every session writes a record at start, and `_rows` in `h2t_ops/lifecycle/gather/sessions.py:40-53`
takes the newest record of the project with no filter: the briefing would show the current,
empty session. Add `AND COALESCE(done, '') <> ''` to that query. The current session's hook record
has no `done`, so it drops out with every other hook-only record. Test in
`tests/lifecycle/pulse/test_handoff_uuid.py`:

```python
def test_briefing_skips_hook_only_records(...):
    # handoff record (done set, updated 10:00) + hook record of the same project (no done, updated 11:00)
    # → find_latest_session_index(project)["session_id"] is the handoff's
```

Ruling to ledger: spec §5.1 says session-start also enriches the record; the hook now writes the
start, and session-start has nothing the record lacks, so session-start's writer is not changed;
only its reader is filtered (above). Cost if wrong: one more field write later.

---

### Task 5: Index schema v2

**Files:**
- Modify: `h2t_ops/lifecycle/index/schema.py`, `h2t_ops/lifecycle/index/build.py:29-31,111-121`
- Test: `tests/lifecycle/index/test_index.py` (add cases)

**Interfaces:**
- Produces:
  - `SCHEMA_VERSION = 2`
  - `sessions` gains columns, appended after `conflict`: `name, tool, origin, cwd, repo, worktree,
    started_at, ended_at, user_msgs, transcript, summary, summary_source, summary_stamp`
  - new table `branch_status(repo TEXT, branch TEXT, worktree TEXT, files TEXT, branch_state TEXT,
    pr TEXT, pr_url TEXT, issues TEXT, verdict TEXT, checked_at TEXT, PRIMARY KEY(repo, branch))`
  - `build._COLUMNS` extended in the same order; `_session_row` reads the new keys.

- [ ] **Step 1: Write the failing tests**

```python
def test_v2_columns_are_filled_from_the_record(...):
    # write a record with tool/cwd/origin/summary → after query.connect(), row["tool"] == "claude", row["origin"] == "live"
def test_v1_base_is_rebuilt(...):
    # create index.sqlite with meta schema_version '1' → connect() succeeds and meta says '2'
def test_branch_status_table_exists(...)
```

- [ ] **Step 2: Run** `pytest tests/lifecycle/index -v` — Expected: the 3 new tests FAIL
- [ ] **Step 3: Implement** the schema and build changes.
- [ ] **Step 4: Run** `pytest tests/lifecycle tests/setup -q` — Expected: pass
- [ ] **Step 5: Commit** `feat(index): schema 2 — session program fields and branch status (#566)`

---

### Task 6: Backfill from transcripts

**Files:**
- Create: `h2t_ops/lifecycle/pulse/backfill.py`
- Test: `tests/lifecycle/pulse/test_backfill.py`

**Interfaces:**
- Consumes: `transcript.read`, `transcript.is_subagent`, `record.find`, `record.upsert`, `record.project_of`, `record.git_facts`
- Produces: `def run(claude_root: Path, codex_root: Path, since_ns: int = 0) -> dict` →
  `{"seen": int, "written": int, "skipped_machine": int, "skipped_empty": int, "unknown": int}`.

Walk `claude_root/*/*.jsonl` (top level only — subagents live deeper) and `codex_root/**/*.jsonl`
whose `st_mtime_ns >= since_ns`. Skip subagents, `machine` origin, `user_msgs == 0`. For a session
already recorded: set `ended_at` to the transcript's last timestamp when it is later, and `origin`
when it was `unknown`. For a new one: write `tool, origin, cwd, transcript, started_at, ended_at,
project, domain` and `git_facts(cwd)` if the cwd still exists. Defaults: `~/.claude/projects`,
`~/.codex/sessions`.

- [ ] **Step 1: Write the failing tests**

```python
def test_backfill_writes_live_skips_machine_subagent_empty(tmp_path): ...
    # 1 live claude, 1 claude subagent, 1 codex_exec, 1 codex-tui, 1 claude with 0 user msgs
    # → written == 2, skipped_machine == 1, skipped_empty == 1; subagent not counted in seen
def test_backfill_updates_end_of_a_hook_record(tmp_path): ...
    # upsert("u1", ended_at missing) then backfill → meta["ended_at"] == last transcript timestamp
def test_backfill_is_idempotent(tmp_path): ...       # second run → written == 0 for unchanged, one file per id
def test_since_skips_old_files(tmp_path): ...
```

- [ ] **Step 2: Run** `pytest tests/lifecycle/pulse/test_backfill.py -v` — Expected: FAIL on import
- [ ] **Step 3: Implement** `backfill.run`.
- [ ] **Step 4: Run** it — Expected: 4 passed
- [ ] **Step 5: Commit** `feat(pulse): backfill sessions the hook missed from transcripts (#566)`

---

### Task 7: Work status per branch

**Files:**
- Create: `h2t_ops/lifecycle/pulse/status.py`
- Test: `tests/lifecycle/pulse/test_status.py`

**Interfaces:**
- Produces:
  - `def branch_state(repo: str, branch: str, base: str) -> str` → `"влита" | "не отправлена" | "отправлена" | "основная"`
  - `def verdict(files: str, state: str, pr: str) -> str` → one of the four labels
  - `def refresh(conn: sqlite3.Connection, *, gh=_gh) -> int` — one row per distinct `(repo, branch)`
    from `sessions` where `origin = 'live'`; returns rows written. `gh` is injectable:
    `gh(repo, args: list[str]) -> list | dict | None`.

Rules (spec §5.4, the designer's calls there):
- `files`: `git -C <worktree> status --porcelain` → `чисто` or `N незакоммиченных`; worktree missing → `нет копии`.
- `base`: `git -C repo symbolic-ref refs/remotes/origin/HEAD` short name, fallback `main`.
- `branch_state`: branch == base → `основная`; PR `MERGED` → `влита`; else every file in
  `git diff --name-only <merge-base> <branch>` has `git diff --quiet origin/<base> <branch> -- <file>`
  → `влита`; else `git rev-parse --verify origin/<branch>` fails → `не отправлена`; else `отправлена`.
  A branch with commits after its merged PR (`git rev-list --count <pr.headRefOid>..<branch>` > 0) is not `влита`.
- `pr`: `gh pr list --head <branch> --state all --json number,state,url --limit 1` → `нет | открыт | влит | закрыт`.
- `issues`: numbers from the record `artifacts` (`issue:N`), the branch name (`/(\d+)-` or `-(\d+)$`),
  `fixes|closes #N` in `git log <base>..<branch>` and in the PR body; each checked with
  `gh issue view N --json state`; stored as JSON `{"N": "open"|"closed"}`.
- `verdict`: `брошено с изменениями` if files is `N незакоммиченных`; else `готово` if state is
  `влита`, or `основная` with nothing ahead of `origin/<base>`; else `ждёт PR` if state is
  `отправлена`; else `не отправлено`.

- [ ] **Step 1: Write the failing tests** (real git repos in `tmp_path` with a bare `origin`; `gh` stubbed)

```python
def test_squash_merged_branch_is_merged(tmp_path): ...   # branch file content == origin/main content → "влита"
def test_unpushed_branch(tmp_path): ...                   # → "не отправлена", verdict "не отправлено"
def test_pushed_without_pr_waits(tmp_path): ...            # → verdict "ждёт PR"
def test_dirty_tree_is_abandoned_with_changes(tmp_path): ...  # → "брошено с изменениями"
def test_missing_worktree_does_not_crash(tmp_path): ...    # files == "нет копии"
def test_commits_after_merged_pr_are_not_merged(tmp_path): ...
def test_issue_numbers_from_branch_and_commits(tmp_path): ...  # "fix/123-x" + "closes #7" → {"123", "7"}
```

- [ ] **Step 2: Run** `pytest tests/lifecycle/pulse/test_status.py -v` — Expected: FAIL on import
- [ ] **Step 3: Implement** `status.py`; every subprocess with a timeout; a failed call yields `""`, never an exception.
- [ ] **Step 4: Run** it — Expected: 7 passed
- [ ] **Step 5: Commit** `feat(pulse): work status per branch — files, branch, PR, issues (#566)`

---

### Task 8: Terminal view and `h2t-ops sessions`

**Files:**
- Create: `h2t_ops/lifecycle/pulse/view.py`, `h2t_ops/lifecycle/pulse/cli.py`
- Modify: `h2t_ops/cli.py:30` (help line) and `:292-294` (route `sessions` to `pulse.cli.main(argv[1:])`)
- Test: `tests/lifecycle/pulse/test_view.py`

**Interfaces:**
- Consumes: `query.connect`, `branch_status`, `status.refresh`
- Produces:
  - `@dataclass class Filters: domain=None, project=None, repo=None, status=None, pr=None, tool=None, since=None, all=False`
  - `def rows(f: Filters) -> list[dict]` — sessions joined with `branch_status` on (repo, branch);
    hidden unless `all`: `origin` other than `live`, and `user_msgs` 0 or empty (spec anti-goal:
    no empty sessions); summary = `summary`, else first 3 lines of `done` with
    `summary_source='handoff'`.
  - `def settle_open() -> int` in `record.py` — for every record on this machine with no
    `ended_at` or with `origin: unknown`, whose transcript exists: `transcript.read` again and
    `upsert` `origin` and `user_msgs` when they changed (a `machine` result is written as
    `origin: machine` and stays hidden; records are never removed). `cli list` calls it before
    querying. So a running session appears once its first user message is in the transcript —
    within a minute (spec §8). Returns records changed.
  - `def local_status(conn, max_age_s: int = 600) -> int` added to `status.py` in this task —
    the git-only part of `status.refresh` (files, branch_state, verdict) for `(repo, branch)`
    pairs of live sessions with no `branch_status` row or `checked_at` older than `max_age_s`;
    keeps the stored `pr`, `issues`. No `gh`, no network. `cli list` calls it after
    `settle_open()`, so a new session has a status before the daily pass; PR data shows the
    time of its last `status`/daily run.
  - `def resume_command(tool: str, session_id: str, cwd: str) -> str`
  - `def render(rows: list[dict], footer: str) -> str` — grouping domain → project → repo → branch →
    sessions, newest first; branch line `<branch>  [<verdict>]  PR: <pr>  <files>`; session line
    `<started_at local>  <tool>  <summary or "—">` then the resume command on the next line.
  - `cli.main(argv) -> int` subcommands: `list` (default), `status` (runs `status.refresh`),
    `backfill`; list flags `--domain --project --repo --status --pr --tool --since --all --json`.
    Task 10 adds `daily`, Task 11 adds `page`.

- [ ] **Step 1: Write the failing tests**

```python
def test_resume_commands():
    assert view.resume_command("codex", "u1", "C:/r") == 'codex resume u1 -C "C:/r"'
    assert view.resume_command("claude", "u1", "C:/r") == 'cd "C:/r"; claude --resume u1'
@pytest.mark.parametrize("flt", ["domain", "project", "repo", "status", "pr", "tool", "since"])
def test_each_filter_narrows(flt, ...)       # 3 sessions across 2 domains/repos/branches/tools → only the matching ones
def test_unknown_hidden_unless_all(...)
def test_empty_session_hidden(...)           # user_msgs 0 → hidden (running or ended); --all shows it
def test_settle_open_reveals_a_running_session(...)   # hook record user_msgs 0, transcript now has 1 user msg → default list shows it
def test_settle_open_hides_a_machine_session(...)     # transcript says codex_exec → origin "machine", file still there, hidden
def test_list_is_offline_and_does_not_rebuild(monkeypatch, ...)
    # gh stub raises, socket.socket raises, query.rebuild raises → `cli.main(["list"])` exits 0
def test_new_session_gets_local_status_before_daily(...)  # no branch_status row → after list, row exists with files/verdict, pr ""
def test_handoff_done_is_the_summary(...)    # summary_source == "handoff"
def test_cli_list_exits_0_and_prints_resume(capsys, ...)
def test_empty_index_says_so(capsys, ...)     # "нет сессий" and exit 0 — an empty pulse is a state, not an error
```

- [ ] **Step 2: Run** `pytest tests/lifecycle/pulse/test_view.py -v` — Expected: FAIL on import
- [ ] **Step 3: Implement** `view.py`, `cli.py`, the `h2t_ops/cli.py` route.
- [ ] **Step 4: Run** it, then `pytest tests/cli tests/core/test_entrypoint_exit_codes.py -q` — Expected: pass
- [ ] **Step 5: Commit** `feat(pulse): h2t-ops sessions — list, filters, resume command (#566)`

---

### Task 9: Model summary

**Files:**
- Create: `h2t_ops/lifecycle/pulse/summary.py`
- Test: `tests/lifecycle/pulse/test_summary.py`

**Interfaces:**
- Consumes: `transcript.user_messages`, `transcript.last_assistant_text`, `record.upsert`
- Produces:
  - `def excerpt(tool: str, path: Path, limit: int = 12000) -> str` — user messages in order, then the
    last assistant text; truncated from the middle to `limit` chars.
  - `def run(conn, *, ask=_ask_claude, cap: int = 30) -> dict` → `{"written": n, "skipped": m}`; picks
    live sessions with no `done`, whose `summary_stamp` != `"<size>:<mtime_ns>"` of the transcript;
    writes `summary`, `summary_source: model`, `summary_stamp`.
  - `def _ask_claude(prompt: str) -> str` — `subprocess.run(["claude", "-p", "--model", "haiku",
    "--no-session-persistence"], input=prompt, env={**os.environ, "H2T_PULSE_SKIP": "1"}, timeout=120)`.
  Prompt (fixed copy): `"Ниже — запись рабочей сессии. Напиши 1–3 строки по-русски: о чём сессия и
  чем кончилась. Без вступления.\n\n" + excerpt`.

- [ ] **Step 1: Write the failing tests** (`ask` stubbed)

```python
def test_summary_written_once_per_transcript_state(...)   # second run → skipped; touch transcript → written again
def test_session_with_handoff_is_not_summarized(...)
def test_cap_limits_calls(...)                             # 5 candidates, cap=2 → ask called twice
def test_ask_runs_with_skip_env_and_no_persistence(monkeypatch)  # capture subprocess.run args/env
def test_excerpt_keeps_head_and_tail(tmp_path)
```

- [ ] **Step 2: Run** `pytest tests/lifecycle/pulse/test_summary.py -v` — Expected: FAIL on import
- [ ] **Step 3: Implement** `summary.py`.
- [ ] **Step 4: Run** it — Expected: 5 passed
- [ ] **Step 5: Commit** `feat(pulse): daily one-to-three line summary by a cheap model (#566)`

---

### Task 10: Daily pass, its trigger, and the audit_map line

**Files:**
- Create: `h2t_ops/lifecycle/pulse/daily.py`
- Modify: `h2t_ops/hooks/session_pulse.py` (call `daily.maybe_spawn()` on `SessionStart`),
  `h2t_ops/lifecycle/pulse/view.py` (`footer()`)
- Test: `tests/lifecycle/pulse/test_daily.py`

**Interfaces:**
- Produces:
  - `STAMP = paths.state_dir() / "pulse-daily.json"` → `{"ran_at": ISO, "backfill_since_ns": int, "audit_map": {...}}`
  - `def run() -> dict` — backfill(since = previous `backfill_since_ns` minus 1 day) → index refresh →
    `status.refresh` → `summary.run` → `audit_map()`; writes STAMP via `store.replace(place="state")`.
  - `def maybe_spawn(now=None) -> bool` — STAMP older than 24 h or missing → take
    `store.create(paths.state_dir() / "pulse-daily.lock", ...)`; on `AlreadyExists` with lock mtime < 2 h
    return False; spawn `[sys.executable, "-m", "h2t_ops.cli", "sessions", "daily"]` detached
    (Windows: `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`; POSIX: `start_new_session=True`), stdio to
    `DEVNULL`; return True. `run()` removes the lock at the end.
  - `def audit_map() -> dict` — argv from `user_config.get("sessions.audit_map")`; None → `{}`;
    runs it with `--out <state>/audit-map.tsv`; sums `branch_count - 1` and `stash_count` over rows →
    `{"branches": n, "stash": m, "report": path, "ran_at": iso}`.
  - `view.footer() -> str` — `Работа без сессии: N веток, M stash — <report> (<date>)`, or
    `Работа без сессии: audit_map не настроен (sessions.audit_map в config/user.yaml)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_maybe_spawn_once_a_day(monkeypatch, tmp_path)   # Popen stubbed: fresh stamp → no call; old stamp → one call; second call within lock → no call
def test_run_calls_stages_in_order(monkeypatch)          # stub backfill/status/summary/audit_map, assert order and STAMP written
def test_audit_map_counts(tmp_path, monkeypatch)         # user.yaml argv to a fake script that writes a 2-row TSV → branches/stash sums
def test_footer_without_config()
```

- [ ] **Step 2: Run** `pytest tests/lifecycle/pulse/test_daily.py -v` — Expected: FAIL on import
- [ ] **Step 3: Implement** `daily.py`, the hook call, `footer()`.
- [ ] **Step 4: Run** `pytest tests/lifecycle/pulse tests/hooks -q` — Expected: pass; the
  `SessionStart` budget in `tests/hooks/test_budgets.py` still holds (spawn is a fork, not a wait).
- [ ] **Step 5: Commit** `feat(pulse): daily pass started by the first session of the day (#566)`

---

### Task 11: Browser page

**Files:**
- Create: `h2t_ops/lifecycle/pulse/page.py`
- Test: `tests/lifecycle/pulse/test_page.py`

**Interfaces:**
- Consumes: `view.rows(Filters(all=True))`, `view.footer()`, `view.resume_command`
- Produces: `def build(out: Path | None = None) -> Path` — one self-contained HTML file
  (`state/sessions.html` by default, `store.replace(place="state")`), data embedded as
  `<script type="application/json" id="data">`, vanilla JS filters (domain, project, repo, status,
  PR, tool, date-from, show unknown), the same grouping as the terminal, a copy button per resume
  command. No network requests. `h2t-ops sessions page` builds it and opens it with
  `webbrowser.open(path.as_uri())` unless `--no-open`.

- [ ] **Step 1: Write the failing tests**

```python
def test_page_embeds_rows_and_resume_commands(...)   # parse the JSON block back → resume strings present
def test_page_has_no_external_urls(...)              # no "http://" or "https://" in the output
def test_page_escapes_summary_html(...)              # summary "<script>" stays inert ("</" escaped inside the JSON block)
```

- [ ] **Step 2: Run** `pytest tests/lifecycle/pulse/test_page.py -v` — Expected: FAIL on import
- [ ] **Step 3: Implement** `page.py` and the `page` subcommand.
- [ ] **Step 4: Run** it — Expected: 3 passed
- [ ] **Step 5: Commit** `feat(pulse): static browser page over the same index (#566)`

---

### Task 12: Codex install note, stale line, acceptance

**Files:**
- Create: `plugins/h2t-core/references/session-pulse.md`
- Modify: `plugins/h2t-core/references/version-check.md:81`
- Modify: `docs/superpowers/specs/2026-10-19-session-pulse.md` (§8 results)

- [ ] **Step 1:** Write `session-pulse.md`: the commands; the Codex hook entry for
  `~/.codex/hooks.json` (`SessionStart` and `SessionEnd` → `h2t-hook session-pulse`, timeout 10);
  "trust it once in `/hooks`, again after every change"; `sessions.audit_map` in `config/user.yaml`.
- [ ] **Step 2:** Fix `version-check.md:81` to say Codex runs hooks (Codex ≥ 0.153, `hooks` stable)
  and that this pack's Codex hook is installed by hand per `session-pulse.md`.
- [ ] **Step 3: Full suite and lint**
  `pytest tests/ -q` → pass; `ruff check plugins/ lib/ h2t_ops/ tests/ scripts/` → `All checks passed!`;
  `uv run h2t-docs-lint doctor` → no new findings against the 2026-08-24 baseline.
- [ ] **Step 4: Acceptance (spec §8), with the author** after deploy (`uv tool install --editable`,
  plugin from the checkout):
  1. New Claude session, no skill → within a minute `h2t-ops sessions --since today` shows it with
     tool, cwd, project and the resume line.
  2. Run that resume line in a new terminal → the same conversation opens.
  3. `codex` TUI session (hook trusted) → appears the same way.
  4. `h2t-ops sessions --all --json` contains no `agent-*` transcript and no `codex_exec` originator
     (command output shown).
  5. `h2t-ops sessions --status "не отправлено"` lists `docs/session-pulse-design` until it is pushed.
  6. `h2t-ops sessions page` opens; filters work; no console errors.
- [ ] **Step 5: Commit** `docs(pulse): Codex hook install, version-check fix, acceptance results (#566)`
