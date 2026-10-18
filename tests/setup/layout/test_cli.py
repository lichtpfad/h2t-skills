"""`h2t-setup layout` runs where it was launched, editable install included (plan R13)."""
from __future__ import annotations

import json

import pytest

from h2t_ops.setup import cli, manifest, state, sync
from h2t_ops.setup.layout import engine


@pytest.fixture
def editable(monkeypatch, tmp_path):
    install = state.Install(version="4.0.0", generation="g", tool_root=str(tmp_path / "t"),
                            entrypoints={}, editable=str(tmp_path / "checkout"))
    monkeypatch.setattr(state, "read", lambda: install)
    monkeypatch.setattr(sync, "ensure_executor",
                        lambda *a, **k: pytest.fail("layout must not re-launch"))
    monkeypatch.setattr(manifest, "urllib_fetch",
                        lambda url: pytest.fail("layout must not read the target"))
    return install


def test_layout_runs_on_an_editable_install(editable, monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(engine, "migrate",
                        lambda report, *, machine=None: seen.append(machine) or report.done.append("layout 1"))
    assert cli.main(["layout", "migrate", "--machine", "m", "--json"]) == 0
    assert seen == ["m"]
    assert json.loads(capsys.readouterr().out)["result"]["done"] == ["layout 1"]


def test_sync_still_refuses_editable(editable, capsys):
    assert cli.main(["sync", "--json"]) == 3
    assert json.loads(capsys.readouterr().err)["error"]["details"]["reason"] == "editable"


def test_layout_flags_live_on_layout_only():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["sync", "--machine", "m"])
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["dev-sync", "--sync-paused"])


def test_rollback_without_sync_paused_is_a_usage_error(capsys):
    assert cli.main(["layout", "rollback", "--json"]) == 2
    assert "pause the sync" in json.loads(capsys.readouterr().err)["error"]["message"]
