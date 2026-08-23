---
title: "Skills release hardening"
status: "draft"
date: "2026-08-23"
milestone: ""
---

# Skills Release Hardening Implementation Plan

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
- `pytest tests/` on clean `main` ends with 1 failure + 4 errors from a missing `ruamel`
  module. That is pre-existing; Task 4 removes it. Do not attribute it to your change.
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
- Modify: `lib/cli/main.py` — delete the `gather` subcommand and `_run_gather`
- Test: `tests/core/test_gather_single_implementation.py` (create)

**Interfaces:**
- Consumes: `h2t_ops.plugin_entrypoints.run_plugin_main(relative_path: str) -> int`
- Produces: nothing new; `h2t-ops gather <skill> [--cwd] [--briefing-only]` keeps its argv shape

- [ ] **Step 1: Write the failing test**

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
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `.venv/bin/pytest tests/core/test_gather_single_implementation.py -q`
Expected: FAIL — the two stdouts differ, `h2t-ops` output missing `### Previous Session`.
Read the diff before continuing; if it fails for another reason (module not runnable with
`-m`), fix the invocation, not the assertion.

- [ ] **Step 3: Route `gather` through the resolver**

```python
# h2t_ops/cli.py — replace lines 186-187
    if argv and argv[0] == "gather":
        from h2t_ops.plugin_entrypoints import run_plugin_main
        # argv is ["gather", "<skill>", ...]; the plugin script takes no skill positional.
        sys.argv = ["h2t-gather", *argv[2:]]
        return run_plugin_main("skills/session-start/scripts/gather.py")
```

- [ ] **Step 4: Delete the second implementation**

Remove `_run_gather` and the `gather` subparser from `lib/cli/main.py`. Leave the module's
docstring stating that gather now lives in the plugin script and this module keeps only what
`h2t_ops/cli.py:_legacy` still needs. If nothing remains, delete `lib/cli/` and drop `lib`
from `packages` in `pyproject.toml:37` — check `grep -rn "from lib\." h2t_ops/` first.

- [ ] **Step 5: Run the test and the suites it can break**

Run: `.venv/bin/pytest tests/core/ tests/lifecycle/ lib/ -q`
Expected: the new test passes; `test_gather_on_skill_hook.py` and
`test_gather_on_prompt_hook.py` stay green.

- [ ] **Step 6: Commit**

```bash
git add h2t_ops/cli.py lib/cli/main.py tests/core/test_gather_single_implementation.py
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

- [ ] **Step 1: Write the failing test**

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

- [ ] **Step 2: Run it to confirm the first test fails and the control passes**

Run: `.venv/bin/pytest tests/core/test_gather_rejects_bad_cwd.py -q`
Expected: `test_nonexistent_cwd_exits_config_error` FAILS with `(0, 'BRIEFING:...')`;
`test_real_cwd_still_succeeds` PASSES. A run where both fail means the probe is wrong.

- [ ] **Step 3: Validate in `main()`**

```python
# plugins/h2t-core/skills/session-start/scripts/gather.py, first lines of main() after parse_args
    cwd = Path(args.cwd).expanduser()
    if not cwd.is_dir():
        print(f"gather: --cwd is not a directory: {args.cwd}", file=sys.stderr)
        sys.exit(3)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/core/test_gather_rejects_bad_cwd.py tests/core/ -q`
Expected: PASS, and no regression in the hook tests, which pass a real cwd.

- [ ] **Step 5: Commit**

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

- [ ] **Step 1: Write the failing test**

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

- [ ] **Step 2: Run it to confirm it fails**

Run: `.venv/bin/pytest tests/core/test_gather_on_skill_hook.py -q -k prefers`
Expected: FAIL — the marker file is absent because the hook ran the script.

- [ ] **Step 3: Prefer the CLI, keep the script as fallback**

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

`run_cli` is `run_script` without the interpreter prefix — add it beside `run_script` in the
same file, reusing its stdout/stderr capture so `SCRIPT_STDERR` keeps working.

- [ ] **Step 4: Run the hook tests**

Run: `.venv/bin/pytest tests/core/test_gather_on_skill_hook.py tests/core/test_gather_on_prompt_hook.py -q`
Expected: PASS, including the existing cases that assert the fallback still works with an
empty PATH.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-core/hooks-handlers/gather-on-skill tests/core/test_gather_on_skill_hook.py
git commit -m "fix(hooks): gather through h2t-gather so hook and skill resolve one root"
```

---

### Task 4: Every plugin test directory runs in CI (#381)

**Evidence:** `.github/workflows/*.yml` runs `lib/`, `tests/`, and exactly two plugin script
directories (`autonomous-run`, `init-project`). Ten directories holding roughly 26 test files
never run — the largest is `plugins/h2t-creative/tests` with 14 files, and the 25 meetgeek
tests merged in #389/#390 are among them. Separately, `tests/core/test_skill_entrypoints.py::
test_payload_script_dependencies_are_installed` fails on clean `main` with
`ModuleNotFoundError: No module named 'ruamel'`.

**Files:**
- Modify: `.github/workflows/` — the workflow that runs pytest
- Modify: `pyproject.toml` — add the missing dependency
- Test: the CI run itself; plus `tests/core/test_ci_covers_plugin_tests.py` (create)

**Interfaces:**
- Produces: a test that fails when a new plugin test directory is added without a CI step

- [ ] **Step 1: Write the failing test**

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

- [ ] **Step 2: Run it to confirm it fails and read the list**

Run: `.venv/bin/pytest tests/core/test_ci_covers_plugin_tests.py -q`
Expected: FAIL listing ten directories. Copy that list — it is the input to Step 3.

- [ ] **Step 3: Add one pytest step per directory**

Append to the workflow, after the existing `plugins/h2t-core/skills/init-project/scripts` step,
one step per directory the test listed, in the same form:

```yaml
      - name: Plugin tests — h2t-creative
        run: python -m pytest plugins/h2t-creative/tests -q
```

Do not collapse them into one `pytest plugins/` invocation: these directories have no shared
conftest and several add their own `sys.path` entries, so a single run cross-contaminates them.

- [ ] **Step 4: Fix the pre-existing dependency failure**

Add `ruamel.yaml` to the dev dependency group in `pyproject.toml` — it is what
`test_payload_script_dependencies_are_installed` asserts is installed. Then:

Run: `.venv/bin/pip install -e .` followed by
`.venv/bin/pytest tests/core/test_skill_entrypoints.py tests/core/test_wheel_payload.py -q`
Expected: PASS — the 1 failure and 4 errors quoted in the Global Constraints disappear.

- [ ] **Step 5: Run everything**

Run: `.venv/bin/pytest tests/ lib/ -q`
Expected: 0 failures, 0 errors. Then run each newly added plugin directory locally and record
which ones are red — a directory that was never in CI may have been red for months. Fix or
`xfail` with a reason and an issue number; do not delete tests to make CI green.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows pyproject.toml tests/core/test_ci_covers_plugin_tests.py
git commit -m "test(ci): run every plugin test directory, add the missing ruamel dep (#381)"
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

- [ ] **Step 1: Write the rule**

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

- [ ] **Step 2: Extend the test to every skill that writes**

```python
WRITERS = {
    "h2t-core/skills/handoff": "h2t-handoff write",
    "h2t-core/skills/init-project": "h2t-project-register",
}

@pytest.mark.parametrize(("skill", "write_call"), sorted(WRITERS.items()))
def test_nothing_blocks_before_the_write(skill, write_call):
    manifest = ROOT / "plugins" / skill / "SKILL.md"
    text = manifest.read_text(encoding="utf-8")
    index = text.find(write_call)
    assert index != -1, f"{manifest} no longer calls `{write_call}`"
    offenders = [p.pattern for p in BLOCKING if p.search(text[:index])]
    assert not offenders, f"{manifest} blocks on the user before `{write_call}`: {offenders}"
```

- [ ] **Step 3: Run it**

Run: `.venv/bin/pytest tests/core/test_handoff_no_prewrite_gate.py -q`
Expected: PASS for handoff (PR #391 removed its gate). If `init-project` fails, read its gate
and classify it with the table above before touching it — it may be a legitimate outward gate,
in which case remove it from `WRITERS` and record why in the docstring.

- [ ] **Step 4: Commit**

```bash
git add .claude/rules/gates.md tests/core/test_handoff_no_prewrite_gate.py
git commit -m "docs(rules): a gate guards an outward action, never a pending write"
```

---

## Wave 2 — consistency, can slip past the release

### Task 6: scaffold-project calls its own entry point

**Evidence:** `h2t-scaffold-project` is a declared entry point (`pyproject.toml`, and `uv tool
list` shows all eight installed), yet
`plugins/h2t-core/skills/scaffold-project/SKILL.md:26-27` hand-rolls an `$H2T_PYTHON` probe for
`~/.h2t/venv`. It is the only skill in `h2t-core` still doing so; handoff, session-start,
init-project and project-audit all gate on `command -v h2t-*`.

**Files:**
- Modify: `plugins/h2t-core/skills/scaffold-project/SKILL.md:20-30, 212`
- Test: `tests/core/test_skill_entrypoints.py` (extend)

**Interfaces:**
- Consumes: `h2t-scaffold-project` on PATH

- [ ] **Step 1: Write the failing test**

```python
CLI_BACKED = {
    "h2t-core/skills/handoff": "h2t-handoff",
    "h2t-core/skills/session-start": "h2t-gather",
    "h2t-core/skills/init-project": "h2t-project-register",
    "h2t-core/skills/project-audit": "h2t-project-audit-scan",
    "h2t-core/skills/scaffold-project": "h2t-scaffold-project",
}

@pytest.mark.parametrize(("skill", "cli"), sorted(CLI_BACKED.items()))
def test_skill_gates_on_its_cli(skill, cli):
    text = (ROOT / "plugins" / skill / "SKILL.md").read_text(encoding="utf-8")
    assert f"command -v {cli}" in text, f"{skill} does not check for {cli}"
```

- [ ] **Step 2: Run it — only scaffold-project fails**

Run: `.venv/bin/pytest tests/core/test_skill_entrypoints.py -q -k gates_on_its_cli`
Expected: four PASS, `scaffold-project` FAIL.

- [ ] **Step 3: Replace the probe with the gate**

```bash
command -v h2t-scaffold-project >/dev/null 2>&1 || {
  echo "ERROR: h2t-scaffold-project not found. Run: uv tool install --editable <repo>"
  exit 1
}
```

Then replace the `$H2T_PYTHON -c "..."` block at `:212` with the equivalent
`h2t-scaffold-project` invocation. Read `h2t-scaffold-project --help` for the flag names — do
not guess them.

- [ ] **Step 4: Run the test, then the skill against a scratch directory**

Run: `.venv/bin/pytest tests/core/ -q`, then `h2t-scaffold-project --help`.
Expected: PASS; the CLI prints its usage.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-core/skills/scaffold-project/SKILL.md tests/core/test_skill_entrypoints.py
git commit -m "fix(scaffold-project): gate on the entry point like every other h2t-core skill"
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

- [ ] **Step 1: Write the failing test**

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

- [ ] **Step 2: Run it to confirm it fails**

Run: `.venv/bin/pytest lib/gather/test_project.py -q -k project_id_file`
Expected: FAIL — `result["id"]` is `unknown`.

- [ ] **Step 3: Read the file first**

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

- [ ] **Step 4: Make the writer emit `domain/project`**

`apply_registration.py:146` writes `project_id` alone, which forces the lookup above. Change it
to `f"{domain}/{project_id}\n"` and update
`plugins/h2t-core/skills/init-project/scripts/test_apply.py:139-161` — note that test asserts an
existing file is **not** overwritten, which must stay true.

- [ ] **Step 5: Mirror to the vendored copy and run parity**

```bash
cp lib/gather/project.py plugins/h2t-core/lib/gather/project.py
```

Run: `.venv/bin/pytest tests/core/test_vendored_lib_parity.py lib/gather/ -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add lib/gather/project.py plugins/h2t-core/lib/gather/project.py \
        plugins/h2t-core/skills/init-project/scripts/apply_registration.py \
        plugins/h2t-core/skills/init-project/scripts/test_apply.py lib/gather/test_project.py
git commit -m "feat(gather): resolve identity from .claude/project-id before the git remote"
```

---

### Task 8: Typed exit codes for the h2t-core entry points

**Evidence:** `h2t-ops` follows the taxonomy in CLAUDE.md — `h2t-ops nosuchconnector` and
`h2t-ops drive nosuchcommand` both exit `2` (usage). The seven other entry points do not:
`h2t-gather --cwd /nonexistent` exits `0` (Task 2 fixes that one), `h2t-handoff` with an
unwritable `--markdown-dir` exits `1` with no distinction between provider, usage and config
failure. None of them offer `--json`.

**Files:**
- Modify: `plugins/h2t-core/skills/handoff/scripts/writer.py` — `main()`
- Modify: `plugins/h2t-core/skills/session-start/scripts/gather.py` — `main()`
- Test: `tests/core/test_entrypoint_exit_codes.py` (create)

**Interfaces:**
- Produces: `0` ok, `2` usage, `3` config, `5` not found — the subset of the connector taxonomy
  these commands can actually hit

- [ ] **Step 1: Write the failing test**

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

- [ ] **Step 2: Run it to confirm the second case fails**

Run: `.venv/bin/pytest tests/core/test_entrypoint_exit_codes.py -q`
Expected: the usage case already passes (argparse exits 2); the unwritable-dir case FAILS with
`1`.

- [ ] **Step 3: Map the failures**

Wrap the write in `main()` so an `OSError` while creating the markdown directory exits `3` with
the path on stderr, leaving `1` for genuinely unexpected errors.

- [ ] **Step 4: Run and commit**

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

- [ ] **Step 1: Regenerate the entry-point list from the source of truth**

```bash
sed -n '/\[project.scripts\]/,/^\[/p' pyproject.toml
```

Paste the eight names into `CLAUDE.md`, each with one line saying what it does.

- [ ] **Step 2: Give both machines' commands**

Replace each single-path command block with both forms, labelled — Windows
`C:/dev/h2t-skills/.venv/Scripts/pytest`, Mac `.venv/bin/pytest` — and note that `ruff` comes
from `uvx` on the Mac.

- [ ] **Step 3: Verify each documented command actually runs**

Run every command block you touched, on this machine, and record the ones that fail. A
documented command that does not run is the defect this task exists to remove.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md .claude/rules/linting.md
git commit -m "docs: eight entry points, and commands that run on both machines"
```

---

## Release checklist

- [ ] PR #391 merged (handoff gate + cwd-derived identity)
- [ ] Wave 1 merged, `pytest tests/ lib/` green, every plugin directory green in CI
- [ ] `python scripts/bump_plugin.py h2t-core <next>` — and each other plugin Wave 2 touched
- [ ] `git push origin main`
- [ ] `/plugin marketplace update lichtpfad`, then `/reload-plugins`
- [ ] Verify the deploy by reading the cache, not the command output:
      `grep -c resolve_identity ~/.claude/plugins/cache/lichtpfad/h2t-core/<new>/skills/handoff/scripts/writer.py`
- [ ] Fresh-session smoke: `/h2t-core:session-start` shows a briefing with `### Previous Session`

## Out of scope, and why

Nine skills across `h2t-dev`, `h2t-edu`, `h2t-arch` and `h2t-creative` still invoke their
scripts directly (`$H2T_PYTHON ${CLAUDE_PLUGIN_ROOT}/skills/.../x.py`): `docs-lint`,
`docs-sync-labels`, `milestone-closure`, `youtube-transcript`, `convert-meeting-transcript`,
`process-transcripts`, `deck`, `landing`, `drawio`. That is not the defect this plan fixes —
none of them has a declared entry point, so there is no second path to disagree with. They
become worth migrating only if their scripts ever ship in the wheel. `plugins/h2t/` is a
rollback archive and is not shipped (`tests/core/test_skill_frontmatter.py`).

## Decisions needed before Wave 2

1. **`~/.claude/plugins/cache/lichtpfad/h2t-core/latest -> 3.2.18`** while the newest cached
   version is 3.2.22, and nine versions have accumulated. Our code reads versioned paths, so
   nothing is broken today. Clean it up, or document it as harness-owned and leave it?
2. **PR #339** (`feat/kb-lint-semantic-health`) has been open since May with a semantic
   conflict — `main` rewrote `kb/query.md`. Rebase it into the release, or close it?
3. **`lib/` as a shipped package.** If Task 1 empties `lib/cli/`, the only remaining reason to
   ship `lib` in the wheel disappears, since every plugin root carries its own vendored copy.
   Dropping it removes one of the two copies the parity test exists to police. In scope?
