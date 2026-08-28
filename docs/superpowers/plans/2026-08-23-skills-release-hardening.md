---
title: "Skills release hardening"
status: "done"
date: "2026-08-23"
milestone: ""
issue: ""
---

# Skills Release Hardening Implementation Plan

> **Status: complete (2026-08-24).** All twelve tasks landed. Wave 1 (1–5) in #397, Wave 2
> (6–12) in #398, and Task 11 as PR #339 itself. The step checkboxes below were closed at
> **task** granularity — each task's deliverable was re-verified on `main` on 2026-08-24 (one
> `gather.py` in the tree, `h2t-gather --cwd /nonexistent` exiting 3 with the reason on stderr,
> `h2t-hook` among the nine entry points, `create_latest_link` gone, `packages = ["h2t_ops"]`
> with the payload force-included) — not by re-running each TDD micro-step. Read a tick as
> "this task's outcome is present on main", not as "this keystroke was replayed".

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one behaviour reachable by exactly one code path, so that what a skill does no
longer depends on which entry point invoked it — then release.

**Architecture:** `h2t_ops/plugin_entrypoints.py` already defines the intended design: the CLI
is a thin shim that locates the *plugin's* script through a five-step ladder (operator override
→ `CLAUDE_PLUGIN_ROOT` → editable checkout → installed plugin cache → frozen wheel payload) and
runs it. One implementation, several ways in. Three places bypass that ladder and each grew its
own behaviour. This plan removes the bypasses rather than adding synchronisation.

**Tech Stack:** Python 3.11, pytest, hatchling wheel with `force-include` payload, Claude Code
plugin marketplace, bash hook handlers.

**Spec:** none — this plan argues from measurements recorded in each task's *Evidence* block,
taken on `main` at 6b9fcd3 plus PR #391. Re-run any probe to confirm before changing code.

## Global Constraints

- Interpreter differs per machine. Mac: `.venv/bin/pytest`, `.venv/bin/python`, `uvx ruff`.
  Windows: `C:/dev/h2t-skills/.venv/Scripts/pytest`. Bare `python` does not exist on the Mac.
- `lib/gather`, `lib/eval`, `lib/activity` are vendored to `plugins/h2t-core/lib/` and guarded
  by `tests/core/test_vendored_lib_parity.py`, which requires **byte-identical** files. Every
  change to one copy must be made to the other in the same commit.
- No `&&` chaining in Bash tool calls (CLAUDE.md).
- A red local suite is usually a stale venv, not the repo. CI installs the project with
  `pip install -e .` and is green. On the Mac the venv is built by `uv` and ships neither
  `ruamel.yaml` (declared at `pyproject.toml:22`) nor `pip` (which `test_wheel_payload.py`
  shells out to). Fix the environment before diagnosing the code:
  `uv pip install --python .venv/bin/python "ruamel.yaml>=0.18" pip`. Baseline after that:
  `1938 passed, 7 skipped`.
- Deploy is not `update-plugin.sh`. Commit → `git push origin main` →
  `/plugin marketplace update lichtpfad` → `/reload-plugins`. Verify by reading the cache, not
  by reading the command's output.
- Every version bump goes through `python scripts/bump_plugin.py <plugin> <semver>`.

## File Structure

| File | Responsibility after this plan |
|---|---|
| `h2t_ops/plugin_entrypoints.py` | the only resolver; unchanged |
| `h2t_ops/cli.py` | `gather` stops routing to `_legacy` (Task 1) |
| `lib/cli/main.py` | its `gather` subcommand is deleted (Task 1) |
| `plugins/h2t-core/skills/session-start/scripts/gather.py` | the single gather implementation; gains cwd validation (Task 2) |
| `plugins/h2t-core/hooks-handlers/gather-on-skill` | prefers `h2t-gather`, falls back to the script (Task 3) |
| `.github/workflows/*.yml` | runs every plugin test directory (Task 4) |
| `plugins/h2t-core/skills/scaffold-project/SKILL.md` | calls `h2t-scaffold-project` (Task 5) |
| `lib/gather/project.py` + vendored copy | reads `.claude/project-id` first (Task 6) |
| `tests/core/test_handoff_no_prewrite_gate.py` | generalised to every skill (Task 7) |

---

## Wave 1 — release blockers

### Task 1: One gather implementation

**Evidence (measured 2026-08-23, same repo, same minute):**

```bash
$ h2t-ops gather session-start --cwd "$(pwd)" --briefing-only | grep -c "Previous Session"
0
$ h2t-gather --cwd "$(pwd)" --briefing-only | grep -c "Previous Session"
1
```

`h2t_ops/cli.py:186` routes `gather` to `_legacy`, which imports `lib/cli/main.py` — a second
gather that never learned `find_latest_session_index` (added to the plugin script only).
`grep -c find_latest_session_index`: `lib/cli/main.py` → 0, plugin script → 3.

**Files:**
- Modify: `h2t_ops/cli.py:186-187`
- Modify: `plugins/h2t-core/skills/session-start/scripts/gather.py` — add `--skill`
- Modify: `lib/cli/main.py` — delete `_cmd_gather`, `_run_gather` and the `gather` subparser
- Test: `tests/core/test_gather_single_implementation.py` (create)

**The contract that must survive.** `lib/cli/main.py` today accepts an *optional* positional
skill (`gather_parser.add_argument("skill", nargs="?", default="")`), never validates it, uses
it only for eval attribution (`SkillEval(skill, ...)`), and refuses an empty one:

```python
# lib/cli/main.py:125
def _cmd_gather(args):
    if not args.skill:
        print("error: gather requires a skill name (e.g. session-start, handoff)", file=sys.stderr)
        return 2
```

The plugin script has no positional at all and hardcodes `SkillEval("session-start", ...)` at
line 136. So the reroute must (a) keep `exit 2` with that exact message when no skill is given,
(b) forward the skill name for eval attribution, and (c) **keep accepting an unrecognised skill
name** — legacy never validated it, and adding validation here is a behaviour change this task
does not own.

**Interfaces:**
- Consumes: `h2t_ops.plugin_entrypoints.run_plugin_main(relative_path: str) -> int`
- Produces: `gather.py` gains `--skill <name>` (default `session-start`), replacing the
  hardcoded literal at line 136. `h2t-ops gather <skill> [--cwd] [--format-briefing]
  [--briefing-only]` keeps its argv shape and its exit codes.

- [x] **Step 1: Write the failing tests**

```python
# tests/core/test_gather_single_implementation.py
"""`h2t-ops gather` and `h2t-gather` must be the same program.

They were not: h2t-ops routed to lib/cli/main.py, which never gained
find_latest_session_index, so its briefing silently lacked "### Previous Session".
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run(argv):
    env = dict(os.environ, H2T_EVALS_MODE="off")
    return subprocess.run([sys.executable, "-m", *argv], capture_output=True,
                          text=True, cwd=ROOT, env=env, check=False)


def test_both_entry_points_produce_the_same_briefing():
    via_ops = _run(["h2t_ops.cli", "gather", "session-start",
                    "--cwd", str(ROOT), "--briefing-only"])
    via_gather = _run(["h2t_ops.gather_entry", "--cwd", str(ROOT), "--briefing-only"])
    assert via_ops.returncode == 0, via_ops.stderr
    assert via_gather.returncode == 0, via_gather.stderr
    assert via_ops.stdout == via_gather.stdout


def test_missing_skill_still_exits_2():
    result = _run(["h2t_ops.cli", "gather"])
    assert result.returncode == 2, (result.returncode, result.stdout[:200])
    assert "requires a skill name" in result.stderr


def test_a_leading_flag_is_not_eaten_as_the_skill():
    """`h2t-ops gather --cwd X` has no skill; --cwd must not be consumed as one."""
    result = _run(["h2t_ops.cli", "gather", "--cwd", str(ROOT), "--briefing-only"])
    assert result.returncode == 2, (result.returncode, result.stdout[:200])
    assert "requires a skill name" in result.stderr


def test_an_unrecognised_skill_is_still_accepted():
    """Legacy never validated the name; this task does not start."""
    result = _run(["h2t_ops.cli", "gather", "nosuch-skill",
                   "--cwd", str(ROOT), "--briefing-only"])
    assert result.returncode == 0, result.stderr
    assert "BRIEFING:" in result.stdout
```

- [x] **Step 2: Run them and read every failure text**

Run: `.venv/bin/pytest tests/core/test_gather_single_implementation.py -q`
Expected: `test_both_entry_points_produce_the_same_briefing` FAILS on differing stdout — the
`h2t-ops` side missing `### Previous Session`. The other three PASS against the unchanged
code: they are the contract you must not break, not new behaviour. If any of the three fails
now, the contract is not what this plan describes — stop and re-read `lib/cli/main.py:125`.

- [x] **Step 3: Give the plugin script the skill name**

```python
# plugins/h2t-core/skills/session-start/scripts/gather.py, in main()
    parser.add_argument("--skill", default="session-start")
```

and at line 136 replace the literal:

```python
        with SkillEval(args.skill, domain=domain, project=proj_id) as ev:
```

- [x] **Step 4: Route `gather` through the resolver, parsing argv instead of slicing it**

```python
# h2t_ops/cli.py — replace lines 186-187
    if argv and argv[0] == "gather":
        from h2t_ops.plugin_entrypoints import run_plugin_main
        rest = list(argv[1:])
        skill = rest.pop(0) if rest and not rest[0].startswith("-") else ""
        if not skill:
            print("error: gather requires a skill name (e.g. session-start, handoff)",
                  file=sys.stderr)
            return 2
        sys.argv = ["h2t-gather", "--skill", skill, *rest]
        return run_plugin_main("skills/session-start/scripts/gather.py")
```

`argv[2:]` would be wrong: `h2t-ops gather --cwd X` has no positional, and slicing would drop
`--cwd` silently.

- [x] **Step 5: Delete the second implementation**

Remove `_cmd_gather`, `_run_gather` and the `gather` subparser from `lib/cli/main.py`, and
update the module docstring to say gather now lives in the plugin script. Do **not** touch
`packages` in `pyproject.toml:37`: `tests/core/test_wheel_payload.py::
test_wheel_ships_the_lib_those_scripts_import` asserts `lib` is shipped, so unshipping it is
its own change — decision 3 below.

- [x] **Step 6: Run the test and the suites it can break**

Run: `.venv/bin/pytest tests/ lib/ -q`
Expected: all four new tests pass; `test_gather_on_skill_hook.py` and
`test_gather_on_prompt_hook.py` stay green; baseline count rises from 1938 by the new tests.

- [x] **Step 7: Commit**

```bash
git add h2t_ops/cli.py lib/cli/main.py \
        plugins/h2t-core/skills/session-start/scripts/gather.py \
        tests/core/test_gather_single_implementation.py
git commit -m "fix(cli): h2t-ops gather runs the plugin script, not a stale second copy"
```

---

### Task 2: Gather fails loudly on an unusable cwd

**Evidence (measured 2026-08-23):**

```bash
$ h2t-gather --cwd /nonexistent/whatever --briefing-only
BRIEFING:
## Сессия: unknown (``)
### Контекст
Handoff-файлы: 1
$ echo $?
0
```

A path that does not exist yields exit 0 and a plausible briefing for project `unknown`,
whose one "handoff file" comes from the `~/.h2t/sessions/<machine>/unknown/` directory. This is
the case `.claude/rules/verification.md` names: a zero that means "broken instrument", not
"nothing found".

**Files:**
- Modify: `plugins/h2t-core/skills/session-start/scripts/gather.py` — `main()`
- Test: `tests/core/test_gather_rejects_bad_cwd.py` (create)

**Interfaces:**
- Produces: exit code `3` (config, per the connector taxonomy in CLAUDE.md) on an unusable cwd,
  with the reason on stderr and nothing on stdout

- [x] **Step 1: Write the failing test**

```python
# tests/core/test_gather_rejects_bad_cwd.py
"""A cwd that does not exist is a broken instrument, not an empty result."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATHER = ROOT / "plugins" / "h2t-core" / "skills" / "session-start" / "scripts" / "gather.py"


def _run(cwd_arg):
    env = dict(os.environ, H2T_EVALS_MODE="off")
    return subprocess.run([sys.executable, str(GATHER), "--cwd", cwd_arg, "--briefing-only"],
                          capture_output=True, text=True, env=env, check=False)


def test_nonexistent_cwd_exits_config_error(tmp_path):
    result = _run(str(tmp_path / "no-such-dir"))
    assert result.returncode == 3, (result.returncode, result.stdout[:200])
    assert "BRIEFING:" not in result.stdout
    assert "no-such-dir" in result.stderr


def test_real_cwd_still_succeeds(tmp_path):
    """The control: the same probe must return 0 where the directory exists."""
    result = _run(str(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "BRIEFING:" in result.stdout
```

- [x] **Step 2: Run it to confirm the first test fails and the control passes**

Run: `.venv/bin/pytest tests/core/test_gather_rejects_bad_cwd.py -q`
Expected: `test_nonexistent_cwd_exits_config_error` FAILS with `(0, 'BRIEFING:...')`;
`test_real_cwd_still_succeeds` PASSES. A run where both fail means the probe is wrong.

- [x] **Step 3: Validate in `main()`**

```python
# plugins/h2t-core/skills/session-start/scripts/gather.py, first lines of main() after parse_args
    cwd = Path(args.cwd).expanduser()
    if not cwd.is_dir():
        print(f"gather: --cwd is not a directory: {args.cwd}", file=sys.stderr)
        sys.exit(3)
```

- [x] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/core/test_gather_rejects_bad_cwd.py tests/core/ -q`
Expected: PASS, and no regression in the hook tests, which pass a real cwd.

- [x] **Step 5: Commit**

```bash
git add plugins/h2t-core/skills/session-start/scripts/gather.py tests/core/test_gather_rejects_bad_cwd.py
git commit -m "fix(gather): exit 3 on an unusable --cwd instead of briefing an unknown project"
```

---

### Task 3: The hook resolves through the same ladder

**Evidence:** `plugins/h2t-core/hooks-handlers/gather-on-skill:116` runs
`"$PLUGIN_ROOT/skills/session-start/scripts/gather.py"` directly, pinning the hook to the
plugin cache. `h2t-gather` instead walks the ladder in `plugin_entrypoints.py` and prefers an
editable checkout (step 3) over the cache (step 4). Measured on 2026-08-23: `h2t-handoff
write --help` already showed the flags added in PR #391 while
`grep -c resolve_identity <cache>/3.2.22/skills/handoff/scripts/writer.py` returned 0. Which
code runs therefore depends on the entry path.

**Files:**
- Modify: `plugins/h2t-core/hooks-handlers/gather-on-skill:110-120`
- Test: `tests/core/test_gather_on_skill_hook.py` (extend)

**Interfaces:**
- Consumes: `h2t-gather --cwd <path> --briefing-only` (Task 1 and 2 keep its contract)
- Produces: no new interface; the hook still emits `BRIEFING:` / `GATHER_META:` or
  `GATHER_ERROR:`

- [x] **Step 1: Write the failing test**

```python
def test_hook_prefers_the_installed_cli(tmp_path, monkeypatch):
    """A shim named h2t-gather on PATH must be what the hook calls.

    The direct script path stays as the fallback for a machine where the wheel was never
    installed — that is what `command -v h2t-gather` in every SKILL.md already assumes.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    marker = tmp_path / "called"
    shim = bin_dir / "h2t-gather"
    shim.write_text(
        "#!/bin/sh\n"
        f"echo called > {marker}\n"
        "echo 'BRIEFING:'\necho 'shim briefing'\n"
        "echo ''\necho 'GATHER_META: {}'\n"
    )
    shim.chmod(0o755)
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}")
    _run_hook(env=env, cwd=tmp_path)          # existing helper in this file
    assert marker.exists(), "hook bypassed h2t-gather and ran the script directly"
```

- [x] **Step 2: Run it to confirm it fails**

Run: `.venv/bin/pytest tests/core/test_gather_on_skill_hook.py -q -k prefers`
Expected: FAIL — the marker file is absent because the hook ran the script.

- [x] **Step 3: Prefer the CLI, keep the script as fallback**

```bash
# plugins/h2t-core/hooks-handlers/gather-on-skill — replace the run_script call at :116
if command -v h2t-gather >/dev/null 2>&1; then
  if ! run_cli h2t-gather --cwd "$cwd" --briefing-only; then
    emit "GATHER_ERROR: h2t-gather failed. ${SCRIPT_STDERR:-no stderr}"
    exit 0
  fi
elif ! run_script "$PLUGIN_ROOT/skills/session-start/scripts/gather.py" --cwd "$cwd" --briefing-only; then
  emit "GATHER_ERROR: gather.py failed. ${SCRIPT_STDERR:-no stderr}"
  exit 0
fi
```

`run_cli` is `run_script` with the `H2T_PYTHON_CMD` prefix dropped. Add it directly beside
`run_script`, keeping the tempfile capture identical so `SCRIPT_STDOUT`, the 500-byte
`SCRIPT_STDERR` tail, and the `set +e` / `set -e` window all behave exactly as before:

```bash
run_cli() {
  local out err rc
  out=$(mktemp)
  err=$(mktemp)
  set +e
  "$@" >"$out" 2>"$err"
  rc=$?
  set -e
  SCRIPT_STDOUT=$(cat "$out")
  SCRIPT_STDERR=$(tail -c 500 "$err")
  rm -f "$out" "$err"
  return "$rc"
}
```

The empty-output guard that follows the call site (`if [ -z "$SCRIPT_STDOUT" ]`) must stay
reachable on both branches — do not move it inside the `if`.

- [x] **Step 4: Run the hook tests**

Run: `.venv/bin/pytest tests/core/test_gather_on_skill_hook.py tests/core/test_gather_on_prompt_hook.py -q`
Expected: PASS, including the existing cases that assert the fallback still works with an
empty PATH.

- [x] **Step 5: Commit**

```bash
git add plugins/h2t-core/hooks-handlers/gather-on-skill tests/core/test_gather_on_skill_hook.py
git commit -m "fix(hooks): gather through h2t-gather so hook and skill resolve one root"
```

---

### Task 4: Every plugin test directory runs in CI (#381)

**Evidence:** `.github/workflows/*.yml` runs `lib/`, `tests/`, and exactly two plugin script
directories (`autonomous-run`, `init-project`). Ten directories holding roughly 26 test files
never run — the largest is `plugins/h2t-creative/tests` with 14 files, and the 25 meetgeek
tests merged in #389/#390 are among them. Nobody knows whether those directories are green:
they have not executed on GitHub since they were written.

**Files:**
- Modify: `.github/workflows/h2t-evals-gate.yml` — the `unit-tests` job
- Modify: `plugins/h2t-ops/skills/research/tests/conftest.py` (create),
  `plugins/h2t-arch/skills/drawio/scripts/test_export.py`,
  `plugins/h2t-arch/skills/drawio/scripts/test_generate.py`,
  `plugins/h2t-ops/skills/connectors/scripts/test_connectors_surface.py`,
  `plugins/h2t-arch/skills/drawio/SKILL.md` (the `compatibility:` line)
- Test: the CI run itself; plus `tests/core/test_ci_covers_plugin_tests.py` (create)
- **Do not touch `pyproject.toml` in this task.** Nothing is missing from it.

**Interfaces:**
- Produces: a test that fails when a new plugin test directory is added without a CI step

- [x] **Step 1: Write the failing test**

```python
# tests/core/test_ci_covers_plugin_tests.py
"""A test directory nobody runs is documentation, not a test.

25 meetgeek tests landed in #389/#390 and have never executed on GitHub.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _dirs_with_tests():
    found = set()
    for path in (ROOT / "plugins").rglob("test_*.py"):
        found.add(path.parent.relative_to(ROOT).as_posix())
    return sorted(found)


def test_every_plugin_test_dir_is_named_in_a_workflow():
    workflow_text = "\n".join(p.read_text(encoding="utf-8") for p in WORKFLOWS.glob("*.yml"))
    missing = [d for d in _dirs_with_tests() if d not in workflow_text]
    assert not missing, f"plugin test dirs never run in CI: {missing}"
```

- [x] **Step 2: Run it to confirm it fails and read the list**

Run: `.venv/bin/pytest tests/core/test_ci_covers_plugin_tests.py -q`
Expected: FAIL listing ten directories. Copy that list — it is the input to Step 3.

- [x] **Step 3: Fix the three directories that are red today**

Measured 2026-08-23 by running each directory locally. Eight of ten are green — 1185 tests
that CI has never executed. The three red ones have known, bounded causes; none is rot:

| Directory | Result | Cause |
|---|---|---|
| `plugins/h2t-ops/skills/research/tests` | 24 failed, 144 passed | `FileNotFoundError: h2t_secrets module not found. Tried: []` — the script resolves `h2t_secrets` from `H2T_PLUGIN_ROOT` or `plugins/h2t-core/scripts/h2t_secrets.py`, and the tests set neither. Add a `conftest.py` in that directory setting `H2T_PLUGIN_ROOT` to the repo's `plugins/h2t-core`. Do not weaken the assertions. |
| `plugins/h2t-arch/skills/drawio/scripts` | 2 collection errors | `ModuleNotFoundError: No module named 'drawpyo'` — an undeclared optional dependency. Add `pytest.importorskip("drawpyo")` at the top of both test modules, and name `drawpyo` in the drawio skill's `compatibility:` line so the gap is documented rather than silent. |
| `plugins/h2t-ops/skills/connectors/scripts` | 1 failed, 16 passed | `test_connectors_skill_exists_and_is_bounded` asserts `name: h2t-ops:connectors` in the frontmatter. `tests/core/test_skill_frontmatter.py` asserts the opposite — the name must be the bare directory name, because the harness prepends the plugin itself (`/h2t-core:h2t-core:handoff` otherwise). The frontmatter is correct; fix the assertion to `name: connectors` and reference the frontmatter test in its docstring. |

Run each one green before Step 4 wires it into CI, so no known-red step is ever committed:
`.venv/bin/pytest plugins/h2t-ops/skills/research/tests -q`

- [x] **Step 4: Add one pytest step per directory, all of them now green**

Append to the `unit-tests` job in `.github/workflows/h2t-evals-gate.yml`, after the existing
`plugins/h2t-core/skills/init-project/scripts` step, one step per directory Step 2 listed:

```yaml
      - name: Plugin tests — h2t-creative
        run: python -m pytest plugins/h2t-creative/tests -q
```

Do not collapse them into one `pytest plugins/` invocation: these directories have no shared
conftest and several add their own `sys.path` entries, so a single run cross-contaminates them.

- [x] **Step 5: Confirm the local baseline is the environment, not the repo**

No dependency is missing from `pyproject.toml`; `ruamel.yaml>=0.18` is declared at line 22 and
CI has been green throughout. Sync the venv instead:

Run: `uv pip install --python .venv/bin/python "ruamel.yaml>=0.18" pip` followed by
`.venv/bin/pytest tests/ lib/ -q`
Expected: **no failures and no errors**. Do not assert a count: the baseline was
`1938 passed, 7 skipped` on 2026-08-23 before Wave 1, and every task in this plan adds tests,
so the number only ever grows. If anything is red, it is your change.

- [x] **Step 6: Run everything**

Run: `.venv/bin/pytest tests/ lib/ -q`
Expected: 0 failures, 0 errors. Then run each newly added plugin directory locally and record
which ones are red — a directory that was never in CI may have been red for months. Fix or
`xfail` with a reason and an issue number; do not delete tests to make CI green.

- [x] **Step 7: Commit**

```bash
git add .github/workflows tests/core/test_ci_covers_plugin_tests.py \
        plugins/h2t-ops/skills/research/tests/conftest.py \
        plugins/h2t-arch/skills/drawio/scripts plugins/h2t-arch/skills/drawio/SKILL.md \
        plugins/h2t-ops/skills/connectors/scripts
git commit -m "test(ci): run every plugin test directory (#381)"
```

---

### Task 5: The gate invariant, stated once and enforced everywhere

**Evidence:** an audit of every shipped `SKILL.md` found seven interactive gates. Six guard an
outward or irreversible action and are correct:

| Gate | Guards | Verdict |
|---|---|---|
| `session-start:102` | naming, at session start with the user present | keep |
| `project-audit:315` | generating docs for a structurally broken repo | keep |
| `project-audit:397` | writing files into the user's repo | keep |
| `setup:187` | waiting for the user to paste secrets | keep |
| `docs-lint:140` | mutating docs on a dirty worktree | keep |
| `handoff:202` | rule promotion — stands *after* the record is written | keep |
| `handoff:26` | **the session name, before the record is written** | removed in PR #391 |

The seventh was the only one of its class: a gate standing between work already produced and
its persistence. That class must not come back.

**Files:**
- Modify: `tests/core/test_handoff_no_prewrite_gate.py` — generalise
- Modify: `plugins/h2t-core/skills/handoff/SKILL.md` — no change if PR #391 is merged
- Create: `.claude/rules/gates.md`

**Interfaces:**
- Consumes: nothing
- Produces: `.claude/rules/gates.md`, quoted by future skill reviews

- [x] **Step 1: Write the rule**

```markdown
# Gate Rules

A gate may guard an action that reaches outside the session — writing into the user's repo,
sending, deleting, spending. It may never stand between work already produced and its
persistence.

Handoff asked for a session name after composing a full summary. The user was asleep; the
record was lost and the summary with it (2026-08-23). A wrong name costs one rename; an
unanswered question costs the session.

Where a value is missing, derive it and say what you derived. Ask afterwards.
```

- [x] **Step 2: Extend the test to every skill that writes**

```python
WRITERS = {
    "h2t-core/skills/handoff": "h2t-handoff write",
    "h2t-core/skills/init-project": "h2t-project-register",
}

@pytest.mark.parametrize(("skill", "write_call"), sorted(WRITERS.items()))
def test_nothing_blocks_before_the_write(skill, write_call):
    """A textual tripwire, not a proof.

    It catches the two phrasings that have actually appeared — "wait for" and a ⛔ GATE
    marker — in the text preceding the FIRST occurrence of the write call. It cannot see a
    gate phrased a third way, a gate reached through a variable, or one in a referenced
    file. The rule in .claude/rules/gates.md is the invariant; this only stops the two
    known regressions. Widen BLOCKING when a third phrasing appears; do not claim the
    invariant is mechanically enforced.
    """
    manifest = ROOT / "plugins" / skill / "SKILL.md"
    text = manifest.read_text(encoding="utf-8")
    index = text.find(write_call)
    assert index != -1, f"{manifest} no longer calls `{write_call}`"
    offenders = [p.pattern for p in BLOCKING if p.search(text[:index])]
    assert not offenders, f"{manifest} blocks on the user before `{write_call}`: {offenders}"
```

The same honesty belongs in `.claude/rules/gates.md`: the rule is enforced by review, and the
test only closes the two regressions seen so far.

- [x] **Step 3: Run it**

Run: `.venv/bin/pytest tests/core/test_handoff_no_prewrite_gate.py -q`
Expected: PASS for handoff (PR #391 removed its gate). If `init-project` fails, read its gate
and classify it with the table above before touching it — it may be a legitimate outward gate,
in which case remove it from `WRITERS` and record why in the docstring.

- [x] **Step 4: Commit**

```bash
git add .claude/rules/gates.md tests/core/test_handoff_no_prewrite_gate.py
git commit -m "docs(rules): a gate guards an outward action, never a pending write"
```

---

## Wave 2 — consistency, can slip past the release

### Task 6: scaffold-project calls its own entry point

**Evidence — re-measured 2026-08-23, and it is not what this task first claimed.** The gate is
already present. `plugins/h2t-core/skills/scaffold-project/SKILL.md:29-31`:

```bash
for _cmd in h2t-scaffold-project h2t-project-register; do
    command -v "$_cmd" >/dev/null 2>&1 || { echo "ERROR: $_cmd not found. Run /h2t-core:setup"; exit 1; }
done
```

The other four skills spell it out one command per line (`handoff:15`, `session-start:17,21`,
`init-project:19`, `project-audit:17`). Same guarantee, different shape — so a test asserting
the literal string `command -v h2t-scaffold-project` would fail on a skill that is correct.

What is actually wrong is the `$H2T_PYTHON` block, and it is dead rather than merely
non-standard. `SKILL.md:25-27` defines the variable; its only use is `:212`, inside a snippet
that cancels itself — `open(... if False else ...)`, `2>/dev/null || true`, and the next line
of prose reads *"Actually — skip automatic label apply for now."* It performs no work and
carries a `~/.h2t/venv` path that nothing else in `h2t-core` still depends on.

**Files:**
- Modify: `plugins/h2t-core/skills/scaffold-project/SKILL.md:25-27, 206-215`
- Test: `tests/core/test_skill_entrypoints.py` (extend)

**Interfaces:**
- Consumes: nothing new.

- [x] **Step 1: Write the failing test**

The test has to recognise both gate shapes, or it measures style instead of safety:

```python
import re

CLI_BACKED = {
    "h2t-core/skills/handoff": "h2t-handoff",
    "h2t-core/skills/session-start": "h2t-gather",
    "h2t-core/skills/init-project": "h2t-project-register",
    "h2t-core/skills/project-audit": "h2t-project-audit-scan",
    "h2t-core/skills/scaffold-project": "h2t-scaffold-project",
}


def _gated_commands(text: str) -> set[str]:
    """Commands the skill refuses to run without.

    Two shapes are in use: `command -v h2t-x` per line, and a `for _cmd in a b; do
    command -v "$_cmd"` loop. Both are gates; only the loop hides the name from a
    substring search.
    """
    gated = set()
    if "command -v" in text:
        gated |= set(re.findall(r"command -v ([\w.-]+)", text))
        for names in re.findall(r"for _cmd in ([^;\n]+); do", text):
            gated |= {n for n in names.split() if n.startswith("h2t-")}
    return gated


@pytest.mark.parametrize(("skill", "cli"), sorted(CLI_BACKED.items()))
def test_skill_gates_on_its_cli(skill, cli):
    text = (ROOT / "plugins" / skill / "SKILL.md").read_text(encoding="utf-8")
    gated = _gated_commands(text)
    assert gated, f"{skill}: no gate found at all — the parser is broken, not the skill"
    assert cli in gated, f"{skill} does not gate on {cli}; it gates on {sorted(gated)}"


def test_no_h2t_core_skill_hand_rolls_a_python_probe():
    """`$H2T_PYTHON` predates the entry points. A skill that still resolves an interpreter
    by hand has a second way to run its code, and the two can disagree."""
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "plugins" / "h2t-core" / "skills").glob("*/SKILL.md")
        if "H2T_PYTHON" in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"still hand-rolling an interpreter: {offenders}"
```

- [x] **Step 2: Run it and read which assertion fires**

Run: `.venv/bin/pytest tests/core/test_skill_entrypoints.py -q -k "gates_on_its_cli or python_probe"`
Expected: the five `gates_on_its_cli` cases PASS (the loop shape is recognised), and
`test_no_h2t_core_skill_hand_rolls_a_python_probe` FAILS naming `scaffold-project/SKILL.md`.
If a `gates_on_its_cli` case fails instead, the parser is wrong — fix the test, not the skill.

- [x] **Step 3: Delete the dead block**

Remove the three `H2T_PYTHON` lines at `SKILL.md:25-27`, and replace the self-cancelling label
snippet at `:206-215` with the instruction the prose underneath already gives:

```markdown
Labels are applied by a separate skill — canonical labels live in
`~/.h2t/config/labels.json` and are synced by `/h2t-dev:docs-sync-labels`:

"Запусти `/h2t-dev:docs-sync-labels` в новом репо для применения канонических labels."
```

Keep `CONFIG_ROOT` — `grep -n CONFIG_ROOT SKILL.md` before deciding, since other steps read it.

- [x] **Step 4: Run the tests**

Run: `.venv/bin/pytest tests/core/ -q`
Expected: green, including the two new tests.

- [x] **Step 5: Commit**

```bash
git add plugins/h2t-core/skills/scaffold-project/SKILL.md tests/core/test_skill_entrypoints.py
git commit -m "fix(scaffold-project): drop the dead H2T_PYTHON probe, pin the gate with a test"
```

---

### Task 7: `.claude/project-id` becomes the identity it was written to be

**Evidence:** `plugins/h2t-core/skills/init-project/scripts/apply_registration.py:141-148`
writes `.claude/project-id` and returns the next step *"Next /session-start will recognize this
project"*. No reader exists — `grep -rn "project-id" --include=*.py` finds only the writer and
its test. Identity therefore comes from `git remote` plus a central
`~/.h2t/config/repo-mapping.yaml`, so a clone on a machine without that mapping, or a renamed
repo, resolves to `unknown`.

**Files:**
- Modify: `lib/gather/project.py:31` — `identify_project`
- Modify: `plugins/h2t-core/lib/gather/project.py` — byte-identical copy
- Test: `lib/gather/test_project.py` (extend)

**Interfaces:**
- Produces: `identify_project(cwd)` returns `{"id", "domain", ...}` sourced from
  `<cwd>/.claude/project-id` when that file exists, before consulting the git remote

- [x] **Step 1: Write the failing test**

```python
def test_project_id_file_wins_over_the_remote(tmp_path, monkeypatch):
    """Identity travels with the checkout, so a clone needs no central mapping."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "project-id").write_text("personal-os/agent-skills\n")
    monkeypatch.setenv("H2T_CONFIG_ROOT", str(tmp_path / "empty-config"))
    result = identify_project(str(tmp_path))
    assert result["id"] == "agent-skills"
    assert result["domain"] == "personal-os"
```

- [x] **Step 2: Run it to confirm it fails**

Run: `.venv/bin/pytest lib/gather/test_project.py -q -k project_id_file`
Expected: FAIL — `result["id"]` is `unknown`.

- [x] **Step 3: Read the file first**

```python
# lib/gather/project.py, at the top of identify_project() after cwd_abs is computed
    pid_file = Path(cwd_abs) / ".claude" / "project-id"
    if pid_file.is_file():
        raw = pid_file.read_text(encoding="utf-8").strip()
        if raw:
            domain, project_id = _split_domain_project(raw) if "/" in raw else ("", raw)
            if not domain:
                domain = _domain_for_project(domains, project_id) or "dev"
            return {
                "id": project_id, "domain": domain,
                "label": _find_label(domains, domain, project_id),
                "type": "git" if (Path(cwd_abs) / ".git").exists() else "directory",
                "github": None, "config_root": str(config_root),
            }
```

Add `_domain_for_project(domains, project_id)` beside `_find_label`: it walks
`domains["domains"]` and returns the first domain whose `projects` contain that id, or `""`.

- [x] **Step 4: Make the writer emit `domain/project`**

`apply_registration.py:146` writes `project_id` alone, which forces the lookup above. Change it
to `f"{domain}/{project_id}\n"` and update
`plugins/h2t-core/skills/init-project/scripts/test_apply.py:139-161` — note that test asserts an
existing file is **not** overwritten, which must stay true.

- [x] **Step 5: Mirror to the vendored copy and run parity**

```bash
cp lib/gather/project.py plugins/h2t-core/lib/gather/project.py
```

Run: `.venv/bin/pytest tests/core/test_vendored_lib_parity.py lib/gather/ -q`
Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add lib/gather/project.py plugins/h2t-core/lib/gather/project.py \
        plugins/h2t-core/skills/init-project/scripts/apply_registration.py \
        plugins/h2t-core/skills/init-project/scripts/test_apply.py lib/gather/test_project.py
git commit -m "feat(gather): resolve identity from .claude/project-id before the git remote"
```

---

### Task 8: Typed exit codes for the h2t-core entry points

**Evidence — re-measured 2026-08-23, after Wave 1.** `h2t-ops nosuchconnector` exits `2`, the
reference. `h2t-gather --cwd /nonexistent` now exits `3` (Task 2 landed). The handoff writer
does not follow the taxonomy:

```
writer.py                                    -> 1, help printed to stdout   (should be 2)
writer.py write                              -> 2                          (argparse, correct)
writer.py write --markdown-dir /dev/null/deep -> 1 + NotADirectoryError traceback (should be 3)
```

The third case matters beyond its exit code. `log_session_end()` writes the spool *before* the
mirror, so the record was already on disk when `md_dir.mkdir` raised — the process died looking
like a total failure over a session that had in fact been saved. That is the invariant
`.claude/rules/gates.md` states, in its other form: not a gate before the write, but a crash
after it.

`--json` is not added. The writer already prints its result as JSON on every path, and gather
has `--briefing-only` / `--format-briefing`; adding a third output flag is scope this release
does not need.

**Files:**
- Modify: `plugins/h2t-core/skills/handoff/scripts/writer.py` — `main()`
- Modify: `plugins/h2t-core/skills/session-start/scripts/gather.py` — `main()`
- Test: `tests/core/test_entrypoint_exit_codes.py` (create)

**Interfaces:**
- Produces: `0` ok, `2` usage, `3` config, `5` not found — the subset of the connector taxonomy
  these commands can actually hit

- [x] **Step 1: Write the failing test**

```python
# tests/core/test_entrypoint_exit_codes.py
"""Exit codes are the only thing a hook can branch on; `1` for everything is no signal."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WRITER = ROOT / "plugins" / "h2t-core" / "skills" / "handoff" / "scripts" / "writer.py"

CASES = [
    (["write"], 2),                                        # missing --session-id
    (["write", "--session-id", "x", "--markdown-dir", "/proc/nope/deep"], 3),
]


@pytest.mark.parametrize(("argv", "expected"), CASES)
def test_writer_exit_codes(argv, expected):
    result = subprocess.run([sys.executable, str(WRITER), *argv],
                            capture_output=True, text=True, check=False)
    assert result.returncode == expected, (result.returncode, result.stderr[:200])
```

- [x] **Step 2: Run it to confirm the second case fails**

Run: `.venv/bin/pytest tests/core/test_entrypoint_exit_codes.py -q`
Expected: the usage case already passes (argparse exits 2); the unwritable-dir case FAILS with
`1`.

- [x] **Step 3: Map the failures**

Route every mirror failure through one `_degraded()` builder and exit `3` from `main()` when
`mirror_write_failed` is set, leaving `1` for genuinely unexpected errors. The contour must
cover the whole mirror, not just `mkdir`: `latest.json` is written by `_write_json_atomic`
before the markdown file, and a directory named `latest.json.tmp` raised `IsADirectoryError`
straight out of `main()` with the spool already written. Only the `markdown_path` backfill
after the `.md` lands stays non-fatal.

The pre-existing `status: "degraded"` path (mirror directory fine, file write refused) exited
`0`. It now exits `3` too — a caller branching on the exit code could not otherwise tell a
complete write from a partial one. Nothing in the repo depended on the old code.

- [x] **Step 4: Run and commit**

Run: `.venv/bin/pytest tests/core/ -q`

```bash
git add plugins/h2t-core/skills/handoff/scripts/writer.py tests/core/test_entrypoint_exit_codes.py
git commit -m "fix(cli): typed exit codes for the handoff writer"
```

---

### Task 9: The docs say what the code does

**Evidence:** `CLAUDE.md` states *"h2t-skills exposes 4 global entry points"* and names four.
`pyproject.toml` declares eight and `uv tool list` shows eight installed —
`h2t-project-audit-scan`, `h2t-project-audit-report`, `h2t-project-register` and
`h2t-scaffold-project` are undocumented. Every command block in `CLAUDE.md` and
`.claude/rules/linting.md` gives Windows paths (`C:/dev/h2t-skills/.venv/Scripts/...`) that do
not exist on the Mac this repo is currently developed on.

**Files:**
- Modify: `CLAUDE.md`
- Modify: `.claude/rules/linting.md`

- [x] **Step 1: Regenerate the entry-point list from the source of truth**

```bash
sed -n '/\[project.scripts\]/,/^\[/p' pyproject.toml
```

Paste the eight names into `CLAUDE.md`, each with one line saying what it does.

- [x] **Step 2: Give both machines' commands**

Replace each single-path command block with both forms, labelled — Windows
`C:/dev/h2t-skills/.venv/Scripts/pytest`, Mac `.venv/bin/pytest` — and note that `ruff` comes
from `uvx` on the Mac.

- [x] **Step 3: Verify each documented command actually runs**

Run every command block you touched, on this machine, and record the ones that fail. A
documented command that does not run is the defect this task exists to remove.

- [x] **Step 4: Commit**

```bash
git add CLAUDE.md .claude/rules/linting.md
git commit -m "docs: eight entry points, and commands that run on both machines"
```

---

### Task 10: Hooks written into other people's projects resolve at run time

**Evidence:** `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py:464` sets
`_HOOK_BASE = "~/.claude/plugins/cache/lichtpfad/h2t-core/latest"` and writes
`{_HOOK_BASE}/hooks-handlers/on-stop` and `.../post-git-commit-docs-lint` into the scaffolded
project's `.claude/settings.json`. Measured 2026-08-23:

- `latest -> 3.2.18` while the cache holds up to `3.2.22` and the repo is at `3.2.23`.
- The symlink **is** maintained by code — `setup_h2t.py:44` `create_latest_link`, called at
  `setup_h2t.py:631`. But that call sits inside the `install-h2t-ops` subcommand only. The
  normal way a plugin updates is `/plugin marketplace update`, which never runs it. So the
  symlink is refreshed by the wrong event and drifts silently; `3.2.18` is simply when
  `install-h2t-ops` last ran.
- `find ~ -name "settings*.json" | xargs grep -l "h2t-core/latest"` → **0 hits**, probe
  controlled by `grep -l "h2t-core" ~/.claude/settings.json` → 1 hit. Nothing has been wired to
  it yet: a latent defect, not a live one.

The plugin's own hooks are already correct — `plugins/h2t-core/hooks/hooks.json` uses
`${CLAUDE_PLUGIN_ROOT}`, expanded by the harness to the running version. A *project's*
`settings.json` has no such variable, which is why scaffold reaches for an absolute path. That
path does not exist under a Windows home directory, and `.claude/settings.json` is normally
committed, so it travels to every clone.

The resolver already exists: `plugin_entrypoints.candidate_roots()` walks `H2T_PLUGIN_ROOT` →
`CLAUDE_PLUGIN_ROOT` → editable checkout → `_cache_plugin_roots()` (ordered by `_version_key`)
→ bundled payload. This task exposes it as a hook launcher and then removes the symlink
machinery, because leaving a generator of a silently-wrong answer next to the correct one is
how this defect returns.

**Files:**
- Create: `h2t_ops/hook_entry.py`
- Create: `tests/core/test_hook_entry.py`
- Modify: `pyproject.toml` — one line under `[project.scripts]`
- Modify: `plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py:464-487`
- Modify: `tests/scaffold/test_scaffold_steps.py:187` — `test_install_hooks_stop_hook_points_to_latest`
- Modify: `plugins/h2t-core/skills/setup/scripts/setup_h2t.py:44-66, 625-632`
- Delete: `tests/scaffold/test_scaffold_latest.py`

**Interfaces:**
- Consumes: `plugin_entrypoints.plugin_script_path(relative_path) -> Path`
- Produces: console script `h2t-hook <handler-name> [args...]`, and
  `hook_entry.interpreter_for(path) -> list[str]`

- [x] **Step 1: Write the failing test**

```python
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _run(argv_tail, env_root, tmp_path):
    return subprocess.run(
        [sys.executable, "-c",
         "import sys; from h2t_ops.hook_entry import main; "
         f"sys.argv=['h2t-hook',{argv_tail}]; raise SystemExit(main())"],
        cwd=ROOT, capture_output=True, text=True,
        env={**dict(__import__("os").environ), "H2T_PLUGIN_ROOT": str(env_root)},
    )


def test_hook_entry_runs_the_handler_the_resolver_finds(tmp_path):
    handlers = tmp_path / "plugin" / "hooks-handlers"
    handlers.mkdir(parents=True)
    (handlers / "probe").write_text("#!/usr/bin/env bash\necho RAN-PROBE\n", encoding="utf-8")
    r = _run("'probe'", tmp_path / "plugin", tmp_path)
    assert r.returncode == 0, r.stderr
    assert "RAN-PROBE" in r.stdout


def test_a_python_handler_is_not_run_under_bash(tmp_path):
    """The two handlers scaffold writes are `#!/usr/bin/env python3`. Running them under
    bash is a syntax error, and bash is what hooks.json hardcodes for its own handlers."""
    handlers = tmp_path / "plugin" / "hooks-handlers"
    handlers.mkdir(parents=True)
    (handlers / "pyprobe").write_text(
        "#!/usr/bin/env python3\nprint('RAN-PY')\n", encoding="utf-8")
    r = _run("'pyprobe'", tmp_path / "plugin", tmp_path)
    assert r.returncode == 0, r.stderr
    assert "RAN-PY" in r.stdout


def test_the_handlers_exit_code_is_passed_through(tmp_path):
    handlers = tmp_path / "plugin" / "hooks-handlers"
    handlers.mkdir(parents=True)
    (handlers / "fails").write_text("#!/usr/bin/env bash\nexit 7\n", encoding="utf-8")
    assert _run("'fails'", tmp_path / "plugin", tmp_path).returncode == 7


def test_a_missing_handler_exits_5_and_names_what_it_tried(tmp_path):
    r = _run("'nope'", tmp_path, tmp_path)
    assert r.returncode == 5
    assert "hooks-handlers/nope" in r.stderr


def test_no_handler_name_is_a_usage_error(monkeypatch):
    from h2t_ops.hook_entry import main
    monkeypatch.setattr(sys, "argv", ["h2t-hook"])
    assert main() == 2


@pytest.mark.parametrize("shebang", ["#!/usr/bin/env bash\n", "#!/bin/sh\n"])
def test_a_shell_shebang_selects_that_shell(tmp_path, shebang):
    from h2t_ops.hook_entry import interpreter_for
    p = tmp_path / "h"
    p.write_text(shebang + "true\n", encoding="utf-8")
    assert Path(interpreter_for(p)[0]).name in {"bash", "sh", "bash.exe", "sh.exe"}


@pytest.mark.parametrize("shebang", ["#!/usr/bin/env python3\n", "#!/usr/bin/python\n"])
def test_a_python_shebang_never_resolves_to_a_missing_name(tmp_path, shebang):
    """On Windows there is often no `python3` on PATH, only `python.exe`. Falling back to
    the literal name would leave the hook broken on exactly the machine class this task
    exists for, so a python shebang resolves to the running interpreter instead."""
    from h2t_ops.hook_entry import interpreter_for
    p = tmp_path / "h"
    p.write_text(shebang + "pass\n", encoding="utf-8")
    resolved = interpreter_for(p)[0]
    assert Path(resolved).is_file(), f"{resolved} is not an executable file"
```

- [x] **Step 2: Run it and read the failure text**

Run: `.venv/bin/pytest tests/core/test_hook_entry.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'h2t_ops.hook_entry'`. Read the text. A
different failure means the test is broken, not the code.

- [x] **Step 3: Write the launcher**

```python
"""Run a plugin hook handler resolved through the same ladder every entry point uses.

A hook written into a *project's* `.claude/settings.json` cannot use
`${CLAUDE_PLUGIN_ROOT}` — the harness defines that only for the plugin's own hooks.json.
An absolute cache path pins the project to one plugin version and to one machine's home
directory, and `.claude/settings.json` is normally committed. This launcher resolves at
fire time instead.
"""
import shutil
import subprocess
import sys
from pathlib import Path

from h2t_ops.plugin_entrypoints import plugin_script_path

_DEFAULT_INTERPRETER = ["bash"]
_PYTHON_NAMES = {"python", "python3", "python.exe", "python3.exe"}


def interpreter_for(path: Path) -> list[str]:
    """The shebang decides.

    hooks.json hardcodes `bash` for the handlers it declares, but the two handlers
    scaffold-project writes are python3 — running those under bash is a syntax error.
    A python shebang resolves to `sys.executable` when PATH has no matching name, which
    is the normal case on Windows (`python.exe`, no `python3.exe`).
    """
    try:
        first = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except (OSError, IndexError):
        return list(_DEFAULT_INTERPRETER)
    if not first.startswith("#!"):
        return list(_DEFAULT_INTERPRETER)
    parts = first[2:].strip().split()
    if not parts:
        return list(_DEFAULT_INTERPRETER)
    if Path(parts[0]).name == "env" and len(parts) > 1:
        parts = parts[1:]
    name = Path(parts[0]).name
    resolved = shutil.which(parts[0]) or shutil.which(name)
    if resolved is None and name in _PYTHON_NAMES:
        resolved = sys.executable
    return [resolved or parts[0], *parts[1:]]


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1]:
        print("usage: h2t-hook <handler-name> [args...]", file=sys.stderr)
        return 2
    relative = f"hooks-handlers/{sys.argv[1]}"
    try:
        path = plugin_script_path(relative)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 5
    return subprocess.run([*interpreter_for(path), str(path), *sys.argv[2:]]).returncode
```

Add to `pyproject.toml` under `[project.scripts]`:

```toml
h2t-hook = "h2t_ops.hook_entry:main"
```

- [x] **Step 4: Run the tests, then reinstall so the entry point exists**

Run: `.venv/bin/pytest tests/core/test_hook_entry.py -q`
Expected: 9 PASS.

Run: `uv tool install --editable .`, then `command -v h2t-hook`
Expected: a path is printed, and `uv tool list` shows nine entry points. Judge the state, not
the install command's output.

- [x] **Step 5: Point scaffold at the launcher**

In `scaffold_project.py`, delete `_HOOK_BASE` and rewrite `_HOOK_ENTRIES`:

```python
_HOOK_ENTRIES = {
    "Stop": [
        {
            "matcher": "",
            "hooks": [{"type": "command", "command": "h2t-hook on-stop"}],
        }
    ],
    "PostToolUse": [
        {
            "matcher": "Bash(git commit*)",
            "hooks": [
                {"type": "command", "command": "h2t-hook post-git-commit-docs-lint"}
            ],
        }
    ],
}
```

- [x] **Step 6: Replace the test that pins the old behaviour**

`tests/scaffold/test_scaffold_steps.py:187` currently reads:

```python
def test_install_hooks_stop_hook_points_to_latest(tmp_path):
    """Stop hook path starts with ~ (portable) and references latest/ junction."""
```

That test asserts the defect. Replace it with:

```python
def test_install_hooks_write_no_machine_specific_path(tmp_path):
    """A project's settings.json travels to other clones and other operating systems.

    An absolute cache path under one home directory, or a `latest` junction refreshed only
    by `install-h2t-ops`, is wrong on arrival. The command must resolve when it fires.
    """
    install_hooks(tmp_path)
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    hooks = data.get("hooks", {})
    commands = _hook_commands(hooks.get("Stop", [])) + _hook_commands(
        hooks.get("PostToolUse", [])
    )
    assert len(commands) == 2, f"expected both hook commands, read {commands}"
    for command in commands:
        assert command.startswith("h2t-hook "), command
        assert "plugins/cache" not in command, command
        assert "latest" not in command, command
        assert not command.startswith("~"), command
```

`_hook_commands` (`tests/scaffold/test_scaffold_steps.py:162`) takes the *entries* list for one
event and returns the command strings inside it, so both events are read separately and
concatenated. The `len(commands) == 2` assertion is the control: an empty list would satisfy
every `for` assertion below it and the test would pass while measuring nothing.

Run: `.venv/bin/pytest tests/scaffold/ tests/core/ -q`
Expected: all PASS.

- [x] **Step 7: End-to-end — fire a real handler through the launcher**

```bash
echo '{}' | h2t-hook post-git-commit-docs-lint; echo "exit=$?"
```

Expected: the handler itself runs — not `ModuleNotFoundError`, not a bash syntax error from a
python file. Its own exit code, whatever it is, is the pass condition. This is the round-trip
`.claude/rules/verification.md` asks for: launcher and handler are two sides of one contract,
and each side's tests stay green while the sides disagree.

- [x] **Step 8: Remove the machinery that produced the stale symlink**

Nothing reads `latest` once Step 5 lands (`grep -rn "h2t-core/latest" --include=*.py` should
return only comments). Delete `create_latest_link` (`setup_h2t.py:44-66`) and its call site
(`setup_h2t.py:625-632`), keeping the `plugin-versions.json` write beside it — that record
names a concrete version and is honest. Delete `tests/scaffold/test_scaffold_latest.py`.
`_semver_key` stays: the version sort still uses it.

Then remove the artifact itself:

```bash
find ~/.claude/plugins/cache -maxdepth 3 -name latest -path "*h2t-core*" -print -delete
grep -rn "create_latest_link" --include=*.py . ; echo "grep-exit=$?  (1 = fully removed)"
```

`find -delete` rather than `rm`: the marketplace namespace is not guaranteed to be
`lichtpfad` on another install, and a bare `rm` on an already-absent path fails the step for
the wrong reason. `-print` makes the removal visible — a silent `find` that matched nothing
looks the same as one that cleaned up.

- [x] **Step 9: Full suite and commit**

Run: `.venv/bin/pytest tests/ lib/ -q`
Expected: green.

```bash
git add h2t_ops/hook_entry.py tests/core/test_hook_entry.py pyproject.toml \
        plugins/h2t-core/skills/scaffold-project/scripts/scaffold_project.py \
        plugins/h2t-core/skills/setup/scripts/setup_h2t.py \
        tests/scaffold/test_scaffold_steps.py
git rm tests/scaffold/test_scaffold_latest.py
git commit -m "fix(scaffold-project): resolve hook handlers at fire time, not at scaffold time"
```

---

### Task 11: Land PR #339 (kb lint semantic health + ingest domain gate)

**Evidence (re-measured 2026-08-23 — the earlier note in this plan was wrong on two counts):**
the PR was opened 2026-08-13, not in May, and the conflict is textual, not semantic.
`git merge-base main origin/feat/kb-lint-semantic-health` = `b4f878b`. Since then `main` added
a `skip_reasons` / `--reingest` block to `ingest.md` (+24) and edited `query.md` (+22/-5) —
both about resuming a partial intake run. The branch's additions are about which domain a page
is written to, and about lint. Neither side overwrote the other:

- `plugins/h2t-ops/skills/kb/references/lint.md` on `main` is **12 lines**, with no match for
  `provenance`, `WARN`, or `semantic health`. The branch adds all three.
- The `classify → propose → confirm` domain gate is absent from `main`'s `ingest.md`. The one
  `grep` hit, "Agent-propose gate", is about surfacing a dev decision — a different thing.

**Gate review.** `ingest.md`'s "ALWAYS propose + confirm before writing" is the exact shape
`.claude/rules/gates.md` exists to catch. It passes: ingest *creates* a KB page — a new outward
mutation — and if the operator never answers, nothing is lost, because the material stays in
`records.json`. Handoff was the other shape, where the record *was* the work. Do not weaken
this gate while resolving conflicts.

**Files:**
- Modify (conflict resolution only): `plugins/h2t-ops/skills/kb/references/ingest.md`,
  `query.md`, `SKILL.md`, `plugins/h2t-ops/.claude-plugin/plugin.json`

- [x] **Step 1: Rebase onto main**

```bash
git fetch origin
git checkout -B feat/kb-lint-semantic-health origin/feat/kb-lint-semantic-health
git rebase origin/main
```

- [x] **Step 2: Resolve, keeping both sides, then continue the rebase**

`ingest.md` — `main`'s `skip_reasons` / `--reingest` block AND the branch's domain-resolution
gate both stay; they sit in different sections. For `plugin.json`, take `main`'s version
verbatim during the resolution; the bump happens in Step 3 through the script. Resolving a
version by hand is how two plugins end up claiming the same number.

```bash
git status --short          # read which files are actually conflicted first
git add plugins/h2t-ops/skills/kb/references/ingest.md \
        plugins/h2t-ops/skills/kb/references/query.md \
        plugins/h2t-ops/skills/kb/SKILL.md \
        plugins/h2t-ops/.claude-plugin/plugin.json
git rebase --continue
```

Stage only the paths `git status --short` reported as conflicted — `git add` on an unconflicted
path is harmless, but a conflicted path left unstaged makes `--continue` refuse, and the error
is easy to misread as the rebase having finished.

- [x] **Step 3: Bump the plugin version once, through the script**

```bash
CURRENT=$(python3 -c "import json;print(json.load(open('plugins/h2t-ops/.claude-plugin/plugin.json'))['version'])")
NEXT=$(python3 -c "import sys;a,b,c=sys.argv[1].split('.');print(f'{a}.{b}.{int(c)+1}')" "$CURRENT")
python scripts/bump_plugin.py h2t-ops "$NEXT"
```

`bump_plugin.py` takes two literal arguments (`scripts/bump_plugin.py:42-46`). Writing
`<next>` in a shell line is an input redirection, not a placeholder — it fails before the
script sees anything.

- [x] **Step 4: Verify no content was lost in the resolution**

```bash
grep -c -i "semantic health" plugins/h2t-ops/skills/kb/references/lint.md
grep -c "classify → propose →" plugins/h2t-ops/skills/kb/references/ingest.md
grep -c "reingest" plugins/h2t-ops/skills/kb/references/ingest.md
```

Expected: all three ≥ 1. The `reingest` count is the control — it proves `main`'s work survived
the rebase, which a "keep ours" resolution would silently drop while the other two still pass.

- [x] **Step 5: Tests and docs lint**

Run: `.venv/bin/pytest tests/ -q`, then
`.venv/bin/python plugins/h2t-dev/skills/docs-lint/scripts/lint.py doctor`
Expected: green. There is no `docs-lint` binary and `uv run docs-lint` fails to spawn — it is a
plugin skill script (`.claude/rules/linting.md`).

- [x] **Step 6: Push and merge**

```bash
git push --force-with-lease origin feat/kb-lint-semantic-health
gh pr merge 339 --squash --delete-branch
```

---

### Task 12: One copy of each module in the wheel

**Evidence:** `pyproject.toml` declares `packages = ["h2t_ops", "lib"]` *and* force-includes
`plugins/h2t-core/lib` at `h2t_ops/_plugin_payload/lib`. The wheel therefore ships
`eval/session.py`, `eval/skill_class.py` and `activity/writer.py` twice, and claims the
top-level name `lib` in `site-packages` — about as generic a name as exists. Measured
consumers of the top-level `lib` inside shipped code:

```
h2t_ops/connectors/evals/commands.py:10  from lib.eval.status import get_status
h2t_ops/connectors/evals/commands.py:39  from lib.eval.report import ...
h2t_ops/cli.py:49                        from lib.cli.main import main   # the Wave 1 stub
```

`lib/practice_harvest` has no consumer outside `tests/` and one plan document.

**The two copies are not interchangeable, and this decides the design.** The vendored copy is
imported as a *top-level* package — `plugins/h2t-core/skills/handoff/scripts/writer.py:35` and
`gather.py:43` both say `from eval.session import SkillEval`, after inserting
`PLUGIN_ROOT/lib` into `sys.path` (`gather.py:27-32`). Inside itself it uses relative imports
(`eval/session.py:25`: `from .skill_class import eval_set_for`). The root copy is imported
through the `lib` package: `lib/eval/status.py:6` is `import lib.eval.session as sess`.

So `load_plugin_module("lib/eval/status.py")` would **not** work: it executes a file by path
without putting any root on `sys.path`, and `status.py`'s own `import lib.eval.session` would
fail in a venv where `lib` is gone. The fix is to make the vendored copy complete and reach it
the way every other payload module is already reached.

**Honest limit on this evidence:** the tool is installed editable (`_editable_impl_h2t_ops.pth`
is in `site-packages`), so a real name collision has never been observed here. Step 1 measures
the current wheel before anything changes.

**Files:**
- Modify: `h2t_ops/plugin_entrypoints.py` — add `ensure_plugin_lib_on_path`
- Move: `lib/eval/status.py`, `lib/eval/report.py` → also into `plugins/h2t-core/lib/eval/`
- Modify: `h2t_ops/connectors/evals/commands.py:10,39`
- Modify: `h2t_ops/cli.py:49`
- Modify: `pyproject.toml` — `packages`
- Modify: `tests/core/test_wheel_payload.py:58` — `test_wheel_still_ships_the_package_and_its_data`

**Interfaces:**
- Produces: `plugin_entrypoints.ensure_plugin_lib_on_path(*, requires="eval/status.py") -> Path`
  — resolves the `lib` that actually contains `requires`, inserts it at `sys.path[0]` if absent,
  returns the directory. Raises `FileNotFoundError` with the same "tried:" listing
  `plugin_script_path` produces.

- [x] **Step 1: Measure the wheel as it is now**

```bash
rm -rf /tmp/wheel-before
.venv/bin/python -m pip wheel --no-deps -w /tmp/wheel-before .
.venv/bin/python -c "
import zipfile, glob, collections
names = zipfile.ZipFile(glob.glob('/tmp/wheel-before/h2t_ops-*.whl')[0]).namelist()
print('top-level:', sorted({n.split('/')[0] for n in names if '/' in n}))
print('eval/session.py copies:', [n for n in names if n.endswith('eval/session.py')])
"
```

Expected: `lib` appears in the top-level list, and `eval/session.py` appears **twice**. Record
both in the PR — this is the before-measurement the change is judged against. `session.py` is
the probe, not `status.py`: `plugins/h2t-core/lib/eval/` holds only `session.py` and
`skill_class.py`, so a `status.py` probe would report one copy today and the test would be
vacuous.

- [x] **Step 2: Write the failing tests**

```python
def test_the_wheel_claims_no_generic_top_level_name(wheel_names):
    tops = {n.split("/")[0] for n in wheel_names if "/" in n}
    assert tops, "no entries read from the wheel — the fixture is broken, not the wheel"
    assert "lib" not in tops, f"wheel claims the top-level name 'lib': {sorted(tops)}"


def test_each_payload_module_ships_once(wheel_names):
    for name in ("eval/session.py", "eval/skill_class.py", "activity/writer.py"):
        copies = [n for n in wheel_names if n.endswith(name)]
        assert len(copies) == 1, f"{name} ships {len(copies)} times: {copies}"


def test_the_payload_lib_is_complete(wheel_names):
    """The evals connector reaches status/report through the payload now, so a payload
    missing them is the packaging defect this task exists to prevent recurring."""
    assert f"{PAYLOAD}/lib/eval/status.py" in wheel_names
    assert f"{PAYLOAD}/lib/eval/report.py" in wheel_names
```

- [x] **Step 3: Run them — all three must fail**

Run: `.venv/bin/pytest tests/core/test_wheel_payload.py -q`
Expected: the three new tests FAIL, the four existing ones PASS. Read each failure message: a
`wheel build failed` fixture error is not the same result as an assertion firing.

- [x] **Step 4: Complete the vendored copy**

```bash
cp lib/eval/status.py lib/eval/report.py plugins/h2t-core/lib/eval/
```

In **both** copies, change the one absolute import to a relative one so the module works under
either import style:

```python
# lib/eval/status.py:6 and plugins/h2t-core/lib/eval/status.py
from . import session as sess
```

Apply the same to `report.py` if it carries a `lib.eval.*` import — check with
`grep -n "^import\|^from" lib/eval/report.py` first; do not assume it has one.

`tests/core/test_vendored_lib_parity.py` requires the two copies to be byte-identical, so this
is not optional duplication — it is the invariant that test polices. Relative imports keep
`from lib.eval.status import get_status` working for `tests/` (a relative import inside the
`lib.eval` package resolves normally) and make `from eval.status import get_status` work when
`<root>/lib` is on `sys.path`.

- [x] **Step 5: Add the path helper**

```python
def ensure_plugin_lib_on_path(*, requires: str = "eval/status.py") -> Path:
    """Put the resolved plugin's `lib` on sys.path, the way the plugin scripts do.

    `gather.py:27-32` and `writer.py` already do this by hand from `__file__`. Code inside
    the installed package has no `__file__` near a plugin root, so it resolves through the
    same ladder every other entry point uses.

    Resolution is by the module the caller needs, not by the presence of a `lib` directory.
    The ladder prefers an installed plugin cache over the bundled payload, and every cache
    entry predating this change has a `lib/eval` without `status.py` — picking it by
    directory alone would insert an incomplete lib and never reach the complete one.
    """
    lib = plugin_script_path(f"lib/{requires}").parent.parent
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))
    return lib
```

`plugin_script_path` already walks every rung and raises `FileNotFoundError` with the full
"tried:" listing, so the failure mode stays identical to the rest of the module. Add
`import sys` at the top of `plugin_entrypoints.py` — it currently imports only
`importlib.util`, `os`, `Path` and `ModuleType`.

- [x] **Step 6: Route the evals connector through it**

In `h2t_ops/connectors/evals/commands.py`, replace both `from lib.eval...` imports:

```python
from h2t_ops.plugin_entrypoints import ensure_plugin_lib_on_path

ensure_plugin_lib_on_path(requires="eval/status.py")
from eval.status import get_status          # noqa: E402 - path set on the line above
```

The second import at `:39` is inside a function; keep it there and give it the same treatment,
naming its own module:

```python
ensure_plugin_lib_on_path(requires="eval/report.py")
from eval.report import (build_report, catalog_skills, load_sessions,
                         render_human, render_md)
```

Copy the name list from the existing import at `commands.py:39-40` rather than retyping it.
`_cmd_report` calls `render_md` at `:65` and `render_human` at `:66`; dropping either from the
list turns `h2t-ops evals report` into a `NameError` that no unit test covers.

Read the surrounding code before editing: the function-level import exists to keep the CLI's
startup cheap, and hoisting it to module scope would undo that. Passing the module each caller
needs is what makes a cache entry with an older, incomplete `lib/eval` fall through to the
bundled payload instead of being selected and failing.

- [x] **Step 7: Make the legacy fallthrough survive `lib` leaving the wheel**

`h2t_ops/cli.py:49` is a bare `from lib.cli.main import main as legacy_main` with no guard —
with `lib` gone from the wheel, an unknown subcommand would crash with `ModuleNotFoundError`
instead of returning the documented usage code:

```python
def _legacy(argv: list[str]) -> int:
    try:
        from lib.cli.main import main as legacy_main  # legacy keeps its own sys.path hack
    except ImportError:
        # Wave 1 emptied lib/cli; outside a checkout it is not shipped at all. The
        # contract for an unrecognised command is exit 2, not a traceback.
        print(f"error: unknown command: {argv[0] if argv else ''}", file=sys.stderr)
        return 2
```

Add a test for it in `tests/core/test_gather_single_implementation.py`, beside the existing
`test_missing_skill_still_exits_2`:

```python
def test_an_unknown_command_exits_2_without_lib(monkeypatch):
    import h2t_ops.cli as cli
    monkeypatch.setitem(sys.modules, "lib.cli.main", None)  # forces ImportError
    assert cli._legacy(["no-such-connector"]) == 2
```

- [x] **Step 8: Drop `lib` from the wheel**

```toml
[tool.hatch.build.targets.wheel]
packages = ["h2t_ops"]
```

The force-include block is unchanged: `plugins/h2t-core/lib` already maps to
`h2t_ops/_plugin_payload/lib`, and it is now the only copy.

Update `tests/core/test_wheel_payload.py:58`, which asserts `"lib/cli/main.py" in wheel_names`
— that is now false by design. Replace that line with an assertion that the payload carries the
lib instead:

```python
def test_wheel_still_ships_the_package_and_its_data(wheel_names):
    assert "h2t_ops/cli.py" in wheel_names
    assert f"{PAYLOAD}/lib/eval/session.py" in wheel_names
```

- [x] **Step 9: Re-measure, and prove the CLI works from a real wheel**

```bash
rm -rf /tmp/wheel-after /tmp/venv-probe
.venv/bin/python -m pip wheel --no-deps -w /tmp/wheel-after .
python3 -m venv /tmp/venv-probe
/tmp/venv-probe/bin/pip install -q /tmp/wheel-after/h2t_ops-*.whl
ls /tmp/venv-probe/lib/python*/site-packages/ | grep -x lib; echo "grep-exit=$?  (1 = 'lib' gone)"
/tmp/venv-probe/bin/h2t-ops evals status > /tmp/evals.out 2>&1; echo "evals-exit=$?"
grep -c "ModuleNotFoundError" /tmp/evals.out; echo "(0 = no import failure)"
cat /tmp/evals.out | head -20
```

Expected: `grep-exit=1`, `evals-exit=0`, and zero `ModuleNotFoundError`. The exit code alone is
not enough — `_run_connector()` catches exceptions and returns an error envelope, so an import
failure can surface as an ordinary non-zero result rather than a traceback. Read the output.

Installing into a throwaway venv is the point: the editable install in `.venv` resolves
everything from the checkout and cannot show a packaging defect at all.

- [x] **Step 10: Full suite and commit**

Run: `.venv/bin/pytest tests/ lib/ -q`
Expected: green. `tests/` still imports `lib.*` directly and must keep passing — `pythonpath =
["."]` serves those from the checkout, which is unaffected by what the wheel ships.

```bash
git add pyproject.toml h2t_ops/plugin_entrypoints.py h2t_ops/cli.py \
        h2t_ops/connectors/evals/commands.py lib/eval/status.py lib/eval/report.py \
        plugins/h2t-core/lib/eval/status.py plugins/h2t-core/lib/eval/report.py \
        tests/core/test_wheel_payload.py tests/core/test_gather_single_implementation.py
git commit -m "fix(packaging): ship one copy of each module and stop claiming the name 'lib'"
```

---

## Release checklist

- [x] PR #391 merged (handoff gate + cwd-derived identity)
- [x] Wave 1 merged (#397), `pytest tests/ lib/` green, ten of twelve plugin dirs green in CI
- [x] `uv tool install --editable .` — `uv tool list` shows nine entry points under one
      package, `h2t-hook` among them
- [x] `scripts/bump_plugin.py` — h2t-core 3.2.23 → 3.2.24 (8eedb4d), h2t-ops 1.6.4 → 1.6.5
      (f80a444, for Task 11)
- [x] `git push origin main`
- [x] `/plugin marketplace update lichtpfad`, then `/reload-plugins`
- [x] Deploy verified by reading the cache, not the command output
- [x] Fresh-session smoke: briefing rendered with `### Previous Session`

**A second deploy is due, and it is not this plan's.** #401 (pinned ruff set, CI lint gate,
drawio tests) and #402 (#400's sweep) landed *after* 3.2.24 shipped and touched six plugin
directories. Both are lint-only — renames and dead-import removal, behaviour identical — so
nothing is broken, but the cache no longer matches the version it claims: as of 2026-08-24
`plugins/h2t-core/lib/gather/briefing.py` differs from its copy in
`~/.claude/plugins/cache/lichtpfad/h2t-core/3.2.24/`. Bump and redeploy before the release.

## Out of scope, and why

Nine skills across `h2t-dev`, `h2t-edu`, `h2t-arch` and `h2t-creative` still invoke their
scripts directly (`$H2T_PYTHON ${CLAUDE_PLUGIN_ROOT}/skills/.../x.py`): `docs-lint`,
`docs-sync-labels`, `milestone-closure`, `youtube-transcript`, `convert-meeting-transcript`,
`process-transcripts`, `deck`, `landing`, `drawio`. That is not the defect this plan fixes —
none of them has a declared entry point, so there is no second path to disagree with. They
become worth migrating only if their scripts ever ship in the wheel. `plugins/h2t/` is a
rollback archive and is not shipped (`tests/core/test_skill_frontmatter.py`).

## Decisions taken (2026-08-23)

All three open questions were answered by the operator after the facts below were measured.
Two of the three descriptions this section previously carried were wrong; the corrections are
recorded with each decision so the reasoning can be re-checked rather than re-trusted.

1. **The `latest` symlink → remove it *and* the code that produces it.** Two of my own claims
   here were wrong and are corrected in Task 10's evidence. The earlier note said "our code
   reads versioned paths, so nothing is broken today" — but `scaffold_project.py:464` *writes*
   that path into other projects' `.claude/settings.json`. I then said the symlink was made by
   hand, having grepped only `update-plugin.sh`; it is created by `setup_h2t.py:44`, called at
   `:631` — inside the `install-h2t-ops` subcommand alone, never by `/plugin marketplace
   update`. That is the actual defect: refreshed by the wrong event, so it drifts silently.
   Deleting only the symlink would leave the generator, and the next `install-h2t-ops` would
   recreate the same wrong answer. Hooks move to run-time resolution through a new `h2t-hook`
   launcher — the option that survives a change of machine, and the one that matches the
   single-ladder principle Wave 1 established. → **Task 10**.
2. **PR #339 → rebase and land.** The earlier note claimed it was "open since May with a
   semantic conflict — main rewrote kb/query.md". Both halves were wrong: opened 2026-08-13,
   and the two sides edit different sections of the same files. Every line of its content is
   still unique on `main`. → **Task 11**.
3. **`lib` in the wheel → ship one copy, drop the top-level name.** Not "drop `lib`": the
   evals connector genuinely imports `lib.eval`. The vendored copy under `_plugin_payload` is
   completed with `status.py`/`report.py` and reached the way every other payload module
   already is, so the wheel stops carrying `eval`/`activity` twice and stops claiming a name as
   generic as `lib` in `site-packages`. The first draft of this task routed the connector
   through `load_plugin_module`, which would have failed: it executes a file by path without
   putting a root on `sys.path`, and the two copies are imported by different styles
   (`lib.eval.session` vs a top-level `from eval.session import`). → **Task 12**.

## Still open

Nothing from this plan. Both items this section carried are closed:

- **#396** — the drawio directory's 578 lines of module-level asserts became 16 pytest
  functions; export moved under a `skipif` guarded by a control test that fails if the CLI path
  it probes drifts. Closed in #401.
- **#381** — all twelve plugin test directories now run in CI. Closed in #401.

Two things found while closing them, tracked outside this plan:

- **#400** (closed in #402) — the five ruff classes deferred when the set was pinned. Cleared:
  117 cosmetic findings to zero and `ignore` removed entirely, F401 markers 101 → 6.
- **#399** (open) — `per-file-ignores` still silences `F821` in `telegram_cli.py`, and that one
  is a real `NameError`: `_create_notion_tasks` reads an undefined `REPO_ROOT` and has no
  caller. Deleting it belongs with #383, which asks where that script's workflows live at all.
