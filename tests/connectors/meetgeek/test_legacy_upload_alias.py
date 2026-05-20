"""Regression tests for the legacy MeetGeek recovery upload alias."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


def _load_legacy_cli():
    path = Path("plugins/h2t-ops/skills/meetgeek/scripts/meetgeek_cli.py")
    spec = importlib.util.spec_from_file_location("legacy_meetgeek_cli_for_tests", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_upload_download_url_delegates_to_h2t_ops_submit_url(monkeypatch, capsys):
    mod = _load_legacy_cli()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "ok": True,
                "provider": "meetgeek",
                "result": {"message": "Processing"},
            }),
            stderr="",
        )

    monkeypatch.setenv("H2T_OPS", "h2t-ops-test")
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    code = mod.cmd_upload(SimpleNamespace(
        download_url="https://example.com/recording.mp4",
        title="Interview",
        language="ru",
        from_file=None,
    ))

    assert code == 0
    assert calls[0][0] == [
        "h2t-ops-test",
        "meetgeek",
        "submit-url",
        "https://example.com/recording.mp4",
        "--json",
        "--title",
        "Interview",
        "--language-code",
        "ru",
    ]
    out = json.loads(capsys.readouterr().out)
    assert out == {"status": "submitted", "response": {"message": "Processing"}}
