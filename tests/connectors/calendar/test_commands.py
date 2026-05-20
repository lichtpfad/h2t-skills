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
        def list_events(self, days=1, max_results=20):
            return [{"id": "evt1", "summary": "M"}]
    monkeypatch.setattr(client_mod, "CalendarClient", lambda: _Stub())
    args = SimpleNamespace(
        calendar_cmd="list", days=1, max=20, as_json=True, fmt="human",
    )
    out = cmds_mod.run(args)
    assert out == [{"id": "evt1", "summary": "M"}]


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
