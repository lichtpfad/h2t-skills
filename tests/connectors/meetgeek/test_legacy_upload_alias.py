"""Regression tests for the legacy MeetGeek recovery upload alias."""
from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

from h2t_ops.connectors.meetgeek import pipeline


def test_upload_download_url_delegates_to_h2t_ops_submit_url(monkeypatch, capsys):
    # meetgeek_cli.py's cmd_upload is pipeline.upload since Task 12: same delegation.
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
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = pipeline.upload(SimpleNamespace(
        download_url="https://example.com/recording.mp4",
        title="Interview",
        language="ru",
        from_file=None,
    ))

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
    assert result == {"status": "submitted", "response": {"message": "Processing"}}
