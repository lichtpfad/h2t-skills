"""Tests for h2t_ops.connectors.calendar.client.CalendarClient.

The only CalendarClient there is: lib/clients/calendar.py, which this once
mirrored, was retired in #356.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from h2t_ops.core.errors import (
    AuthError, ConfigError, NetworkError, NotFoundError, ProviderError, UsageError,
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
    assert rows[0]["kind"] == "calendar_event/v1"
    assert rows[0]["calendar_id"] == "primary"


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


def test_list_calendars_normalizes_access_role(client_obj):
    client_obj.service.calendarList.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "primary",
                "summary": "Primary",
                "primary": True,
                "accessRole": "owner",
                "timeZone": "Asia/Jerusalem",
                "conferenceProperties": {"allowedConferenceSolutionTypes": ["hangoutsMeet"]},
            },
            {
                "id": "readonly@example.com",
                "summary": "Read Only",
                "accessRole": "reader",
            },
        ]
    }

    result = client_obj.list_calendars()

    assert result["kind"] == "calendar_list/v1"
    assert result["calendars"][0]["access_role"] == "owner"
    assert result["calendars"][0]["can_write"] is True
    assert result["calendars"][1]["can_write"] is False


def test_read_methods_accept_calendar_id(client_obj):
    client_obj.service.events.return_value.list.return_value.execute.return_value = {"items": []}

    client_obj.list_events(calendar_id="team@example.com")
    assert client_obj.service.events.return_value.list.call_args.kwargs["calendarId"] == "team@example.com"

    client_obj.search_events("q", calendar_id="team@example.com")
    assert client_obj.service.events.return_value.list.call_args.kwargs["calendarId"] == "team@example.com"

    client_obj.service.events.return_value.get.return_value.execute.return_value = {"id": "evt"}
    assert client_obj.get_event("evt", calendar_id="team@example.com") == {"id": "evt"}
    assert client_obj.service.events.return_value.get.call_args.kwargs["calendarId"] == "team@example.com"


def test_create_event_with_provider_features(client_obj, monkeypatch):
    import h2t_ops.connectors.calendar.client as cal_client

    monkeypatch.setattr(cal_client.uuid, "uuid4", lambda: "uuid-1")
    client_obj.service.events.return_value.insert.return_value.execute.return_value = {
        "id": "evt",
        "summary": "M",
        "start": {"dateTime": "2026-05-25T14:00:00+03:00"},
        "end": {"dateTime": "2026-05-25T15:00:00+03:00"},
        "hangoutLink": "https://meet.google.com/abc",
        "recurrence": ["RRULE:FREQ=WEEKLY;COUNT=2"],
        "attendees": [{"email": "a@example.com"}],
        "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 10}]},
    }

    result = client_obj.create_event(
        "M",
        "2026-05-25",
        "14:00",
        calendar_id="team@example.com",
        location="Room A",
        attendees="a@example.com,a@example.com",
        meet=True,
        rrule="RRULE:FREQ=WEEKLY;COUNT=2",
        reminder_minutes=[10],
    )

    kwargs = client_obj.service.events.return_value.insert.call_args.kwargs
    body = kwargs["body"]
    assert kwargs["calendarId"] == "team@example.com"
    assert kwargs["conferenceDataVersion"] == 1
    assert body["location"] == "Room A"
    assert body["conferenceData"]["createRequest"]["requestId"] == "uuid-1"
    assert body["recurrence"] == ["RRULE:FREQ=WEEKLY;COUNT=2"]
    assert body["attendees"] == [{"email": "a@example.com"}]
    assert body["reminders"]["overrides"] == [{"method": "popup", "minutes": 10}]
    assert result["meet_link"] == "https://meet.google.com/abc"
    assert result["calendar_id"] == "team@example.com"


def test_create_event_all_day_uses_date_fields(client_obj):
    client_obj.service.events.return_value.insert.return_value.execute.return_value = {
        "id": "ad",
        "summary": "Holiday",
        "start": {"date": "2026-05-25"},
        "end": {"date": "2026-05-26"},
    }

    result = client_obj.create_event("Holiday", "2026-05-25", None, all_day=True)

    body = client_obj.service.events.return_value.insert.call_args.kwargs["body"]
    assert body["start"] == {"date": "2026-05-25"}
    assert body["end"] == {"date": "2026-05-26"}
    assert "timeZone" not in body["start"]
    assert result["all_day"] is True


def test_create_event_rejects_invalid_inputs(client_obj):
    with pytest.raises(ValueError):
        client_obj.create_event("Holiday", "2026-05-25", "14:00", all_day=True)
    with pytest.raises(ValueError):
        client_obj.create_event("Meeting", "2026-05-25", None)
    with pytest.raises(ValueError):
        client_obj.create_event("R", "2026-05-25", "14:00", rrule="FREQ=WEEKLY")
    with pytest.raises(ValueError):
        client_obj.create_event("R", "2026-05-25", "14:00", reminder_minutes=[-1])


def test_patch_event_reschedule_replace_arrays_and_meet(client_obj, monkeypatch):
    import h2t_ops.connectors.calendar.client as cal_client

    monkeypatch.setattr(cal_client.uuid, "uuid4", lambda: "uuid-2")
    client_obj.service.events.return_value.patch.return_value.execute.return_value = {
        "id": "evt",
        "summary": "New",
        "start": {"dateTime": "2026-05-25T14:00:00+03:00"},
        "end": {"dateTime": "2026-05-25T14:30:00+03:00"},
    }

    client_obj.patch_event(
        "evt",
        summary="New",
        date="2026-05-25",
        time="14:00",
        duration_min=30,
        replace_attendees="a@example.com,b@example.com",
        meet=True,
        replace_rrule="RRULE:FREQ=DAILY;COUNT=2",
        replace_reminder_minutes=[10, 60],
    )

    kwargs = client_obj.service.events.return_value.patch.call_args.kwargs
    body = kwargs["body"]
    assert kwargs["calendarId"] == "primary"
    assert kwargs["eventId"] == "evt"
    assert kwargs["conferenceDataVersion"] == 1
    assert body["attendees"] == [{"email": "a@example.com"}, {"email": "b@example.com"}]
    assert body["conferenceData"]["createRequest"]["requestId"] == "uuid-2"
    assert body["recurrence"] == ["RRULE:FREQ=DAILY;COUNT=2"]
    assert body["reminders"]["overrides"][1]["minutes"] == 60


def test_patch_event_noop_and_invalid_shapes_rejected(client_obj):
    with pytest.raises(ValueError):
        client_obj.patch_event("evt")
    with pytest.raises(ValueError):
        client_obj.patch_event("evt", date="2026-05-25")
    with pytest.raises(ValueError):
        client_obj.patch_event("evt", date="2026-05-25", time="14:00", all_day=True)
    with pytest.raises(ValueError):
        client_obj.patch_event("evt", clear_reminders=True, replace_reminder_minutes=[10])


def test_patch_event_clear_reminders_and_omits_arrays_without_replace(client_obj):
    client_obj.service.events.return_value.patch.return_value.execute.return_value = {
        "id": "evt",
        "summary": "New",
        "start": {"date": "2026-05-25"},
        "end": {"date": "2026-05-26"},
    }

    client_obj.patch_event("evt", summary="New")
    body = client_obj.service.events.return_value.patch.call_args.kwargs["body"]
    assert "attendees" not in body
    assert "recurrence" not in body
    assert "reminders" not in body

    client_obj.patch_event("evt", clear_reminders=True)
    body = client_obj.service.events.return_value.patch.call_args.kwargs["body"]
    assert body["reminders"] == {"useDefault": False, "overrides": []}


def test_rsvp_event_updates_self_attendee(client_obj):
    client_obj.service.events.return_value.get.return_value.execute.return_value = {
        "id": "evt",
        "summary": "Invite",
        "start": {"dateTime": "2026-05-25T14:00:00+03:00"},
        "end": {"dateTime": "2026-05-25T15:00:00+03:00"},
        "attendees": [
            {"email": "other@example.com", "responseStatus": "accepted"},
            {"email": "me@example.com", "self": True, "responseStatus": "needsAction"},
        ],
    }
    client_obj.service.events.return_value.patch.return_value.execute.return_value = {
        "id": "evt",
        "summary": "Invite",
        "start": {"dateTime": "2026-05-25T14:00:00+03:00"},
        "end": {"dateTime": "2026-05-25T15:00:00+03:00"},
        "attendees": [
            {"email": "other@example.com", "responseStatus": "accepted"},
            {"email": "me@example.com", "self": True, "responseStatus": "accepted"},
        ],
    }

    result = client_obj.rsvp_event("evt", "accepted", calendar_id="team@example.com")

    kwargs = client_obj.service.events.return_value.patch.call_args.kwargs
    assert kwargs["calendarId"] == "team@example.com"
    assert kwargs["eventId"] == "evt"
    assert kwargs["sendUpdates"] == "all"
    assert kwargs["body"]["attendees"][1]["responseStatus"] == "accepted"
    assert result["attendees"][1]["responseStatus"] == "accepted"


def test_rsvp_event_requires_self_attendee(client_obj):
    client_obj.service.events.return_value.get.return_value.execute.return_value = {
        "id": "evt",
        "summary": "Invite",
        "start": {"dateTime": "2026-05-25T14:00:00+03:00"},
        "end": {"dateTime": "2026-05-25T15:00:00+03:00"},
        "attendees": [{"email": "other@example.com", "responseStatus": "accepted"}],
    }

    with pytest.raises(UsageError):
        client_obj.rsvp_event("evt", "accepted")


def test_move_event_uses_destination_calendar(client_obj):
    client_obj.service.events.return_value.move.return_value.execute.return_value = {
        "id": "evt",
        "summary": "Moved",
        "start": {"dateTime": "2026-05-25T14:00:00+03:00"},
        "end": {"dateTime": "2026-05-25T15:00:00+03:00"},
    }

    result = client_obj.move_event(
        "evt",
        calendar_id="source@example.com",
        destination_calendar_id="dest@example.com",
    )

    kwargs = client_obj.service.events.return_value.move.call_args.kwargs
    assert kwargs == {
        "calendarId": "source@example.com",
        "eventId": "evt",
        "destination": "dest@example.com",
    }
    assert result["calendar_id"] == "dest@example.com"


def test_delete_accepts_calendar_id(client_obj):
    client_obj.service.events.return_value.delete.return_value.execute.return_value = {}

    client_obj.delete_event("evt", calendar_id="team@example.com")

    assert client_obj.service.events.return_value.delete.call_args.kwargs["calendarId"] == "team@example.com"


def test_freebusy_normalizes_partial_errors(client_obj):
    client_obj.service.freebusy.return_value.query.return_value.execute.return_value = {
        "calendars": {
            "primary": {"busy": [{"start": "s", "end": "e"}]},
            "bad": {"errors": [{"reason": "notFound"}], "busy": []},
        }
    }

    out = client_obj.freebusy("s", "e", calendar_ids=["primary", "bad"])

    assert out["kind"] == "calendar_freebusy/v1"
    assert out["has_errors"] is True
    assert out["calendars"][1]["errors"][0]["reason"] == "notFound"


def test_normalize_event_meet_pending_and_entrypoint(client_obj):
    pending = client_obj._normalize_event({
        "id": "evt",
        "summary": "M",
        "start": {"dateTime": "2026-05-25T14:00:00+03:00"},
        "end": {"dateTime": "2026-05-25T15:00:00+03:00"},
        "conferenceData": {"createRequest": {"status": {"statusCode": "pending"}}},
    })
    assert pending["meet_status"] == "pending"
    assert pending["meet_link"] == ""

    success = client_obj._normalize_event({
        "id": "evt",
        "summary": "M",
        "start": {"dateTime": "2026-05-25T14:00:00+03:00"},
        "end": {"dateTime": "2026-05-25T15:00:00+03:00"},
        "conferenceData": {
            "entryPoints": [{"entryPointType": "video", "uri": "https://meet.google.com/abc"}]
        },
    })
    assert success["meet_status"] == "success"
    assert success["meet_link"] == "https://meet.google.com/abc"


# ---------- P0: create_calendar and list_instances ----------

def test_create_calendar_dispatches_summary_timezone(client_obj):
    client_obj.service.calendars.return_value.insert.return_value.execute.return_value = {
        "id": "newcal@group.calendar.google.com",
        "summary": "Test Calendar",
        "timeZone": "UTC",
    }

    result = client_obj.create_calendar("Test Calendar", timezone="UTC")

    call_kwargs = client_obj.service.calendars.return_value.insert.call_args.kwargs
    assert call_kwargs["body"]["summary"] == "Test Calendar"
    assert call_kwargs["body"]["timeZone"] == "UTC"
    assert result["summary"] == "Test Calendar"


def test_instances_dispatches_date_window_and_max(client_obj):
    client_obj.service.events.return_value.instances.return_value.execute.return_value = {
        "items": [
            {
                "id": "evt_20260601",
                "summary": "Weekly Meeting",
                "start": {"dateTime": "2026-06-01T14:00:00+03:00"},
                "end": {"dateTime": "2026-06-01T15:00:00+03:00"},
            }
        ]
    }

    result = client_obj.list_instances(
        "event1",
        calendar_id="primary",
        time_min="2026-06-01T00:00:00+00:00",
        time_max="2026-07-01T00:00:00+00:00",
        max_results=50,
    )

    call_kwargs = client_obj.service.events.return_value.instances.call_args.kwargs
    assert call_kwargs["calendarId"] == "primary"
    assert call_kwargs["eventId"] == "event1"
    assert call_kwargs["timeMin"] == "2026-06-01T00:00:00+00:00"
    assert call_kwargs["timeMax"] == "2026-07-01T00:00:00+00:00"
    assert call_kwargs["maxResults"] == 50
    assert isinstance(result, list)
    assert len(result) == 1


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


# --- span fields: multi-day / ongoing (#351, #359) --------------------------

def _span(client_obj, start, end, now, *, all_day=True, tz=None):
    key = "date" if all_day else "dateTime"
    ev = {"id": "e", "summary": "Trip",
          "start": {key: start}, "end": {key: end}}
    return client_obj._normalize_event(ev, now=now, tz=tz)


def _client():
    from h2t_ops.connectors.calendar.client import CalendarClient
    return object.__new__(CalendarClient)


def _at(iso: str) -> datetime:
    """A tz-aware instant; every `ongoing` question is a question about an instant."""
    return datetime.fromisoformat(iso)


def test_all_day_multi_day_ongoing():
    r = _span(_client(), "2026-08-18", "2026-08-26", _at("2026-08-20T09:00:00+03:00"))
    assert (r["multi_day"], r["days_total"], r["ongoing"], r["day_index"]) == (True, 8, True, 3)


def test_all_day_end_is_exclusive_last_day_and_after():
    c = _client()
    last = _span(c, "2026-08-18", "2026-08-26", _at("2026-08-25T23:00:00+03:00"))
    assert last["ongoing"] is True and last["day_index"] == 8
    after = _span(c, "2026-08-18", "2026-08-26", _at("2026-08-26T00:30:00+03:00"))
    assert after["ongoing"] is False and after["day_index"] is None


def test_single_all_day_stays_ongoing_all_day():
    """A birthday has no clock; for all-day rows the day *is* the span."""
    r = _span(_client(), "2026-08-20", "2026-08-21", _at("2026-08-20T21:00:00+03:00"))
    assert r["multi_day"] is False and r["days_total"] == 1
    assert r["ongoing"] is True and r["day_index"] == 1


def test_timed_event_is_not_ongoing_before_it_starts():
    """The #359 regression: a 13:00 meeting was 'ongoing' at 09:00."""
    r = _span(_client(), "2026-04-06T13:00:00+03:00", "2026-04-06T14:00:00+03:00",
              _at("2026-04-06T09:00:00+03:00"), all_day=False)
    assert r["ongoing"] is False
    assert r["day_index"] == 1  # it still falls on today


def test_timed_event_is_ongoing_while_it_runs():
    r = _span(_client(), "2026-04-06T13:00:00+03:00", "2026-04-06T14:00:00+03:00",
              _at("2026-04-06T13:30:00+03:00"), all_day=False)
    assert r["ongoing"] is True and r["all_day"] is False and r["multi_day"] is False


def test_timed_event_is_not_ongoing_after_it_ends():
    r = _span(_client(), "2026-04-06T13:00:00+03:00", "2026-04-06T14:00:00+03:00",
              _at("2026-04-06T20:00:00+03:00"), all_day=False)
    assert r["ongoing"] is False


def test_timed_event_end_is_exclusive():
    """At exactly 14:00 the meeting is over, not running."""
    r = _span(_client(), "2026-04-06T13:00:00+03:00", "2026-04-06T14:00:00+03:00",
              _at("2026-04-06T14:00:00+03:00"), all_day=False)
    assert r["ongoing"] is False


def test_timed_event_ongoing_is_judged_in_the_requested_timezone():
    """09:00 in Jerusalem is 08:00 in Berlin — the requested tz decides."""
    ev_start, ev_end = "2026-04-06T09:30:00+03:00", "2026-04-06T10:30:00+03:00"
    c = _client()
    berlin = c._normalize_event(
        {"id": "e", "start": {"dateTime": ev_start}, "end": {"dateTime": ev_end}},
        now=_at("2026-04-06T09:00:00+02:00"), tz="Europe/Berlin",
    )
    assert berlin["ongoing"] is True  # 09:00 Berlin == 10:00 Jerusalem, mid-meeting


def test_span_survives_a_naive_now():
    """A caller that forgets tzinfo must not raise; the event's offset is assumed."""
    r = _span(_client(), "2026-04-06T13:00:00+03:00", "2026-04-06T14:00:00+03:00",
              datetime(2026, 4, 6, 13, 30), all_day=False)
    assert r["ongoing"] is True


def test_unparseable_times_fall_back_to_the_date_span():
    """A valid date with a broken clock part degrades to the old date answer.

    Exercised on _event_span directly: _normalize_event parses the same timestamps
    for `duration_min` and would raise before the span is ever derived.
    """
    from h2t_ops.connectors.calendar.client import CalendarClient
    r = CalendarClient._event_span(
        "2026-04-06T13:00:00+03:00", "2026-04-06T99:99:99", False,
        _at("2026-04-06T09:00:00+03:00"),
    )
    assert r["ongoing"] is True and r["days_total"] == 1
