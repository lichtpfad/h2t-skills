"""Tests for h2t_ops.connectors.calendar.client.CalendarClient.

API logic mirrors lib/clients/calendar.py; only side effects and error types
differ per the connector standard (spec §10).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from h2t_ops.core.errors import (
    AuthError, ConfigError, NetworkError, NotFoundError, ProviderError,
)


@pytest.fixture
def client_obj():
    """Construct a CalendarClient WITHOUT running __init__ (no network / SDK)."""
    from h2t_ops.connectors.calendar.client import CalendarClient
    c = object.__new__(CalendarClient)
    c.service = MagicMock()
    return c


# ---------- _normalize_event — migrated verbatim from tests/clients/test_calendar.py ----------

def test_normalize_timed_event(client_obj):
    event = {
        "id": "evt1",
        "summary": "Meeting",
        "start": {"dateTime": "2026-04-06T14:00:00+03:00"},
        "end": {"dateTime": "2026-04-06T15:00:00+03:00"},
        "htmlLink": "https://cal.google.com/...",
    }
    result = client_obj._normalize_event(event)
    assert result["summary"] == "Meeting"
    assert result["time"] == "14:00"
    assert result["duration_min"] == 60
    assert result["date"] == "2026-04-06"
    assert result["id"] == "evt1"


def test_normalize_all_day_event(client_obj):
    event = {
        "id": "evt2",
        "summary": "Holiday",
        "start": {"date": "2026-04-07"},
        "end": {"date": "2026-04-08"},
    }
    result = client_obj._normalize_event(event)
    assert result["time"] == "весь день"
    assert result["duration_min"] is None
    assert result["date"] == "2026-04-07"


def test_normalize_missing_location(client_obj):
    event = {
        "id": "evt3",
        "summary": "No Location",
        "start": {"date": "2026-04-06"},
        "end": {"date": "2026-04-07"},
    }
    result = client_obj._normalize_event(event)
    assert result["location"] == ""


def test_normalize_description_truncated(client_obj):
    event = {
        "id": "evt4",
        "summary": "With Desc",
        "start": {"date": "2026-04-06"},
        "end": {"date": "2026-04-07"},
        "description": "A" * 300,
    }
    result = client_obj._normalize_event(event)
    assert len(result["description"]) == 200


# ---------- typed-error mapping (mirror Gmail _map_http_error shape) ----------

def test_map_http_error_401_to_autherror(client_obj):
    from h2t_ops.connectors.calendar.client import _map_http_error
    e = MagicMock()
    e.resp = SimpleNamespace(status=401)
    e.reason = "Unauthorized"
    err = _map_http_error(e, op="list events")
    assert isinstance(err, AuthError)


def test_map_http_error_404_to_notfounderror(client_obj):
    from h2t_ops.connectors.calendar.client import _map_http_error
    e = MagicMock()
    e.resp = SimpleNamespace(status=404)
    e.reason = "Not Found"
    err = _map_http_error(e, op="get event")
    assert isinstance(err, NotFoundError)


def test_map_http_error_500_to_providererror(client_obj):
    from h2t_ops.connectors.calendar.client import _map_http_error
    e = MagicMock()
    e.resp = SimpleNamespace(status=500)
    e.reason = "Server Error"
    err = _map_http_error(e, op="list events")
    assert isinstance(err, ProviderError)


# ---------- happy-path read (stub the google service) ----------

def test_list_events_happy_path_returns_normalized_list(client_obj):
    client_obj.service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "evt1",
                "summary": "M",
                "start": {"dateTime": "2026-04-06T14:00:00+03:00"},
                "end": {"dateTime": "2026-04-06T15:00:00+03:00"},
            }
        ]
    }
    rows = client_obj.list_events(days=1, max_results=1)
    assert isinstance(rows, list) and len(rows) == 1
    assert rows[0]["summary"] == "M"
    assert rows[0]["time"] == "14:00"


def test_list_events_accepts_explicit_time_bounds_and_timezone(client_obj):
    client_obj.service.events.return_value.list.return_value.execute.return_value = {
        "items": []
    }

    rows = client_obj.list_events(
        max_results=250,
        time_min="2026-05-01T00:00:00+03:00",
        time_max="2026-05-22T00:00:00+03:00",
        tz="Asia/Jerusalem",
    )

    assert rows == []
    client_obj.service.events.return_value.list.assert_called_once_with(
        calendarId="primary",
        timeMin="2026-05-01T00:00:00+03:00",
        timeMax="2026-05-22T00:00:00+03:00",
        maxResults=250,
        singleEvents=True,
        orderBy="startTime",
        timeZone="Asia/Jerusalem",
    )


def test_list_events_busy_only_filters_transparent_before_normalization(client_obj):
    client_obj.service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "busy",
                "summary": "Busy",
                "start": {"dateTime": "2026-05-01T10:00:00+03:00"},
                "end": {"dateTime": "2026-05-01T11:00:00+03:00"},
            },
            {
                "id": "free",
                "summary": "Free",
                "transparency": "transparent",
                "start": {"dateTime": "2026-05-01T12:00:00+03:00"},
                "end": {"dateTime": "2026-05-01T13:00:00+03:00"},
            },
        ]
    }

    rows = client_obj.list_events(busy_only=True)

    assert [row["id"] for row in rows] == ["busy"]


# ---------- missing-libs / missing-creds path (re-checked via google_auth) ----------

def test_init_with_missing_google_libs_raises_configerror(monkeypatch):
    """If google_auth._import_google fails, surfacing as ConfigError, the
    CalendarClient constructor must propagate the typed error (not crash).

    Mirrors Gmail test approach: guard builtins.__import__ to block google libs.
    """
    import builtins
    import sys
    monkeypatch.delitem(sys.modules, "h2t_ops.connectors.calendar.client", raising=False)
    real = builtins.__import__

    def guard(name, *a, **k):
        if name.startswith("google") or name == "googleapiclient":
            raise ImportError(f"No module named {name!r}")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", guard)
    from h2t_ops.connectors.calendar.client import CalendarClient
    with pytest.raises(ConfigError):
        CalendarClient()
