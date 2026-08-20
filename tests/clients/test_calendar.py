"""Unit tests for CalendarClient._normalize_event (no network calls)."""
import sys
from datetime import date
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


# --- span fields: multi-day and ongoing detection ---------------------------

def _trip(start: str, end: str) -> dict:
    """All-day event; Google end dates are exclusive."""
    return {
        "id": "trip",
        "summary": "Bavaria",
        "start": {"date": start},
        "end": {"date": end},
    }


def test_all_day_exposes_raw_start_and_end(client):
    r = client._normalize_event(_trip("2026-08-18", "2026-08-26"), today=date(2026, 8, 20))
    assert r["start"] == "2026-08-18"
    assert r["end"] == "2026-08-26"
    assert r["all_day"] is True


def test_multi_day_ongoing_reports_day_index(client):
    r = client._normalize_event(_trip("2026-08-18", "2026-08-26"), today=date(2026, 8, 20))
    assert r["multi_day"] is True
    assert r["days_total"] == 8
    assert r["ongoing"] is True
    assert r["day_index"] == 3


def test_ongoing_on_first_day(client):
    r = client._normalize_event(_trip("2026-08-18", "2026-08-26"), today=date(2026, 8, 18))
    assert r["ongoing"] is True
    assert r["day_index"] == 1


def test_ongoing_on_last_day_end_is_exclusive(client):
    """25 Aug is the last real day when end is 26 Aug."""
    r = client._normalize_event(_trip("2026-08-18", "2026-08-26"), today=date(2026, 8, 25))
    assert r["ongoing"] is True
    assert r["day_index"] == 8


def test_finished_on_exclusive_end_date(client):
    r = client._normalize_event(_trip("2026-08-18", "2026-08-26"), today=date(2026, 8, 26))
    assert r["ongoing"] is False
    assert r["day_index"] is None


def test_upcoming_multi_day_is_not_ongoing(client):
    r = client._normalize_event(_trip("2026-08-18", "2026-08-26"), today=date(2026, 8, 1))
    assert r["multi_day"] is True
    assert r["ongoing"] is False


def test_single_all_day_is_not_multi_day(client):
    r = client._normalize_event(_trip("2026-08-20", "2026-08-21"), today=date(2026, 8, 20))
    assert r["multi_day"] is False
    assert r["days_total"] == 1
    assert r["ongoing"] is True
    assert r["day_index"] == 1


def test_timed_event_span_fields(client):
    event = {
        "id": "evt5",
        "summary": "Call",
        "start": {"dateTime": "2026-04-06T14:00:00+03:00"},
        "end": {"dateTime": "2026-04-06T15:00:00+03:00"},
    }
    r = client._normalize_event(event, today=date(2026, 4, 6))
    assert r["all_day"] is False
    assert r["multi_day"] is False
    assert r["ongoing"] is True
    assert r["end"] == "2026-04-06T15:00:00+03:00"
