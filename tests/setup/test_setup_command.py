"""`h2t-ops setup <verb>`: the setup skill's backend as a command (Task 12).

The skill ran `uv run ... python scripts/setup_h2t.py <verb>`; the module is now
h2t_ops/setup/legacy.py, reached through the h2t-ops dispatcher.
"""
from __future__ import annotations

import json

import pytest

from h2t_ops import cli
from h2t_ops.setup import legacy


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def test_install_dry_run_through_the_dispatcher(monkeypatch, capsys):
    monkeypatch.setattr(legacy, "resolve_uv", lambda: {"status": "ready", "path": "uv", "source": "t"})
    assert cli.dispatch(["setup", "install-h2t-ops", "--source", "main", "--dry-run", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "dry_run"
    assert out["command"][:3] == ["uv", "tool", "install"]


def test_secrets_skeleton_reads_the_packaged_registry(home, monkeypatch, capsys):
    monkeypatch.delenv("H2T_SECRETS_FILE", raising=False)
    assert cli.dispatch(["setup", "secrets", "skeleton", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out.get("kind") != "h2t_setup_error/v1", out  # the registry was found
    assert "added" in out
    # Not whether the file was written: a key another test put in os.environ is skipped.
    assert out["path"] == str(home / ".h2t" / "secrets" / "shared")   # one file per provider (R40)


def test_an_unknown_verb_is_a_usage_error(capsys):
    assert cli.dispatch(["setup", "bogus"]) == 2
    assert "invalid choice" in capsys.readouterr().err


def test_setup_is_listed_in_the_top_level_parser():
    choices = cli.build_parser()._subparsers._group_actions[0].choices
    assert "setup" in choices


def test_the_real_install_is_refused_in_process(monkeypatch, capsys):
    """The process is the h2t-ops tool `uv tool install` replaces; on Windows its exe is
    locked. So the command hands the exact uv line back instead of running it."""
    monkeypatch.setattr(legacy, "resolve_uv", lambda: {"status": "ready", "path": "uv", "source": "t"})
    # `runner` is bound at def time; replace the default itself so nothing can run uv.
    def never(command, timeout):
        pytest.fail(f"ran {command}")
    monkeypatch.setattr(legacy.install_h2t_ops, "__kwdefaults__",
                        {"dry_run": False, "runner": never})
    assert cli.dispatch(["setup", "install-h2t-ops", "--source", "main", "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "error"
    assert out["command"][:4] == ["uv", "tool", "install", "--reinstall"]
    assert "uv tool install --reinstall" in out["hint"]
