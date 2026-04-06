"""Unit tests for CalendarClient._normalize_event (no network calls)."""
import sys
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
