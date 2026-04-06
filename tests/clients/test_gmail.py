"""Unit tests for GmailClient helpers (no network calls)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

import pytest
from clients.gmail import format_message_list, format_message_detail


def test_format_message_list_empty():
    assert format_message_list([]) == "No messages found."


def test_format_message_list_unread_marker():
    msg = {
        "id": "abc123",
        "labelIds": ["UNREAD"],
        "subject": "Test Subject",
        "from": "test@example.com",
        "date": "Mon, 6 Apr 2026",
        "snippet": "Hello world",
    }
    result = format_message_list([msg])
    assert "Test Subject" in result
    assert "📩" in result
    assert "abc123" in result


def test_format_message_list_read_no_marker():
    msg = {
        "id": "xyz",
        "labelIds": [],
        "subject": "Read Mail",
        "from": "a@b.com",
        "date": "Mon",
        "snippet": "body",
    }
    result = format_message_list([msg])
    assert "📩" not in result


def test_format_message_detail():
    msg = {
        "subject": "Subject",
        "from": "From",
        "to": "To",
        "date": "Date",
        "labelIds": ["INBOX"],
        "body": "Body text",
    }
    result = format_message_detail(msg)
    assert "# Subject" in result
    assert "Body text" in result
    assert "**From:**" in result
