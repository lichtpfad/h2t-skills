"""`h2t-runbook`: the autonomous-run skill's scripts as a command (Task 12)."""
from __future__ import annotations

import json

import pytest

from h2t_ops.tools.runbook import cli

FIELDS = ["--title", "T", "--branch", "b", "--spec-path", "s.md", "--issue", "#1",
          "--venv-test", "pytest", "--e2e-state", "N/A (no integration surface)"]


def test_new_writes_a_runbook_that_validates(tmp_path, capsys):
    dest = tmp_path / "plans" / "2026-10-17-x-runbook.md"
    assert cli.main(["new", str(dest), *FIELDS, "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "path": str(dest)}
    assert str(dest) in dest.read_text(encoding="utf-8")  # runbook_path is the destination
    assert cli.main(["validate", str(dest), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "problems": []}


def test_state_lists_the_unchecked_steps(tmp_path, capsys):
    dest = tmp_path / "r.md"
    cli.main(["new", str(dest), *FIELDS])
    capsys.readouterr()
    text = dest.read_text(encoding="utf-8").replace("- [ ] **write-spec**", "- [x] **write-spec**")
    dest.write_text(text, encoding="utf-8")
    assert cli.main(["state", str(dest), "--json"]) == 0
    state = json.loads(capsys.readouterr().out)
    assert state["active"] is True
    assert state["unchecked"][0] == "review-spec"


def test_a_gutted_runbook_fails_validation(tmp_path, capsys):
    dest = tmp_path / "r.md"
    dest.write_text("# nothing here\n", encoding="utf-8")
    assert cli.main(["validate", str(dest), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["problems"]


def test_an_invalid_field_writes_nothing(tmp_path, capsys):
    dest = tmp_path / "r.md"
    args = [a if a != "N/A (no integration surface)" else "maybe" for a in FIELDS]
    assert cli.main(["new", str(dest), *args, "--json"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and set(out["error"]) == {"message", "hint"}
    assert not dest.exists()


@pytest.mark.parametrize("verb", ["validate", "state"])
def test_a_missing_runbook_is_an_envelope_not_a_traceback(tmp_path, capsys, verb):
    assert cli.main([verb, str(tmp_path / "nope.md"), "--json"]) == 5
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert "nope.md" in out["error"]["message"] and out["error"]["hint"]


def test_a_missing_runbook_without_json_says_so_on_stderr(tmp_path, capsys):
    assert cli.main(["state", str(tmp_path / "nope.md")]) == 5
    assert "no runbook at" in capsys.readouterr().err
