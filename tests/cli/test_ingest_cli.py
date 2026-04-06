"""Integration tests for `h2t ingest` subcommand."""

import json
import os
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure lib/ is on sys.path
_lib = str(Path(__file__).resolve().parent.parent.parent / "lib")
if _lib not in sys.path:
    sys.path.insert(0, _lib)


def run_cli(*args):
    """Run CLI with given args, return captured stdout."""
    old_argv = sys.argv
    old_stdout = sys.stdout
    sys.argv = ["h2t"] + list(args)
    sys.stdout = StringIO()
    try:
        from cli.main import main
        try:
            main()
        except SystemExit:
            pass
    finally:
        captured_io = sys.stdout
        sys.stdout = old_stdout
        sys.argv = old_argv
    output = captured_io.getvalue()
    return output


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_ingest_help():
    output = run_cli("ingest", "--help")
    assert "gmail" in output
    assert "notion" in output
    assert "calendar" in output


def test_ingest_gmail_list_json():
    mock_messages = [
        {
            "id": "1",
            "labelIds": ["UNREAD"],
            "subject": "Test",
            "from": "a@b.com",
            "to": "me",
            "date": "Mon",
            "snippet": "Hi",
            "body": "",
        }
    ]
    mock_client = MagicMock()
    mock_client.list_messages.return_value = mock_messages

    with patch("clients.gmail.GmailClient") as MockClass:
        MockClass.return_value = mock_client
        output = run_cli("ingest", "gmail", "list", "--max", "5", "--json")

    data = json.loads(output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == "1"
    assert data[0]["subject"] == "Test"


def test_ingest_gmail_labels():
    mock_labels = [{"name": "INBOX", "id": "INBOX"}]
    mock_client = MagicMock()
    mock_client.list_labels.return_value = mock_labels

    with patch("clients.gmail.GmailClient") as MockClass:
        MockClass.return_value = mock_client
        output = run_cli("ingest", "gmail", "labels")

    assert "INBOX" in output


def test_ingest_calendar_list_json():
    mock_events = [
        {
            "id": "e1",
            "summary": "Meeting",
            "date": "2026-04-06",
            "time": "10:00",
            "duration_min": 60,
            "location": "",
            "description": "",
            "html_link": "",
        }
    ]
    mock_client = MagicMock()
    mock_client.list_events.return_value = mock_events

    with patch("clients.calendar.CalendarClient") as MockClass:
        MockClass.return_value = mock_client
        output = run_cli("ingest", "calendar", "list", "--json")

    data = json.loads(output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == "e1"
    assert data[0]["summary"] == "Meeting"


def test_ingest_notion_no_cmd():
    output = run_cli("ingest", "notion")
    assert output == ""
