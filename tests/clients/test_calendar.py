"""Unit tests for CalendarClient._normalize_event (no network calls)."""
import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

import pytest
from clients.calendar import CalendarClient


@pytest.fixture
def client():
    return object.__new__(CalendarClient)


def test_normalize_timed_event(client):
    event = {
        "id": "evt1",
        "summary": "Meeting",
        "start": {"dateTime": "2026-04-06T14:00:00+03:00"},
        "end": {"dateTime": "2026-04-06T15:00:00+03:00"},
        "htmlLink": "https://cal.google.com/...",
    }
    result = client._normalize_event(event)
    assert result["summary"] == "Meeting"
    assert result["time"] == "14:00"
    assert result["duration_min"] == 60
    assert result["date"] == "2026-04-06"
    assert result["id"] == "evt1"


def test_normalize_all_day_event(client):
    event = {
        "id": "evt2",
        "summary": "Holiday",
        "start": {"date": "2026-04-07"},
        "end": {"date": "2026-04-08"},
    }
    result = client._normalize_event(event)
    assert result["time"] == "весь день"
    assert result["duration_min"] is None
    assert result["date"] == "2026-04-07"


def test_normalize_missing_location(client):
    event = {
        "id": "evt3",
        "summary": "No Location",
        "start": {"date": "2026-04-06"},
        "end": {"date": "2026-04-07"},
    }
    result = client._normalize_event(event)
    assert result["location"] == ""


def test_normalize_description_truncated(client):
    event = {
        "id": "evt4",
        "summary": "With Desc",
        "start": {"date": "2026-04-06"},
        "end": {"date": "2026-04-07"},
        "description": "A" * 300,
    }
    result = client._normalize_event(event)
    assert len(result["description"]) == 200


# --- span fields: multi-day and ongoing detection (#351, #359) --------------

def _trip(start: str, end: str) -> dict:
    """All-day event; Google end dates are exclusive."""
    return {
        "id": "trip",
        "summary": "Bavaria",
        "start": {"date": start},
        "end": {"date": end},
    }


def _at(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def test_all_day_exposes_raw_start_and_end(client):
    r = client._normalize_event(_trip("2026-08-18", "2026-08-26"), now=_at("2026-08-20T09:00+03:00"))
    assert r["start"] == "2026-08-18"
    assert r["end"] == "2026-08-26"
    assert r["all_day"] is True


def test_multi_day_ongoing_reports_day_index(client):
    r = client._normalize_event(_trip("2026-08-18", "2026-08-26"), now=_at("2026-08-20T09:00+03:00"))
    assert r["multi_day"] is True
    assert r["days_total"] == 8
    assert r["ongoing"] is True
    assert r["day_index"] == 3


def test_ongoing_on_first_day(client):
    r = client._normalize_event(_trip("2026-08-18", "2026-08-26"), now=_at("2026-08-18T23:00+03:00"))
    assert r["ongoing"] is True
    assert r["day_index"] == 1


def test_ongoing_on_last_day_end_is_exclusive(client):
    """25 Aug is the last real day when end is 26 Aug."""
    r = client._normalize_event(_trip("2026-08-18", "2026-08-26"), now=_at("2026-08-25T12:00+03:00"))
    assert r["ongoing"] is True
    assert r["day_index"] == 8


def test_finished_on_exclusive_end_date(client):
    r = client._normalize_event(_trip("2026-08-18", "2026-08-26"), now=_at("2026-08-26T00:30+03:00"))
    assert r["ongoing"] is False
    assert r["day_index"] is None


def test_upcoming_multi_day_is_not_ongoing(client):
    r = client._normalize_event(_trip("2026-08-18", "2026-08-26"), now=_at("2026-08-01T09:00+03:00"))
    assert r["multi_day"] is True
    assert r["ongoing"] is False


def test_single_all_day_stays_ongoing_all_day(client):
    """A birthday has no clock; for all-day rows the day is the span."""
    r = client._normalize_event(_trip("2026-08-20", "2026-08-21"), now=_at("2026-08-20T21:00+03:00"))
    assert r["multi_day"] is False
    assert r["days_total"] == 1
    assert r["ongoing"] is True
    assert r["day_index"] == 1


def _call(start: str, end: str) -> dict:
    return {"id": "evt5", "summary": "Call",
            "start": {"dateTime": start}, "end": {"dateTime": end}}


def test_timed_event_is_not_ongoing_before_it_starts(client):
    """The #359 regression: a 13:00 meeting was 'ongoing' at 09:00."""
    r = client._normalize_event(
        _call("2026-04-06T13:00:00+03:00", "2026-04-06T14:00:00+03:00"),
        now=_at("2026-04-06T09:00:00+03:00"))
    assert r["ongoing"] is False
    assert r["day_index"] == 1  # it still falls on today


def test_timed_event_is_ongoing_while_it_runs(client):
    r = client._normalize_event(
        _call("2026-04-06T13:00:00+03:00", "2026-04-06T14:00:00+03:00"),
        now=_at("2026-04-06T13:30:00+03:00"))
    assert r["all_day"] is False
    assert r["multi_day"] is False
    assert r["ongoing"] is True
    assert r["end"] == "2026-04-06T14:00:00+03:00"


def test_timed_event_is_not_ongoing_after_it_ends(client):
    r = client._normalize_event(
        _call("2026-04-06T13:00:00+03:00", "2026-04-06T14:00:00+03:00"),
        now=_at("2026-04-06T20:00:00+03:00"))
    assert r["ongoing"] is False


def test_timed_event_end_is_exclusive(client):
    r = client._normalize_event(
        _call("2026-04-06T13:00:00+03:00", "2026-04-06T14:00:00+03:00"),
        now=_at("2026-04-06T14:00:00+03:00"))
    assert r["ongoing"] is False


def test_span_survives_a_naive_now(client):
    r = client._normalize_event(
        _call("2026-04-06T13:00:00+03:00", "2026-04-06T14:00:00+03:00"),
        now=datetime(2026, 4, 6, 13, 30))
    assert r["ongoing"] is True
