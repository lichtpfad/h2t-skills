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
    mock_client.list_messages_page.return_value = {
        "items": mock_messages,
        "has_more": False,
        "estimated_total": 1,
    }

    with patch("clients.gmail.GmailClient") as MockClass:
        MockClass.return_value = mock_client
        output = run_cli("ingest", "gmail", "list", "--max", "5", "--json")

    data = json.loads(output)
    assert data["count"] == 1
    assert data["limit"] == 5
    assert data["truncated"] is False
    assert data["estimated_total"] == 1
    assert data["items"][0]["id"] == "1"
    assert data["items"][0]["subject"] == "Test"


def test_ingest_gmail_list_bare_is_a_plain_array():
    mock_client = MagicMock()
    mock_client.list_messages_page.return_value = {
        "items": [{"id": "1", "subject": "Test"}],
        "has_more": True,
    }

    with patch("clients.gmail.GmailClient") as MockClass:
        MockClass.return_value = mock_client
        output = run_cli("ingest", "gmail", "list", "--max", "1", "--json", "--bare")

    data = json.loads(output)
    assert isinstance(data, list)
    assert data[0]["id"] == "1"


def test_ingest_gmail_list_reports_truncation():
    """A full page must not read as a complete result."""
    mock_client = MagicMock()
    mock_client.list_messages_page.return_value = {
        "items": [{"id": "1"}, {"id": "2"}],
        "has_more": True,
        "estimated_total": 412,
    }

    with patch("clients.gmail.GmailClient") as MockClass:
        MockClass.return_value = mock_client
        output = run_cli("ingest", "gmail", "list", "--max", "2", "--json")

    data = json.loads(output)
    assert data["count"] == 2
    assert data["truncated"] is True
    assert data["estimated_total"] == 412


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
    mock_client.list_events_page.return_value = {
        "items": mock_events,
        "has_more": False,
        "window": {"from": "2026-08-20T00:00:00+00:00", "to": "2026-08-21T00:00:00+00:00"},
    }

    with patch("clients.calendar.CalendarClient") as MockClass:
        MockClass.return_value = mock_client
        output = run_cli("ingest", "calendar", "list", "--json")

    data = json.loads(output)
    assert data["count"] == 1
    assert data["truncated"] is False
    assert data["window"]["from"].startswith("2026-08-20")
    assert data["items"][0]["id"] == "e1"
    assert data["items"][0]["summary"] == "Meeting"


def test_ingest_notion_no_cmd():
    output = run_cli("ingest", "notion")
    assert output == ""


def test_ingest_notion_search_envelope_carries_resolved_relations():
    """The markdown path resolved relations; the json envelope must too."""
    rows = [{"id": "t1", "url": "https://notion.so/t1",
             "properties": {"Project": {"type": "relation",
                                        "relation": [{"id": "p1"}], "has_more": False}}}]
    mock_client = MagicMock()
    mock_client.query_database_page.return_value = {"items": rows, "has_more": False}
    mock_client.resolve_relations.return_value = {
        "p1": {"title": "Qatal Yiktol", "url": "https://notion.so/qy"}
    }

    with patch("clients.notion.NotionClient") as MockClass:
        MockClass.return_value = mock_client
        output = run_cli(
            "ingest", "notion", "search", "db1",
            "--limit", "10", "--format", "json", "--resolve-relations", "Project",
        )

    data = json.loads(output)
    assert data["relations"]["p1"]["title"] == "Qatal Yiktol"
    assert data["count"] == 1
    assert data["truncated"] is False
