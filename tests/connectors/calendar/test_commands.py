"""Tests for h2t_ops.connectors.calendar.commands — registration, dispatch, shim."""
from __future__ import annotations

import argparse
from types import SimpleNamespace

import pytest

from h2t_ops.core.errors import ConfigError, UsageError


def _patch_calendar_client(monkeypatch, factory):
    """Patch the exact calendar.client module object used by commands.run().

    Some tests temporarily manipulate sys.modules for import-laziness checks.
    After that, Python can leave the parent package attribute and sys.modules
    pointing at different module objects. commands.run() imports from
    sys.modules, so tests must patch that object rather than whichever object
    `import h2t_ops.connectors.calendar.client` happens to return.
    """
    import importlib
    import sys

    module_name = "h2t_ops.connectors.calendar.client"
    client_mod = importlib.import_module(module_name)
    client_mod = sys.modules.get(module_name, client_mod)
    monkeypatch.setattr(client_mod, "CalendarClient", factory)


def _build_parser():
    from h2t_ops.connectors.calendar.commands import register
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="provider")
    register(sub)
    return parser


def test_register_adds_calendar_subcommands():
    parser = _build_parser()
    for cmd, extra in [
        ("calendars", []),
        ("list", []),
        ("search", ["q"]),
        ("get", ["evtid"]),
        ("create", ["Title", "2026-04-06", "14:00"]),
        ("update", ["evtid", "--summary", "New"]),
        ("delete", ["evtid"]),
        ("freebusy", ["--from", "2026-05-01", "--to", "2026-05-02"]),
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
    from h2t_ops.connectors.calendar import commands as cmds_mod

    class _Stub:
        def list_events(self, **kwargs):
            assert kwargs["days"] == 1
            assert kwargs["max_results"] == 20
            assert kwargs["time_min"] is None
            assert kwargs["time_max"] is None
            return [{"id": "evt1", "summary": "M"}]
    _patch_calendar_client(monkeypatch, lambda: _Stub())
    args = SimpleNamespace(
        calendar_cmd="list", days=1, max=20, calendar_id="primary",
        from_date=None, to_date=None, tz=None, busy_only=False,
        as_json=True, fmt="human",
    )
    out = cmds_mod.run(args)
    assert out == [{"id": "evt1", "summary": "M"}]


def test_list_dispatch_date_window_passes_explicit_bounds(monkeypatch):
    from h2t_ops.connectors.calendar import commands as cmds_mod

    calls = []

    class _Stub:
        def list_events(self, **kwargs):
            calls.append(kwargs)
            return []

    _patch_calendar_client(monkeypatch, lambda: _Stub())
    args = SimpleNamespace(
        calendar_cmd="list",
        days=7,
        from_date="2026-05-01",
        to_date="2026-05-21",
        tz="Asia/Jerusalem",
        max=250,
        calendar_id="primary",
        busy_only=True,
        as_json=True,
        fmt="human",
    )

    out = cmds_mod.run(args)

    assert out == []
    assert calls == [{
        "days": 7,
        "max_results": 250,
        "calendar_id": "primary",
        "time_min": "2026-05-01T00:00:00+03:00",
        "time_max": "2026-05-22T00:00:00+03:00",
        "tz": "Asia/Jerusalem",
        "busy_only": True,
    }]


def test_list_dispatch_rejects_partial_date_window(monkeypatch):
    from h2t_ops.connectors.calendar import commands as cmds_mod

    _patch_calendar_client(monkeypatch, lambda: object())
    args = SimpleNamespace(
        calendar_cmd="list",
        days=1,
        from_date="2026-05-01",
        to_date=None,
        tz=None,
        max=250,
        calendar_id="primary",
        busy_only=False,
        as_json=True,
        fmt="human",
    )

    with pytest.raises(UsageError):
        cmds_mod.run(args)


def test_delete_dispatch_requires_confirm(monkeypatch):
    """delete without --confirm raises UsageError (parity with legacy)."""
    from h2t_ops.connectors.calendar import commands as cmds_mod
    _patch_calendar_client(monkeypatch, lambda: object())
    args = SimpleNamespace(
        calendar_cmd="delete", event_id="evt1", confirm=False,
        as_json=True, fmt="human",
    )
    with pytest.raises(UsageError):
        cmds_mod.run(args)


def test_unknown_subcommand_raises_usageerror(monkeypatch):
    from h2t_ops.connectors.calendar import commands as cmds_mod
    _patch_calendar_client(monkeypatch, lambda: object())
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
    class _Stub:
        def list_events(self, **_): return []
    _patch_calendar_client(monkeypatch, lambda: _Stub())
    from h2t_ops.cli import dispatch
    rc = dispatch(["ingest", "calendar", "list", "--days", "1"])
    err = capsys.readouterr().err
    assert "deprecated" in err.lower()
    assert "h2t-ops calendar" in err.lower()
    assert rc == 0


def test_ingest_calendar_shim_silent_on_json(monkeypatch, capsys):
    class _Stub:
        def list_events(self, **_): return []
    _patch_calendar_client(monkeypatch, lambda: _Stub())
    from h2t_ops.cli import dispatch
    rc = dispatch(["ingest", "calendar", "list", "--format", "json"])
    err = capsys.readouterr().err
    assert "deprecated" not in err.lower()
    assert rc == 0


def test_calendar_provider_feature_parsers():
    parser = _build_parser()
    assert parser.parse_args(["calendar", "calendars", "--json"]).calendar_cmd == "calendars"

    ns = parser.parse_args([
        "calendar", "list", "--calendar-id", "team@example.com", "--json",
    ])
    assert ns.calendar_id == "team@example.com"

    ns = parser.parse_args([
        "calendar", "create", "Holiday", "2026-05-25", "--all-day",
        "--calendar-id", "team@example.com", "--duration", "45",
        "--location", "Berlin", "--meet", "--rrule", "RRULE:FREQ=WEEKLY;COUNT=2",
        "--reminder-minutes", "10,60", "--json",
    ])
    assert ns.time is None
    assert ns.all_day is True
    assert ns.calendar_id == "team@example.com"
    assert ns.duration_min == 45
    assert ns.location == "Berlin"
    assert ns.meet is True

    ns = parser.parse_args([
        "calendar", "update", "evt",
        "--replace-attendees", "a@example.com,b@example.com",
        "--replace-rrule", "RRULE:FREQ=DAILY;COUNT=2",
        "--replace-reminders", "5,30",
        "--json",
    ])
    assert ns.replace_attendees == "a@example.com,b@example.com"
    assert ns.replace_rrule == "RRULE:FREQ=DAILY;COUNT=2"
    assert ns.replace_reminders == "5,30"

    ns = parser.parse_args([
        "calendar", "freebusy", "--from", "2026-05-22", "--to", "2026-05-23",
        "--calendar-id", "primary", "--calendar-id", "team@example.com", "--json",
    ])
    assert ns.calendar_id == ["primary", "team@example.com"]


def test_calendars_dispatch(monkeypatch):
    from h2t_ops.connectors.calendar import commands as cmds_mod

    class _Stub:
        def list_calendars(self):
            return {"kind": "calendar_list/v1", "calendars": []}

    _patch_calendar_client(monkeypatch, lambda: _Stub())

    out = cmds_mod.run(SimpleNamespace(calendar_cmd="calendars", as_json=True, fmt="human"))

    assert out["kind"] == "calendar_list/v1"


def test_create_dispatch_passes_provider_features(monkeypatch):
    from h2t_ops.connectors.calendar import commands as cmds_mod
    calls = []

    class _Stub:
        def create_event(self, *args, **kwargs):
            calls.append((args, kwargs))
            return {"kind": "calendar_event/v1", "id": "evt"}

    _patch_calendar_client(monkeypatch, lambda: _Stub())

    cmds_mod.run(SimpleNamespace(
        calendar_cmd="create",
        summary="S",
        date="2026-05-25",
        time="14:00",
        duration_min=45,
        all_day=False,
        description="D",
        attendees="a@example.com",
        location="Room A",
        calendar_id="team@example.com",
        meet=True,
        rrule="RRULE:FREQ=WEEKLY;COUNT=2",
        reminder_minutes="10,60",
        tz="Asia/Jerusalem",
        as_json=True,
        fmt="human",
    ))

    kwargs = calls[0][1]
    assert kwargs["calendar_id"] == "team@example.com"
    assert kwargs["location"] == "Room A"
    assert kwargs["meet"] is True
    assert kwargs["rrule"] == "RRULE:FREQ=WEEKLY;COUNT=2"
    assert kwargs["reminder_minutes"] == [10, 60]


def test_create_dispatch_validates_all_day_and_timed_forms(monkeypatch):
    from h2t_ops.connectors.calendar import commands as cmds_mod

    _patch_calendar_client(monkeypatch, lambda: object())

    with pytest.raises(UsageError):
        cmds_mod.run(SimpleNamespace(
            calendar_cmd="create", summary="S", date="2026-05-25", time=None,
            all_day=False, duration_min=60, description=None, attendees=None,
            location=None, calendar_id="primary", meet=False, rrule=None,
            reminder_minutes=None, tz="Asia/Jerusalem", as_json=True, fmt="human",
        ))

    with pytest.raises(UsageError):
        cmds_mod.run(SimpleNamespace(
            calendar_cmd="create", summary="S", date="2026-05-25", time="14:00",
            all_day=True, duration_min=60, description=None, attendees=None,
            location=None, calendar_id="primary", meet=False, rrule=None,
            reminder_minutes=None, tz="Asia/Jerusalem", as_json=True, fmt="human",
        ))


def test_update_dispatch_passes_replace_flags(monkeypatch):
    from h2t_ops.connectors.calendar import commands as cmds_mod
    calls = []

    class _Stub:
        def patch_event(self, *args, **kwargs):
            calls.append((args, kwargs))
            return {"kind": "calendar_event/v1", "id": "evt"}

    _patch_calendar_client(monkeypatch, lambda: _Stub())

    out = cmds_mod.run(SimpleNamespace(
        calendar_cmd="update",
        event_id="evt",
        calendar_id="primary",
        summary="New",
        date="2026-05-25",
        time="14:00",
        duration_min=30,
        all_day=None,
        description=None,
        location=None,
        replace_attendees="a@example.com,b@example.com",
        meet=True,
        replace_rrule="RRULE:FREQ=DAILY;COUNT=2",
        replace_reminders="10",
        clear_reminders=False,
        tz="Asia/Jerusalem",
        as_json=True,
        fmt="human",
    ))

    assert out["id"] == "evt"
    kwargs = calls[0][1]
    assert kwargs["replace_attendees"] == "a@example.com,b@example.com"
    assert kwargs["replace_rrule"] == "RRULE:FREQ=DAILY;COUNT=2"
    assert kwargs["replace_reminder_minutes"] == [10]


def test_freebusy_dispatch_uses_date_window(monkeypatch):
    from h2t_ops.connectors.calendar import commands as cmds_mod
    calls = []

    class _Stub:
        def freebusy(self, time_min, time_max, *, calendar_ids, tz=None):
            calls.append((time_min, time_max, calendar_ids, tz))
            return {"kind": "calendar_freebusy/v1", "calendars": [], "has_errors": False}

    _patch_calendar_client(monkeypatch, lambda: _Stub())

    out = cmds_mod.run(SimpleNamespace(
        calendar_cmd="freebusy",
        from_date="2026-05-22",
        to_date="2026-05-23",
        tz="Asia/Jerusalem",
        calendar_id=["primary", "team@example.com"],
        as_json=True,
        fmt="human",
    ))

    assert out["kind"] == "calendar_freebusy/v1"
    assert calls[0] == (
        "2026-05-22T00:00:00+03:00",
        "2026-05-24T00:00:00+03:00",
        ["primary", "team@example.com"],
        "Asia/Jerusalem",
    )
