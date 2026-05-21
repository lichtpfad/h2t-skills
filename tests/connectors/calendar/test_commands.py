"""Tests for h2t_ops.connectors.calendar.commands — registration, dispatch, shim."""
from __future__ import annotations

import argparse
from types import SimpleNamespace

import pytest

from h2t_ops.core.errors import ConfigError, UsageError


def _build_parser():
    from h2t_ops.connectors.calendar.commands import register
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="provider")
    register(sub)
    return parser


def test_register_adds_5_calendar_subcommands():
    parser = _build_parser()
    for cmd, extra in [
        ("list", []),
        ("search", ["q"]),
        ("get", ["evtid"]),
        ("create", ["Title", "2026-04-06", "14:00"]),
        ("delete", ["evtid"]),
    ]:
        ns = parser.parse_args(["calendar", cmd, *extra])
        assert ns.calendar_cmd == cmd


def test_register_has_format_and_json_flags():
    parser = _build_parser()
    ns = parser.parse_args(["calendar", "list", "--json"])
    assert ns.as_json is True
    ns2 = parser.parse_args(["calendar", "list", "--format", "md"])
    assert ns2.fmt == "md"


def test_list_parser_accepts_date_window_busy_only_tz_and_max():
    parser = _build_parser()
    ns = parser.parse_args([
        "calendar", "list",
        "--from", "2026-05-01",
        "--to", "2026-05-21",
        "--tz", "Asia/Jerusalem",
        "--max", "250",
        "--busy-only",
        "--json",
    ])
    assert ns.from_date == "2026-05-01"
    assert ns.to_date == "2026-05-21"
    assert ns.tz == "Asia/Jerusalem"
    assert ns.max == 250
    assert ns.busy_only is True


def test_date_window_bounds_are_inclusive_user_dates():
    from h2t_ops.connectors.calendar.commands import _date_window_bounds

    time_min, time_max = _date_window_bounds(
        "2026-05-01",
        "2026-05-21",
        "Asia/Jerusalem",
    )

    assert time_min == "2026-05-01T00:00:00+03:00"
    assert time_max == "2026-05-22T00:00:00+03:00"


def test_calendar_timezone_resolution_prefers_arg_then_env(monkeypatch):
    from h2t_ops.connectors.calendar.commands import _resolve_query_tz

    monkeypatch.setenv("H2T_CALENDAR_TZ", "UTC")

    assert _resolve_query_tz("Asia/Jerusalem") == "Asia/Jerusalem"
    assert _resolve_query_tz(None) == "UTC"
    monkeypatch.delenv("H2T_CALENDAR_TZ")
    assert _resolve_query_tz(None) == "Asia/Jerusalem"


def test_importing_commands_does_not_import_client(monkeypatch):
    import builtins
    real = builtins.__import__
    seen = []
    def guard(n, *a, **k):
        seen.append(n)
        return real(n, *a, **k)
    builtins.__import__ = guard
    try:
        import importlib
        import h2t_ops.connectors.calendar.commands as cmds
        importlib.reload(cmds)
    finally:
        builtins.__import__ = real
    assert not any(s.endswith("calendar.client") for s in seen), (
        f"commands.py must not import client at module scope. Seen: {seen}"
    )


def test_list_dispatch_json_returns_rows(monkeypatch):
    """Happy-path dispatch — stub CalendarClient, assert JSON path returns rows."""
    import sys
    import h2t_ops.connectors.calendar.client as client_mod
    # Sync past the sys.modules-vs-package-attr desync that T2's
    # test_init_with_missing_google_libs_raises_configerror can create: after
    # that test restores sys.modules, `import ... as client_mod` resolves via
    # the parent package attr (new module) while `from ... import CalendarClient`
    # in run() reads sys.modules (original module). Both paths must patch the
    # same object — force client_mod to the sys.modules reference.
    client_mod = sys.modules.get(
        "h2t_ops.connectors.calendar.client", client_mod
    )
    from h2t_ops.connectors.calendar import commands as cmds_mod

    class _Stub:
        def list_events(self, **kwargs):
            assert kwargs["days"] == 1
            assert kwargs["max_results"] == 20
            assert kwargs["time_min"] is None
            assert kwargs["time_max"] is None
            return [{"id": "evt1", "summary": "M"}]
    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    args = SimpleNamespace(
        calendar_cmd="list", days=1, max=20, as_json=True, fmt="human",
    )
    out = cmds_mod.run(args)
    assert out == [{"id": "evt1", "summary": "M"}]


def test_list_dispatch_date_window_passes_explicit_bounds(monkeypatch):
    import sys
    import h2t_ops.connectors.calendar.client as client_mod
    client_mod = sys.modules.get(
        "h2t_ops.connectors.calendar.client", client_mod
    )
    from h2t_ops.connectors.calendar import commands as cmds_mod

    calls = []

    class _Stub:
        def list_events(self, **kwargs):
            calls.append(kwargs)
            return []

    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    args = SimpleNamespace(
        calendar_cmd="list",
        days=7,
        from_date="2026-05-01",
        to_date="2026-05-21",
        tz="Asia/Jerusalem",
        max=250,
        busy_only=True,
        as_json=True,
        fmt="human",
    )

    out = cmds_mod.run(args)

    assert out == []
    assert calls == [{
        "days": 7,
        "max_results": 250,
        "time_min": "2026-05-01T00:00:00+03:00",
        "time_max": "2026-05-22T00:00:00+03:00",
        "tz": "Asia/Jerusalem",
        "busy_only": True,
    }]


def test_list_dispatch_rejects_partial_date_window(monkeypatch):
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod

    monkeypatch.setattr(client_mod, "CalendarClient", lambda: object())
    args = SimpleNamespace(
        calendar_cmd="list",
        days=1,
        from_date="2026-05-01",
        to_date=None,
        tz=None,
        max=250,
        busy_only=False,
        as_json=True,
        fmt="human",
    )

    with pytest.raises(UsageError):
        cmds_mod.run(args)


def test_delete_dispatch_requires_confirm(monkeypatch):
    """delete without --confirm raises UsageError (parity with legacy)."""
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod
    monkeypatch.setattr(client_mod, "CalendarClient", lambda: object())
    args = SimpleNamespace(
        calendar_cmd="delete", event_id="evt1", confirm=False,
        as_json=True, fmt="human",
    )
    with pytest.raises(UsageError):
        cmds_mod.run(args)


def test_unknown_subcommand_raises_usageerror(monkeypatch):
    import h2t_ops.connectors.calendar.client as client_mod
    from h2t_ops.connectors.calendar import commands as cmds_mod
    monkeypatch.setattr(client_mod, "CalendarClient", lambda: object())
    args = SimpleNamespace(
        calendar_cmd="bogus", as_json=False, fmt="human",
    )
    with pytest.raises(UsageError):
        cmds_mod.run(args)


# ---------- Missing-scopes upfront detection (NEW behavior, design §"Auth model") ----------

def test_missing_scopes_surfaces_as_configerror_with_neutral_hint(tmp_path, monkeypatch):
    """Calendar client construction with a Gmail-only token must raise
    ConfigError with the neutral bootstrap hint — not the legacy 403-at-call.
    """
    from pathlib import Path
    import json
    shared = tmp_path / ".config" / "google-calendar-mcp" / "tokens.json"
    shared.parent.mkdir(parents=True)
    shared.write_text(json.dumps({
        "client_id": "id.apps.googleusercontent.com",
        "client_secret": "secret",
        "token_uri": "https://oauth2.googleapis.com/token",
        "token": "access_t",
        "refresh_token": "refresh_t",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
    }))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    from h2t_ops.connectors.calendar.client import CalendarClient
    with pytest.raises(ConfigError) as ei:
        CalendarClient()
    assert "scope" in str(ei.value).lower() or "scope" in (ei.value.hint or "").lower()
    # Hint stays neutral — no legacy-skill name.
    assert "gmail_cli" not in (ei.value.hint or "")
    assert "gmail skill" not in (ei.value.hint or "")
    assert "Google OAuth" in (ei.value.hint or "")


# ---------- Ingest calendar shim (mirror Gmail §10.2) ----------

def test_ingest_calendar_shim_warns_on_human(monkeypatch, capsys):
    from h2t_ops.connectors.calendar import commands as cmds_mod
    import h2t_ops.connectors.calendar.client as client_mod
    class _Stub:
        def list_events(self, **_): return []
    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    from h2t_ops.cli import dispatch
    rc = dispatch(["ingest", "calendar", "list", "--days", "1"])
    err = capsys.readouterr().err
    assert "deprecated" in err.lower()
    assert "h2t-ops calendar" in err.lower()
    assert rc == 0


def test_ingest_calendar_shim_silent_on_json(monkeypatch, capsys):
    from h2t_ops.connectors.calendar import commands as cmds_mod
    import h2t_ops.connectors.calendar.client as client_mod
    class _Stub:
        def list_events(self, **_): return []
    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    from h2t_ops.cli import dispatch
    rc = dispatch(["ingest", "calendar", "list", "--format", "json"])
    err = capsys.readouterr().err
    assert "deprecated" not in err.lower()
    assert rc == 0
