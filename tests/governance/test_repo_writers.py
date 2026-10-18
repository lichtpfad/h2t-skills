"""Every write into a user's repository goes through store.repo and its allow-list (#548 §7.1).

Each command of REPO_WRITERS runs in a scratch repository under a Recorder guarding only
that repository: a write that did not come through store is a violation, and every path
the command changed must match one of its patterns. The list of patterns is the measured
one (docs/reports/2026-10-18-storage-repo-writers.md), not a guess.

What the recorder cannot see: child processes. `git mv` inside RepoWriter.rename and the
docs-init that scaffold runs in a child process are covered by the second assertion only —
the paths they changed are still matched against the allow-list.
"""
from __future__ import annotations

import fnmatch
import hashlib
import os
from pathlib import Path

import pytest

from h2t_ops.core.repo_writers import REPO_WRITERS
from tests.governance import audit
from tests.governance.sandbox_cases import REPO_SCENARIOS


def snapshot(root: Path) -> dict[str, str | None]:
    """sha256 of every file, and every directory as "<rel>/". Of .git only
    info/exclude, which scaffold appends to; the rest is git's own."""
    out: dict[str, str | None] = {}
    if not root.exists():
        return out
    for d, dirs, files in os.walk(root):
        rel_d = Path(d).relative_to(root).as_posix()
        if rel_d == ".":
            rel_d = ""
            if ".git" in dirs:
                dirs.remove(".git")
                exclude = root / ".git" / "info" / "exclude"
                if exclude.is_file():
                    out[".git/info/exclude"] = hashlib.sha256(exclude.read_bytes()).hexdigest()
        prefix = f"{rel_d}/" if rel_d else ""
        for f in files:
            out[prefix + f] = hashlib.sha256((Path(d) / f).read_bytes()).hexdigest()
        if rel_d:
            out[prefix] = None
    return out


def changed(before: dict, after: dict) -> set[str]:
    """Files added, modified or removed, and the deepest new directories that hold none
    of them (mkdir); a directory a rename emptied is not a write."""
    out = {p for p in before.keys() | after.keys()
           if not p.endswith("/") and before.get(p, "-") != after.get(p, "-")}
    new_dirs = {d for d in after if d.endswith("/") and d not in before}
    return out | {d for d in new_dirs if not any(p != d and p.startswith(d) for p in out | new_dirs)}


def allowed(command: str, also: tuple[str, ...]) -> list[str]:
    return [g for c in (command, *also) for globs in REPO_WRITERS[c].values() for g in globs]


def outside(paths: set[str], globs: list[str]) -> list[str]:
    return sorted(p for p in paths if not any(fnmatch.fnmatchcase(p.rstrip("/"), g) for g in globs))


def test_every_command_has_a_scenario():
    """A command added to REPO_WRITERS without a scenario would be pinned by nothing.
    The two registration commands are Task 15's and are run by tests/lifecycle."""
    assert set(REPO_WRITERS) == set(REPO_SCENARIOS) | {"init-project", "h2t-project-register"}


@pytest.mark.parametrize("command", sorted(REPO_SCENARIOS))
def test_command_writes_only_through_store_and_its_allow_list(command, tmp_path, monkeypatch):
    setup, run, also = REPO_SCENARIOS[command]
    repo = tmp_path / "repo"
    if setup is not None:
        setup(repo, monkeypatch)
    before = snapshot(repo)
    rec = audit.Recorder([repo], [], [], {})
    with rec.active():
        run(repo, monkeypatch)
    after = snapshot(repo)
    assert rec.violations == [], "\n".join(rec.violations)
    touched = changed(before, after)
    assert touched, f"{command} changed nothing: the scenario does not reach its writes"
    assert outside(touched, allowed(command, also)) == [], f"all changed: {sorted(touched)}"


def test_snapshot_sees_a_planted_write_outside_the_allow_list(tmp_path):
    """Control: the second assertion reports a path no pattern covers."""
    repo = tmp_path / "repo"
    repo.mkdir()
    before = snapshot(repo)
    (repo / "stray.txt").write_text("x", encoding="utf-8")
    (repo / "empty").mkdir()
    touched = changed(before, snapshot(repo))
    assert touched == {"stray.txt", "empty/"}
    assert outside(touched, allowed("h2t-docs-init", ())) == ["empty/", "stray.txt"]


def test_type_root_dirs_are_the_project_types_root_dirs():
    """scaffold and fix-safe lay out PROJECT_TYPES root_dirs; a new type adds a directory
    the allow-list would refuse."""
    from h2t_ops.core import repo_writers
    from h2t_ops.tools.docs.project_types import PROJECT_TYPES
    declared = {d for t in PROJECT_TYPES.values() for d in t.get("root_dirs", [])}
    assert set(repo_writers._TYPE_ROOT_DIRS) == declared


def test_hook_report_ignore_lands_in_the_main_repository_of_a_worktree(tmp_path):
    """In a worktree .git is a file; git names the exclude file, which lies in the main
    repository, outside the worktree — written through store with dest=True."""
    import subprocess

    from h2t_ops.lifecycle.scaffold_project import ensure_hook_report_cache_ignored
    from tests.governance.sandbox_cases import _git_repo
    main, wt = tmp_path / "main", tmp_path / "wt"
    _git_repo(main, {"a.txt": "a"})
    subprocess.run(["git", "-C", str(main), "worktree", "add", "-q", str(wt)], check=True)
    exclude = main / ".git" / "info" / "exclude"
    rec = audit.Recorder([main, wt], [], [], {})
    with rec.active():
        ensure_hook_report_cache_ignored(wt)
    assert exclude.read_text(encoding="utf-8").splitlines().count(".h2t/lifecycle/*.json") == 1
    with rec.active():
        ensure_hook_report_cache_ignored(main)      # the same file: no second line
    assert exclude.read_text(encoding="utf-8").splitlines().count(".h2t/lifecycle/*.json") == 1
    assert rec.violations == []


@pytest.mark.parametrize("configured, moved", [("outputs", True), ("../outside", False),
                                               ("/abs", False), (".git/x", False)])
def test_fix_safe_moves_into_the_configured_deliverables_dir(configured, moved, tmp_path):
    """docs-lint.yaml deliverables_dir (config.py) is the rename target fix-safe may use;
    a value that does not stay inside the repository moves nothing."""
    from h2t_ops.tools.docs import lint
    from tests.governance.sandbox_cases import _git_repo
    repo = tmp_path / "repo"
    _git_repo(repo, {".claude/rules/docs-lint.yaml": f"project_checks: true\ndeliverables_dir: {configured}\n",
                     "docs/a.pdf": "pdf", "outputs/.gitkeep": ""})
    rec = audit.Recorder([repo], [], [], {})
    with rec.active():
        fixes = lint._apply_misplaced_moves(repo, lint.load_config(repo))
    assert rec.violations == []
    assert (repo / "outputs" / "a.pdf").exists() is moved, fixes
    assert (repo / "docs" / "a.pdf").exists() is not moved
    if not moved:
        assert fixes == [f"SKIP: deliverables_dir {configured!r} is not a directory inside the repository"]


def test_a_new_repo_directory_is_journaled_once(tmp_path):
    """RepoWriter.mkdir writes a writes.jsonl row for a directory it created, none for one
    that was there."""
    import json

    from h2t_ops.core import paths, store
    repo = tmp_path / "repo"
    repo.mkdir()
    rw = store.repo(repo, "h2t-scaffold-project")
    rw.mkdir("src")
    rw.mkdir("src")
    log = paths.logs_dir() / "writes.jsonl"
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    mk = [r for r in rows if r["op"] == "mkdir"]
    assert [r["path"] for r in mk] == [str(Path(os.path.realpath(repo)) / "src")]


@pytest.mark.parametrize("configured", ["*", ".g?t", "[.]git", ".GIT"])
def test_a_glob_or_git_deliverables_dir_cannot_reach_git(configured, tmp_path):
    """deliverables_dir is data, not a pattern: a value that would widen fix-safe's rename
    rule, or name .git in another case, moves nothing — not by misplaced-moves and not by a
    --plan move_file into .git/hooks."""
    import json

    from h2t_ops.tools.docs import lint
    from tests.governance.sandbox_cases import _git_repo
    repo = tmp_path / "repo"
    _git_repo(repo, {".claude/rules/docs-lint.yaml": f'project_checks: true\ndeliverables_dir: "{configured}"\n',
                     "docs/a.pdf": "pdf", "docs/x.pdf": "pdf"})
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"plan_id": "p", "actions": [
        {"action_id": "m", "type": "move_file", "path": "docs/x.pdf",
         "target_path": ".git/hooks/pre-commit", "risk": "safe"}]}), encoding="utf-8")
    fixes = lint._apply_misplaced_moves(repo, lint.load_config(repo))
    lint._run_fix_safe(repo, plan_file=str(plan))
    assert not (repo / ".git" / "hooks" / "pre-commit").exists()
    assert (repo / "docs" / "x.pdf").exists() and (repo / "docs" / "a.pdf").exists()
    assert not (repo / ".git" / "a.pdf").exists()
    assert fixes == [f"SKIP: deliverables_dir {configured!r} is not a directory inside the repository"]
