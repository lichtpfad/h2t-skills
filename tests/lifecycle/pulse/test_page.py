"""The browser page: one static file over the same rows as the terminal view."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from h2t_ops.lifecycle.pulse import cli, page, view
from tests.lifecycle.pulse.test_view import _branch, _rec


@pytest.fixture(autouse=True)
def _machine(monkeypatch):
    monkeypatch.setenv("H2T_MACHINE_NAME", "test-machine")


def _data(html: str) -> dict:
    block = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)
    assert block is not None
    return json.loads(block.group(1))


def _build(tmp_path: Path) -> str:
    return page.build(tmp_path / "out" / "sessions.html").read_text(encoding="utf-8")


def test_page_embeds_rows_and_resume_commands(tmp_path):
    _rec("s-claude", tmp_path)
    _rec("s-codex", tmp_path, tool="codex", started_at="2026-10-11T10:00:00Z")
    _rec("s-unknown", tmp_path, origin="unknown")
    _branch(str(tmp_path / "r1"), "b1", issues=json.dumps({"7": "unknown"}))
    data = _data(_build(tmp_path))
    by_id = {r["session_id"]: r for r in data["rows"]}
    assert set(by_id) == {"s-claude", "s-codex", "s-unknown"}
    cwd = str(tmp_path / "r1")
    assert by_id["s-claude"]["resume"] == view.resume_command("claude", "s-claude", cwd)
    assert by_id["s-codex"]["resume"] == view.resume_command("codex", "s-codex", cwd)
    assert by_id["s-claude"]["verdict"] == "ждёт PR"
    assert by_id["s-claude"]["issues"] == "#7 ?"
    assert by_id["s-unknown"]["hidden"] is True and by_id["s-claude"]["hidden"] is False
    assert data["footer"] == view.footer()


def test_page_has_no_external_urls(tmp_path):
    _rec("s1", tmp_path)
    html = _build(tmp_path)
    assert "http://" not in html and "https://" not in html


def test_page_escapes_summary_html(tmp_path):
    _rec("s1", tmp_path, summary="</script><script>alert(1)</script>")
    html = _build(tmp_path)
    assert html.count("</script>") == 2          # the data block and the code block, nothing else
    assert "<script>alert" not in html
    assert _data(html)["rows"][0]["summary"] == "</script><script>alert(1)</script>"


def test_sessions_page_builds_without_opening(tmp_path, capsys):
    _rec("s1", tmp_path)
    out = tmp_path / "p.html"
    assert cli.main(["page", "--no-open", "--out", str(out)]) == 0
    assert out.is_file() and str(out) in capsys.readouterr().out
