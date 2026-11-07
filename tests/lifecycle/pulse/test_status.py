"""Work status per branch: real git repos with a bare origin, gh stubbed."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from h2t_ops.lifecycle.index import schema
from h2t_ops.lifecycle.pulse import status


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                           *args], capture_output=True, text=True, check=True)
    return done.stdout.strip()


def commit(repo: Path, name: str, text: str, message: str = "c") -> str:
    (repo / name).write_text(text, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-m", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path) -> Path:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True,
                   capture_output=True)
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-b", "main", str(work)], check=True, capture_output=True)
    git(work, "remote", "add", "origin", str(origin))
    commit(work, "base.txt", "base")
    git(work, "push", "-u", "origin", "main")
    git(work, "remote", "set-head", "origin", "main")
    return work


def no_gh(repo, args):
    return []


def test_squash_merged_branch_is_merged(repo):
    git(repo, "checkout", "-b", "feat/x")
    commit(repo, "a.txt", "same")
    git(repo, "checkout", "main")
    commit(repo, "a.txt", "same", "squash of feat/x")      # different commit, same content
    git(repo, "push", "origin", "main")
    assert status.branch_state(str(repo), "feat/x", "main") == "влита"
    assert status.verdict("чисто", "влита", "нет") == "готово"


def test_unpushed_branch(repo):
    git(repo, "checkout", "-b", "feat/y")
    commit(repo, "b.txt", "work")
    state = status.branch_state(str(repo), "feat/y", "main")
    assert state == "не отправлена"
    assert status.verdict("чисто", state, "нет") == "не отправлено"


def test_pushed_without_pr_waits(repo):
    git(repo, "checkout", "-b", "feat/z")
    commit(repo, "c.txt", "work")
    git(repo, "push", "-u", "origin", "feat/z")
    state = status.branch_state(str(repo), "feat/z", "main")
    assert state == "отправлена"
    assert status.verdict("чисто", state, "нет") == "ждёт PR"


def test_dirty_tree_is_abandoned_with_changes(repo):
    git(repo, "checkout", "-b", "feat/d")
    commit(repo, "d.txt", "work")
    git(repo, "push", "-u", "origin", "feat/d")
    (repo / "new.txt").write_text("x", encoding="utf-8")
    files = status.files_state(str(repo))
    assert files == "1 незакоммиченных"
    assert status.verdict(files, "влита", "влит") == "брошено с изменениями"


def test_missing_worktree_does_not_crash(tmp_path, repo):
    assert status.files_state(str(tmp_path / "gone")) == "нет копии"
    assert status.files_state("") == "нет копии"
    assert status.verdict("нет копии", "не отправлена", "нет") == "не отправлено"


def test_commits_after_merged_pr_are_not_merged(repo):
    git(repo, "checkout", "-b", "feat/m")
    head = commit(repo, "m.txt", "one")
    git(repo, "push", "-u", "origin", "feat/m")
    commit(repo, "m2.txt", "after the merge")
    pr = {"number": 5, "state": "MERGED", "url": "u", "headRefOid": head, "body": ""}
    assert status.branch_state(str(repo), "feat/m", "main", pr=pr) != "влита"
    assert status.branch_state(str(repo), "feat/m", "main",
                               pr={**pr, "headRefOid": git(repo, "rev-parse", "HEAD")}) == "влита"
    assert status.branch_state(str(repo), "main", "main") == "основная"


def test_issue_numbers_from_branch_and_commits(tmp_path, repo):
    git(repo, "checkout", "-b", "fix/123-x")
    commit(repo, "i.txt", "work", "fix thing\n\ncloses #7")
    conn = sqlite3.connect(":memory:")
    schema.ensure(conn)
    conn.execute("INSERT INTO sessions(path, repo, branch, worktree, origin, artifacts, updated_at)"
                 " VALUES ('p1', ?, 'fix/123-x', ?, 'live', ?, '2026-10-20')",
                 (str(repo), str(repo), json.dumps(["issue:9"])))
    conn.execute("INSERT INTO sessions(path, repo, branch, worktree, origin, updated_at)"
                 " VALUES ('p2', ?, 'other', ?, 'import', '2026-10-20')", (str(repo), str(repo)))
    calls = []

    def gh(repo_path, args):
        calls.append(args)
        if args[:2] == ["issue", "view"]:
            return {"state": "CLOSED" if args[2] == "7" else "OPEN"}
        return []

    assert status.refresh(conn, gh=gh) == 1                 # the import session gets no row
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM branch_status").fetchone()
    issues = json.loads(row["issues"])
    assert set(issues) == {"123", "7", "9"}
    assert issues["7"] == "closed" and issues["123"] == "open"
