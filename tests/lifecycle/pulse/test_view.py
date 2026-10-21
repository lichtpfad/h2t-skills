"""The terminal view: list, filters, resume command, settle_open, local status."""

from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path

import pytest

from h2t_ops.lifecycle import session_record
from h2t_ops.lifecycle.index import query
from h2t_ops.lifecycle.pulse import cli, record, status, view


@pytest.fixture(autouse=True)
def _machine(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")


def _rec(sid: str, tmp_path: Path, **over) -> Path:
    fields = {"tool": "claude", "origin": "live", "user_msgs": 2, "project": "p1", "domain": "d1",
              "cwd": str(tmp_path / "r1"), "repo": str(tmp_path / "r1"), "branch": "b1",
              "worktree": str(tmp_path / "r1"), "started_at": "2026-10-10T10:00:00Z",
              "summary": f"summary of {sid}", **over}
    return record.upsert(sid, fields)


def _branch(repo: str, branch: str, **over) -> None:
    row = {"worktree": repo, "files": "чисто", "branch_state": "отправлена", "pr": "нет",
           "pr_url": "", "issues": "{}", "verdict": "ждёт PR",
           "checked_at": "2026-10-10T10:00:00+00:00", **over}
    with query.connect() as conn:
        conn.execute("INSERT OR REPLACE INTO branch_status VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (repo, branch, row["worktree"], row["files"], row["branch_state"], row["pr"],
                      row["pr_url"], row["issues"], row["verdict"], row["checked_at"]))
        conn.commit()


def _write(path: Path, records: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def _claude_tr(path: Path, cwd: str, users: int) -> Path:
    recs = [{"timestamp": f"2026-10-10T10:0{i}:00Z", "type": "user", "cwd": cwd, "entrypoint": "cli",
             "message": {"role": "user", "content": f"hello {i}"}} for i in range(users)]
    recs.append({"timestamp": "2026-10-10T10:09:00Z", "type": "assistant", "cwd": cwd,
                 "entrypoint": "cli", "message": {"role": "assistant", "content": "ok"}})
    return _write(path, recs)


def _codex_exec_tr(path: Path, sid: str, cwd: str) -> Path:
    return _write(path, [
        {"timestamp": "2026-10-10T10:00:00Z", "type": "session_meta",
         "payload": {"id": sid, "cwd": cwd, "originator": "codex_exec"}},
        {"timestamp": "2026-10-10T10:01:00Z", "type": "response_item",
         "payload": {"type": "message", "role": "user",
                     "content": [{"type": "input_text", "text": "hello"}]}}])


def _ids(rows: list[dict]) -> set[str]:
    return {r["session_id"] for r in rows}


def _meta(sid: str) -> dict:
    found = record.find(sid, "test-machine")
    assert found is not None
    return session_record.parse(found.read_bytes())[0]


def test_resume_commands():
    assert view.resume_command("codex", "u1", "C:/r") == 'codex resume u1 -C "C:/r"'
    assert view.resume_command("claude", "u1", "C:/r") == 'cd "C:/r"; claude --resume u1'


@pytest.fixture
def three(tmp_path):
    r1, r2 = str(tmp_path / "r1"), str(tmp_path / "r2")
    _rec("A", tmp_path, domain="d1", project="p1", repo=r1, branch="b1", tool="claude",
         started_at="2026-10-10T10:00:00Z")
    _rec("B", tmp_path, domain="d2", project="p2", repo=r2, branch="b2", tool="codex",
         started_at="2026-10-01T10:00:00Z")
    _rec("C", tmp_path, domain="d2", project="p2", repo=r2, branch="b2", tool="claude",
         started_at="2026-10-02T10:00:00Z")
    _branch(r1, "b1", verdict="ждёт PR", pr="открыт")
    _branch(r2, "b2", verdict="готово", pr="влит")
    return tmp_path


@pytest.mark.parametrize("flt, value, expected", [
    ("domain", "d1", {"A"}),
    ("project", "p2", {"B", "C"}),
    ("repo", "r2", {"B", "C"}),
    ("status", "ждёт PR", {"A"}),
    ("pr", "открыт", {"A"}),
    ("tool", "codex", {"B"}),
    ("since", "2026-10-05", {"A"}),
])
def test_each_filter_narrows(three, flt, value, expected):
    assert _ids(view.rows(view.Filters())) == {"A", "B", "C"}
    assert _ids(view.rows(view.Filters(**{flt: value}))) == expected


def test_unknown_hidden_unless_all(tmp_path):
    _rec("L", tmp_path)
    _rec("U", tmp_path, origin="unknown")
    _rec("M", tmp_path, origin="machine")
    assert _ids(view.rows(view.Filters())) == {"L"}
    assert _ids(view.rows(view.Filters(all=True))) == {"L", "U", "M"}


def test_empty_session_hidden(tmp_path):
    _rec("run", tmp_path, user_msgs=0)
    _rec("done", tmp_path, user_msgs=0, ended_at="2026-10-10T11:00:00Z")
    _rec("full", tmp_path)
    assert _ids(view.rows(view.Filters())) == {"full"}
    assert _ids(view.rows(view.Filters(all=True))) == {"run", "done", "full"}


def test_settle_open_reveals_a_running_session(tmp_path, capsys):
    cwd = str(tmp_path / "r1")
    tr = _claude_tr(tmp_path / "t" / "run.jsonl", cwd, users=1)
    record.write_draft("run", {"tool": "claude", "origin": "live", "cwd": cwd, "project": "p1",
                               "domain": "d1", "transcript": str(tr),
                               "started_at": "2026-10-10T10:00:00Z"})
    assert record.find("run", "test-machine") is None
    assert cli.main(["list"]) == 0
    assert "run" in capsys.readouterr().out
    assert _meta("run")["user_msgs"] == 1
    assert not record.draft_path("run").exists()


def test_settle_open_leaves_a_draft_without_user_messages(tmp_path):
    cwd = str(tmp_path / "r1")
    tr = _claude_tr(tmp_path / "t" / "idle.jsonl", cwd, users=0)
    record.write_draft("idle", {"tool": "claude", "origin": "live", "cwd": cwd, "project": "p1",
                                "transcript": str(tr)})
    assert record.settle_open() == 0
    assert record.draft_path("idle").exists()
    assert record.find("idle", "test-machine") is None


def test_settle_open_hides_a_machine_session(tmp_path):
    cwd = str(tmp_path / "r1")
    tr = _codex_exec_tr(tmp_path / "t" / "cx-draft.jsonl", "cx-draft", cwd)
    record.write_draft("cx-draft", {"tool": "codex", "origin": "unknown", "cwd": cwd,
                                    "project": "p1", "transcript": str(tr)})
    tr2 = _codex_exec_tr(tmp_path / "t" / "cx-rec.jsonl", "cx-rec", cwd)
    _rec("cx-rec", tmp_path, tool="codex", origin="unknown", transcript=str(tr2), user_msgs=1)
    record.settle_open()
    assert not record.draft_path("cx-draft").exists()
    assert record.find("cx-draft", "test-machine") is None        # never became a record
    assert _meta("cx-rec")["origin"] == "machine"                 # the file stays
    assert record.find("cx-rec", "test-machine").exists()
    assert _ids(view.rows(view.Filters())) == set()
    assert _ids(view.rows(view.Filters(all=True))) == {"cx-rec"}


def test_settle_open_skips_an_unreadable_transcript(tmp_path, monkeypatch):
    cwd = str(tmp_path / "r1")
    tr = _claude_tr(tmp_path / "t" / "bad.jsonl", cwd, users=1)
    _rec("bad", tmp_path, transcript=str(tr), user_msgs=0)

    def boom(tool, path):
        raise OSError("gone")
    monkeypatch.setattr(record.transcript, "read", boom)
    assert record.settle_open() == 0                              # counted, never aborts


def test_list_is_offline_and_does_not_rebuild(tmp_path, monkeypatch, capsys):
    _rec("A", tmp_path)

    def boom(*a, **k):
        raise AssertionError("network or rebuild touched")
    monkeypatch.setattr(status, "_gh", boom)
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(query, "rebuild", boom)
    assert cli.main(["list"]) == 0
    assert "summary of A" in capsys.readouterr().out


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


@pytest.fixture
def work(tmp_path) -> Path:
    w = tmp_path / "work"
    subprocess.run(["git", "init", "-b", "main", str(w)], check=True, capture_output=True)
    (w / "a.txt").write_text("a", encoding="utf-8")
    _git(w, "add", "a.txt")
    _git(w, "commit", "-m", "base")
    _git(w, "checkout", "-b", "feat/x")
    (w / "b.txt").write_text("b", encoding="utf-8")
    _git(w, "add", "b.txt")
    _git(w, "commit", "-m", "work")
    return w


def _status_row(repo: str, branch: str):
    with query.connect() as conn:
        return conn.execute("SELECT * FROM branch_status WHERE repo=? AND branch=?",
                            (repo, branch)).fetchone()


def test_new_session_gets_local_status_before_daily(tmp_path, work, monkeypatch):
    monkeypatch.setattr(status, "_gh", lambda *a, **k: (_ for _ in ()).throw(AssertionError("gh")))
    _rec("N", tmp_path, repo=str(work), worktree=str(work), cwd=str(work), branch="feat/x")
    assert _status_row(str(work), "feat/x") is None
    assert cli.main(["list"]) == 0
    row = _status_row(str(work), "feat/x")
    assert row["files"] == "чисто"
    assert row["verdict"] == "не отправлено"
    assert row["pr"] == ""


def test_local_status_keeps_pr_and_issues_and_skips_fresh_rows(tmp_path, work):
    _rec("N", tmp_path, repo=str(work), worktree=str(work), cwd=str(work), branch="feat/x")
    _branch(str(work), "feat/x", files="3 незакоммиченных", pr="открыт",
            pr_url="https://example.invalid/pr/1", issues='{"12": "unknown"}',
            verdict="брошено с изменениями", checked_at="2000-01-01T00:00:00+00:00")
    with query.connect() as conn:
        assert status.local_status(conn) == 1
        assert status.local_status(conn) == 0                      # just checked: fresh
    row = _status_row(str(work), "feat/x")
    assert row["files"] == "чисто" and row["verdict"] == "не отправлено"
    assert (row["pr"], row["pr_url"], row["issues"]) == (
        "открыт", "https://example.invalid/pr/1", '{"12": "unknown"}')


def test_handoff_done_is_the_summary(tmp_path):
    _rec("H", tmp_path, summary="", done="first\nsecond\nthird\nfourth")
    row = view.rows(view.Filters())[0]
    assert row["summary_source"] == "handoff"
    assert row["summary"] == "first\nsecond\nthird"


def test_summary_wins_over_done(tmp_path):
    _rec("S", tmp_path, summary="short", summary_source="model", done="long text")
    row = view.rows(view.Filters())[0]
    assert (row["summary"], row["summary_source"]) == ("short", "model")


def test_render_groups_and_resume_lines(three):
    out = view.render(view.rows(view.Filters()), "footer text")
    lines = out.splitlines()
    assert [i for i, ln in enumerate(lines) if ln.strip() in ("d1", "d2")] != []
    assert lines.index(next(ln for ln in lines if ln.strip() == "d1")) < \
        lines.index(next(ln for ln in lines if ln.strip() == "p1"))
    branch_line = next(ln for ln in lines if ln.strip().startswith("b2"))
    assert "[готово]" in branch_line and "PR: влит" in branch_line and "чисто" in branch_line
    assert lines[-1] == "footer text"
    # newest first inside a branch: C (10-02) before B (10-01)
    assert out.index("summary of C") < out.index("summary of B")
    # the resume command sits on the line right after its session line
    i = next(n for n, ln in enumerate(lines) if "summary of B" in ln)
    assert lines[i + 1].strip() == view.resume_command("codex", "B", lines[i + 1].split('"')[1])


def test_render_issue_unknown_shows_question_mark(tmp_path):
    _rec("I", tmp_path)
    _branch(str(tmp_path / "r1"), "b1", issues='{"12": "open", "13": "unknown"}')
    out = view.render(view.rows(view.Filters()), "")
    line = next(ln for ln in out.splitlines() if ln.strip().startswith("b1"))
    assert line.endswith("#12 open #13 ?")


def test_cli_list_exits_0_and_prints_resume(tmp_path, capsys):
    _rec("A", tmp_path)
    assert cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "claude --resume A" in out
    assert cli.main([]) == 0                                       # list is the default
    assert "claude --resume A" in capsys.readouterr().out


def test_cli_list_json(tmp_path, capsys):
    _rec("A", tmp_path)
    assert cli.main(["list", "--json"]) == 0
    got = json.loads(capsys.readouterr().out)
    assert [r["session_id"] for r in got["result"]] == ["A"]


def test_empty_index_says_so(capsys):
    assert cli.main(["list"]) == 0
    assert "нет сессий" in capsys.readouterr().out


def test_cli_status_refreshes_with_a_stub(tmp_path, monkeypatch, capsys):
    called = []
    monkeypatch.setattr(status, "refresh", lambda conn, **k: called.append(1) or 4)
    assert cli.main(["status"]) == 0
    assert called == [1]
    assert "4" in capsys.readouterr().out


def test_cli_unknown_subcommand_is_a_usage_error(capsys):
    assert cli.main(["nope"]) == 2
