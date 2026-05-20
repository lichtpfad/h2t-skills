"""Tests for h2t_ops.connectors.meetgeek.commands."""
from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from h2t_ops.core.errors import ConfigError, UsageError


def _build_parser():
    from h2t_ops.connectors.meetgeek.commands import register
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="provider")
    register(sub)
    return parser


# ─── Registration ─────────────────────────────────────────────────────────────

def test_register_creates_subparsers_for_ten_verbs():
    parser = _build_parser()
    for verb, extra in [
        ("auth-check", []),
        ("teams", []),
        ("list", []),
        ("get", ["m1"]),
        ("transcript", ["m1"]),
        ("summary", ["m1"]),
        ("highlights", ["m1"]),
        ("insights", ["m1"]),
        ("download-url", ["m1"]),
        ("submit-url", ["https://example.com/f.mp4"]),
    ]:
        ns = parser.parse_args(["meetgeek", verb, *extra])
        assert ns.meetgeek_cmd == verb, f"verb {verb!r} not registered"


def test_json_flag_available_on_all_verbs():
    parser = _build_parser()
    for verb, extra in [
        ("list", []),
        ("get", ["m1"]),
        ("transcript", ["m1"]),
        ("teams", []),
        ("download-url", ["m1"]),
        ("submit-url", ["https://example.com/f.mp4"]),
    ]:
        ns = parser.parse_args(["meetgeek", verb, "--json", *extra])
        assert ns.as_json is True, f"--json missing from {verb!r}"


def test_transcript_summary_highlights_insights_have_format_flag():
    parser = _build_parser()
    for verb in ("transcript", "summary", "highlights", "insights"):
        ns = parser.parse_args(["meetgeek", verb, "--format", "md", "m1"])
        assert ns.fmt == "md"
        ns2 = parser.parse_args(["meetgeek", verb, "--format", "json", "m1"])
        assert ns2.fmt == "json"


def test_submit_url_requires_url_positional():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["meetgeek", "submit-url"])


# ─── Client lazily imported ────────────────────────────────────────────────────

def test_commands_module_does_not_import_client_at_module_scope():
    src = Path("h2t_ops/connectors/meetgeek/commands.py").read_text(encoding="utf-8")
    for i, line in enumerate(src.splitlines(), 1):
        stripped = line.lstrip()
        if "meetgeek.client" in stripped or "MeetGeekClient" in stripped:
            assert line[0] == " ", (
                f"line {i}: MeetGeekClient must not be imported at module scope: {line!r}"
            )


# ─── Dispatch — happy path ────────────────────────────────────────────────────

def _stub_client(monkeypatch, methods: dict):
    """Patch MeetGeekClient constructor to return a stub."""
    import h2t_ops.connectors.meetgeek.client as client_mod
    stub = MagicMock()
    for name, ret in methods.items():
        getattr(stub, name).return_value = ret
    monkeypatch.setattr(client_mod, "MeetGeekClient", lambda: stub)
    return stub


def test_list_dispatch_returns_rows(monkeypatch):
    stub = _stub_client(monkeypatch, {"list_meetings": {"rows": [{"meeting_id": "m1"}], "next_cursor": None}})
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(
        meetgeek_cmd="list", limit=None, cursor=None,
        from_date=None, to_date=None, as_json=True, fmt="human",
    )
    result = cmds.run(args)
    assert result["rows"][0]["meeting_id"] == "m1"


def test_get_dispatch_returns_meeting(monkeypatch):
    stub = _stub_client(monkeypatch, {"get_meeting": {"meeting_id": "m1", "title": "Test"}})
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(meetgeek_cmd="get", meeting_id="m1", as_json=True, fmt="human")
    result = cmds.run(args)
    assert result["meeting_id"] == "m1"


def test_transcript_dispatch_json_format(monkeypatch):
    stub = _stub_client(monkeypatch, {"get_transcript": {"sentences": [{"text": "Hi"}]}})
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(meetgeek_cmd="transcript", meeting_id="m1", fmt="json", as_json=False)
    result = cmds.run(args)
    assert result["sentences"][0]["text"] == "Hi"


def test_transcript_dispatch_md_format_returns_string(monkeypatch):
    stub = _stub_client(monkeypatch, {
        "get_meeting": {"meeting_id": "m1", "title": "T"},
        "get_transcript": {"sentences": [{"speaker": "A", "text": "Hello", "timestamp": 0}]},
    })
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(meetgeek_cmd="transcript", meeting_id="m1", fmt="md", as_json=False)
    result = cmds.run(args)
    assert isinstance(result, str)
    assert "---" in result  # frontmatter present
    assert "Hello" in result


def test_download_url_dispatch_returns_envelope(monkeypatch):
    stub = _stub_client(monkeypatch, {
        "get_download_url": {"meeting_id": "m1", "download_url": "https://example.com/f.mp4"},
    })
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(meetgeek_cmd="download-url", meeting_id="m1", as_json=True, fmt="human")
    result = cmds.run(args)
    assert result["download_url"] == "https://example.com/f.mp4"


def test_submit_url_dispatch_calls_submit_url(monkeypatch):
    stub = _stub_client(monkeypatch, {"submit_url": {"message": "Processing"}})
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(
        meetgeek_cmd="submit-url",
        download_url="https://example.com/f.mp4",
        title=None, language_code=None, template_name=None,
        as_json=True, fmt="human",
    )
    result = cmds.run(args)
    stub.submit_url.assert_called_once_with(
        "https://example.com/f.mp4",
        title=None, language_code=None, template_name=None,
    )
    assert result["message"] == "Processing"


def test_auth_check_dispatch_returns_ok(monkeypatch):
    stub = _stub_client(monkeypatch, {"auth_check": True})
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(meetgeek_cmd="auth-check", as_json=False, fmt="human")
    result = cmds.run(args)
    assert result is True or result == {"status": "ok"}


def test_teams_dispatch_returns_teams(monkeypatch):
    stub = _stub_client(monkeypatch, {"get_teams": {"teams": []}})
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(meetgeek_cmd="teams", as_json=True, fmt="human")
    result = cmds.run(args)
    assert "teams" in result


def test_unknown_subcommand_raises_usageerror(monkeypatch):
    _stub_client(monkeypatch, {})
    from h2t_ops.connectors.meetgeek import commands as cmds
    args = SimpleNamespace(meetgeek_cmd="bogus", as_json=False, fmt="human")
    with pytest.raises(UsageError):
        cmds.run(args)


# ─── Formatter helpers ────────────────────────────────────────────────────────

def test_normalize_meeting_prefers_timestamp_start_utc():
    from h2t_ops.connectors.meetgeek.commands import _normalize_meeting
    m = {"id": "m1", "title": "T", "timestamp_start_utc": "2026-05-01T10:00:00Z", "start_time": "old"}
    result = _normalize_meeting(m)
    assert result["timestamp_start_utc"] == "2026-05-01T10:00:00Z"
    assert result["date"] == "2026-05-01"


def test_normalize_meeting_falls_back_to_start_time():
    from h2t_ops.connectors.meetgeek.commands import _normalize_meeting
    m = {"meeting_id": "m2", "title": "T", "start_time": "2026-04-01T09:00:00Z"}
    result = _normalize_meeting(m)
    assert result["meeting_id"] == "m2"
    assert result["timestamp_start_utc"] == "2026-04-01T09:00:00Z"
    assert result["date"] == "2026-04-01"


def test_normalize_meeting_supports_id_alias():
    from h2t_ops.connectors.meetgeek.commands import _normalize_meeting
    m = {"id": "m3", "title": "T"}
    result = _normalize_meeting(m)
    assert result["meeting_id"] == "m3"
