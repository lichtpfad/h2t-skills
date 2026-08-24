"""A merged PR closes the plans it carried.

Retrospectively this link cannot be recovered — a plan slug appears in 7 of 60
merged PR bodies on this repo, and commit counts cannot separate "done and never
updated" from "abandoned". At the moment of the merge nothing has to be
inferred: the PR lists its own files. The link was never hard to compute, it was
just never written down while it was still free.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load():
    path = Path(__file__).parents[2] / "plugins" / "h2t-core" / "hooks-handlers" / "plan_closer.py"
    spec = importlib.util.spec_from_file_location("plan_closer_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _plan(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


# ── reading the PR number out of the command ────────────────────────────────


def test_pr_number_from_an_explicit_merge():
    m = _load()
    assert m.extract_pr_number("gh pr merge 408 --squash --delete-branch") == 408


def test_pr_number_ignores_flag_values():
    m = _load()
    assert m.extract_pr_number("gh pr merge --squash --delete-branch") is None


def test_non_merge_commands_are_not_ours():
    m = _load()
    assert m.extract_pr_number("gh pr view 408") is None
    assert m.extract_pr_number("git commit -m 'gh pr merge 12'") is None


# ── flipping the status ─────────────────────────────────────────────────────


_VIEW = {
    "state": "MERGED",
    "files": [
        {"path": "docs/superpowers/plans/2026-08-24-thing.md"},
        {"path": "docs/superpowers/specs/2026-08-24-thing-design.md"},
        {"path": "lib/thing.py"},
        {"path": "docs/reports/2026-08-24-evidence.md"},
    ],
}


def test_plans_and_specs_in_the_pr_are_closed(tmp_path):
    m = _load()
    _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md",
          '---\ntitle: "T"\nstatus: "draft"\ndate: "2026-08-24"\n---\nbody\n')
    _plan(tmp_path, "docs/superpowers/specs/2026-08-24-thing-design.md",
          '---\ntitle: "T"\nstatus: draft\n---\nbody\n')

    changed = m.close_plans_for_pr(tmp_path, 408, _VIEW)

    assert {c["path"] for c in changed} == {
        "docs/superpowers/plans/2026-08-24-thing.md",
        "docs/superpowers/specs/2026-08-24-thing-design.md",
    }
    text = (tmp_path / "docs/superpowers/plans/2026-08-24-thing.md").read_text()
    assert 'status: "done"' in text
    assert 'pr: 408' in text
    assert "body" in text


def test_reports_and_code_are_left_alone(tmp_path):
    """Only plans and specs carry a lifecycle. A report is a record of a moment."""
    m = _load()
    _plan(tmp_path, "docs/reports/2026-08-24-evidence.md",
          '---\ntitle: "E"\nstatus: "draft"\n---\nx\n')
    m.close_plans_for_pr(tmp_path, 408, _VIEW)
    assert 'status: "draft"' in (tmp_path / "docs/reports/2026-08-24-evidence.md").read_text()


def test_an_unmerged_pr_changes_nothing(tmp_path):
    """`gh pr merge` can fail. The hook runs either way."""
    m = _load()
    _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md",
          '---\nstatus: "draft"\n---\nx\n')
    assert m.close_plans_for_pr(tmp_path, 408, {"state": "OPEN", "files": _VIEW["files"]}) == []
    assert 'status: "draft"' in (tmp_path / "docs/superpowers/plans/2026-08-24-thing.md").read_text()


def test_an_already_closed_plan_is_not_touched_again(tmp_path):
    m = _load()
    p = _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md",
              '---\nstatus: "done"\npr: 12\n---\nx\n')
    before = p.read_text()
    assert m.close_plans_for_pr(tmp_path, 408, _VIEW) == []
    assert p.read_text() == before


def test_a_file_deleted_by_the_pr_is_skipped(tmp_path):
    """The PR may have moved a plan into docs/archive/ — nothing to rewrite."""
    m = _load()
    assert m.close_plans_for_pr(tmp_path, 408, _VIEW) == []


def test_a_plan_without_frontmatter_is_skipped_not_corrupted(tmp_path):
    m = _load()
    p = _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md", "# Plain\n\nbody\n")
    assert m.close_plans_for_pr(tmp_path, 408, _VIEW) == []
    assert p.read_text() == "# Plain\n\nbody\n"


def test_existing_pr_field_is_replaced_not_duplicated(tmp_path):
    m = _load()
    p = _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md",
              '---\nstatus: "draft"\npr: 12\n---\nx\n')
    m.close_plans_for_pr(tmp_path, 408, _VIEW)
    assert p.read_text().count("pr:") == 1
    assert "pr: 408" in p.read_text()


# ── the hook's own output contract ──────────────────────────────────────────


def test_hook_reports_on_both_channels(tmp_path, monkeypatch, capsys):
    """The model reads additionalContext; the user reads systemMessage."""
    m = _load()
    _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md",
          '---\nstatus: "draft"\n---\nx\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(m, "_pr_view", lambda root, n: _VIEW)
    monkeypatch.setattr(
        m, "_load_payload",
        lambda: {"tool_name": "Bash", "tool_input": {"command": "gh pr merge 408 --squash"}},
    )
    assert m.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert "408" in out["systemMessage"]
    assert "2026-08-24-thing.md" in out["hookSpecificOutput"]["additionalContext"]


def test_hook_is_silent_for_unrelated_commands(monkeypatch, capsys):
    m = _load()
    monkeypatch.setattr(
        m, "_load_payload",
        lambda: {"tool_name": "Bash", "tool_input": {"command": "ls -la"}},
    )
    assert m.main() == 0
    assert capsys.readouterr().out == ""


def test_message_distinguishes_a_plan_from_its_spec(tmp_path, monkeypatch, capsys):
    """Plan and spec routinely share a stem — basenames alone read as a duplicate."""
    m = _load()
    _plan(tmp_path, "docs/superpowers/plans/2026-08-24-thing.md",
          '---\nstatus: "draft"\n---\nx\n')
    _plan(tmp_path, "docs/superpowers/specs/2026-08-24-thing.md",
          '---\nstatus: "draft"\n---\nx\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(m, "_pr_view", lambda root, n: {
        "state": "MERGED",
        "files": [{"path": "docs/superpowers/plans/2026-08-24-thing.md"},
                  {"path": "docs/superpowers/specs/2026-08-24-thing.md"}],
    })
    monkeypatch.setattr(m, "_load_payload", lambda: {
        "tool_name": "Bash", "tool_input": {"command": "gh pr merge 408"}})
    m.main()
    msg = json.loads(capsys.readouterr().out)["systemMessage"]
    assert "plans/2026-08-24-thing.md" in msg
    assert "specs/2026-08-24-thing.md" in msg
