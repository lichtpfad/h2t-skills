"""Tests for h2t_ops.connectors.meetgeek.client.MeetGeekClient."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from h2t_ops.core.errors import (
    AuthError,
    ConfigError,
    NetworkError,
    NotFoundError,
    ProviderError,
    UsageError,
)

# ─── Fixture ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client_obj(monkeypatch):
    """MeetGeekClient bypassing __init__ (no network / secrets)."""
    monkeypatch.setenv("MEETGEEK_API_KEY", "test-key")
    from h2t_ops.connectors.meetgeek.client import MeetGeekClient
    c = object.__new__(MeetGeekClient)
    c._api_key = "test-key"
    c._base_url = "https://api.meetgeek.ai"
    c._timeout = 10
    return c


# ─── Module-scope import guard ────────────────────────────────────────────────

def test_module_has_no_module_level_requests_import():
    """requests must not appear at module scope — lazy-import regression guard."""
    src = (
        __import__("pathlib").Path("h2t_ops/connectors/meetgeek/client.py")
        .read_text(encoding="utf-8")
    )
    lines = src.splitlines()
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith(("import requests", "from requests")):
            assert line[0] == " ", (
                f"line {i}: module-scope 'requests' import forbidden in client.py: {line!r}"
            )


# ─── Init / auth ─────────────────────────────────────────────────────────────

def test_init_missing_api_key_raises_configerror(monkeypatch):
    monkeypatch.delenv("MEETGEEK_API_KEY", raising=False)
    with patch("h2t_ops.connectors.meetgeek.client.load_secrets"):
        from h2t_ops.connectors.meetgeek.client import MeetGeekClient
        with pytest.raises(ConfigError) as ei:
            MeetGeekClient()
    assert "MEETGEEK_API_KEY" in str(ei.value)
    assert ei.value.hint is not None


def test_init_calls_load_secrets_before_reading_env(monkeypatch):
    """load_secrets() must be called before checking os.environ."""
    monkeypatch.delenv("MEETGEEK_API_KEY", raising=False)
    call_log = []

    def fake_load():
        os.environ["MEETGEEK_API_KEY"] = "injected-key"
        call_log.append("load_secrets")

    with patch("h2t_ops.connectors.meetgeek.client.load_secrets", side_effect=fake_load):
        from h2t_ops.connectors.meetgeek.client import MeetGeekClient
        client = MeetGeekClient()
    assert call_log == ["load_secrets"]
    assert client._api_key == "injected-key"
    monkeypatch.delenv("MEETGEEK_API_KEY", raising=False)


def test_auth_check_returns_true_on_200(client_obj):
    resp = MagicMock()
    resp.status_code = 200
    client_obj._request = MagicMock(return_value=resp)
    assert client_obj.auth_check() is True


def test_auth_check_raises_autherror_on_401(client_obj):
    resp = MagicMock()
    resp.status_code = 401
    client_obj._request = MagicMock(return_value=resp)
    with pytest.raises(AuthError):
        client_obj.auth_check()


def test_auth_check_raises_providererror_on_500(client_obj):
    resp = MagicMock()
    resp.status_code = 500
    resp.text = "err"
    client_obj._request = MagicMock(return_value=resp)
    with pytest.raises(ProviderError):
        client_obj.auth_check()


# ─── list_meetings ────────────────────────────────────────────────────────────

def test_list_meetings_returns_rows_and_next_cursor(client_obj):
    resp_data = {
        "meetings": [{"meeting_id": "m1"}, {"meeting_id": "m2"}],
        "pagination": {"next_cursor": "tok123"},
    }
    client_obj._get = MagicMock(return_value=resp_data)
    result = client_obj.list_meetings(limit=2)
    assert result["rows"] == [{"meeting_id": "m1"}, {"meeting_id": "m2"}]
    assert result["next_cursor"] == "tok123"


def test_list_meetings_handles_list_response_shape(client_obj):
    """API may return a bare list instead of {meetings: [...]}."""
    client_obj._get = MagicMock(return_value=[{"meeting_id": "m1"}])
    result = client_obj.list_meetings()
    assert result["rows"] == [{"meeting_id": "m1"}]
    assert result["next_cursor"] is None


def test_list_meetings_raw_rows_preserve_api_fields(client_obj):
    """Client must NOT normalize meeting_id|id or timestamp fields — that is commands layer."""
    raw = {"meeting_id": "abc", "timestamp_start_utc": "2026-05-01T10:00:00Z", "title": "T"}
    client_obj._get = MagicMock(return_value={"meetings": [raw], "pagination": {}})
    result = client_obj.list_meetings()
    assert result["rows"][0] is raw  # same object, no transformation


def test_list_meetings_handles_items_response_shape(client_obj):
    """API may return {"items": [...]} instead of {"meetings": [...]}."""
    client_obj._get = MagicMock(return_value={"items": [{"meeting_id": "m3"}], "pagination": {}})
    result = client_obj.list_meetings()
    assert result["rows"] == [{"meeting_id": "m3"}]
    assert result["next_cursor"] is None


# ─── get_meeting ──────────────────────────────────────────────────────────────

def test_get_meeting_calls_singular_endpoint(client_obj):
    """/v1/meeting/{id} — note singular, not /v1/meetings/{id}."""
    client_obj._get = MagicMock(return_value={"meeting_id": "m1"})
    client_obj.get_meeting("m1")
    client_obj._get.assert_called_once_with("/v1/meeting/m1")


def test_get_meeting_returns_raw_response(client_obj):
    payload = {"meeting_id": "m1", "title": "Test", "language": "ru"}
    client_obj._get = MagicMock(return_value=payload)
    result = client_obj.get_meeting("m1")
    assert result is payload


def test_get_meeting_falls_back_to_list_row_when_metadata_404s(client_obj):
    payload = {"meetings": [{"id": "m1", "title": "Listed"}]}
    client_obj._get = MagicMock(side_effect=[
        NotFoundError("Not found: /v1/meeting/m1"),
        payload,
    ])

    result = client_obj.get_meeting("m1")

    assert result == payload["meetings"][0]
    assert client_obj._get.call_args_list[0].args == ("/v1/meeting/m1",)
    assert client_obj._get.call_args_list[1].args == ("/v1/meetings",)


def test_get_meeting_raises_when_metadata_and_list_fallback_miss(client_obj):
    client_obj._get = MagicMock(side_effect=[
        NotFoundError("Not found: /v1/meeting/missing"),
        {"meetings": []},
    ])

    with pytest.raises(NotFoundError) as ei:
        client_obj.get_meeting("missing")

    assert "metadata endpoint or list fallback" in str(ei.value)


# ─── get_transcript ───────────────────────────────────────────────────────────

def test_get_transcript_returns_combined_sentences(client_obj):
    page1 = {
        "meeting_id": "m1",
        "sentences": [{"speaker": "A", "text": "Hello"}],
        "pagination": {"next_cursor": "tok2"},
    }
    page2 = {
        "sentences": [{"speaker": "B", "text": "World"}],
        "pagination": {},
    }
    client_obj._get = MagicMock(side_effect=[page1, page2])
    result = client_obj.get_transcript("m1")
    assert result["meeting_id"] == "m1"
    assert len(result["sentences"]) == 2
    assert result["sentences"][0]["text"] == "Hello"
    assert result["sentences"][1]["text"] == "World"


def test_get_transcript_single_page_no_cursor(client_obj):
    page = {"sentences": [{"text": "Solo"}], "pagination": {}}
    client_obj._get = MagicMock(return_value=page)
    result = client_obj.get_transcript("m1")
    assert len(result["sentences"]) == 1
    client_obj._get.assert_called_once()


# ─── get_summary / highlights / insights ──────────────────────────────────────

def test_get_summary_calls_correct_endpoint(client_obj):
    client_obj._get = MagicMock(return_value={"summary": "text"})
    client_obj.get_summary("m1")
    client_obj._get.assert_called_once_with("/v1/meetings/m1/summary")


def test_get_highlights_calls_correct_endpoint(client_obj):
    client_obj._get = MagicMock(return_value={"highlights": []})
    client_obj.get_highlights("m1")
    client_obj._get.assert_called_once_with("/v1/meetings/m1/highlights")


def test_get_insights_calls_correct_endpoint(client_obj):
    client_obj._get = MagicMock(return_value={})
    client_obj.get_insights("m1")
    client_obj._get.assert_called_once_with("/v1/meetings/m1/insights")


# ─── get_download_url ─────────────────────────────────────────────────────────

def test_get_download_url_normalizes_download_link(client_obj):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"download_link": "https://media.meetgeek.ai/file.mp4"}
    client_obj._request = MagicMock(return_value=resp)
    result = client_obj.get_download_url("m1")
    assert result["meeting_id"] == "m1"
    assert result["download_url"] == "https://media.meetgeek.ai/file.mp4"


def test_get_download_url_normalizes_url_field(client_obj):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"url": "https://media.meetgeek.ai/file.mp4"}
    client_obj._request = MagicMock(return_value=resp)
    result = client_obj.get_download_url("m1")
    assert result["download_url"] == "https://media.meetgeek.ai/file.mp4"


def test_get_download_url_raises_providererror_when_no_url(client_obj):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"message": "ok"}  # no url field
    client_obj._request = MagicMock(return_value=resp)
    with pytest.raises(ProviderError):
        client_obj.get_download_url("m1")


def test_download_url_never_opens_file(client_obj):
    """get_download_url must never open/write a file — URL-only verb."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"download_link": "https://example.com/f.mp4"}
    client_obj._request = MagicMock(return_value=resp)
    with patch("builtins.open") as mock_open:
        client_obj.get_download_url("m1")
    mock_open.assert_not_called()


# ─── get_teams ────────────────────────────────────────────────────────────────

def test_get_teams_calls_correct_endpoint(client_obj):
    client_obj._get = MagicMock(return_value={"teams": []})
    client_obj.get_teams()
    client_obj._get.assert_called_once_with("/v1/teams")


# ─── submit_url ───────────────────────────────────────────────────────────────

def test_submit_url_posts_with_confirmed_language_field(client_obj):
    """T0 confirmed: API body uses 'language' (not 'language_code')."""
    resp = MagicMock()
    resp.status_code = 202
    resp.json.return_value = {"message": "Processing"}
    client_obj._request = MagicMock(return_value=resp)
    result = client_obj.submit_url(
        "https://example.com/f.mp4",
        title="Meeting 2026-05-20",
        language_code="ru",
        template_name="default",
    )
    call_kwargs = client_obj._request.call_args
    body = call_kwargs[1]["json_body"]
    assert body["download_url"] == "https://example.com/f.mp4"
    assert body["language"] == "ru"          # API field is "language" not "language_code"
    assert "language_code" not in body       # must NOT send "language_code" to API
    assert body["title"] == "Meeting 2026-05-20"
    assert body["template_name"] == "default"
    assert result["message"] == "Processing"


def test_submit_url_omits_none_optional_fields(client_obj):
    resp = MagicMock()
    resp.status_code = 202
    resp.json.return_value = {"message": "ok"}
    client_obj._request = MagicMock(return_value=resp)
    client_obj.submit_url("https://example.com/f.mp4")
    body = client_obj._request.call_args[1]["json_body"]
    assert "title" not in body
    assert "language" not in body
    assert "language_code" not in body
    assert "template_name" not in body


def test_submit_url_empty_url_raises_usageerror(client_obj):
    with pytest.raises(UsageError):
        client_obj.submit_url("")


def test_submit_url_raises_autherror_on_401(client_obj):
    resp = MagicMock()
    resp.status_code = 401
    resp.text = "Unauthorized"
    client_obj._request = MagicMock(return_value=resp)
    with pytest.raises(AuthError):
        client_obj.submit_url("https://example.com/f.mp4")


# ─── action_items ─────────────────────────────────────────────────────────────

def test_action_items_returns_summary_action_items(client_obj):
    summary_data = {
        "summary": "Meeting summary text",
        "action_items": [
            {"owner": "Alice", "text": "Follow up with client"},
            {"owner": "Bob", "text": "Update docs"},
        ],
    }
    client_obj.get_summary = MagicMock(return_value=summary_data)
    result = client_obj.action_items("m1")
    assert result["meeting_id"] == "m1"
    assert result["source"] == "summary"
    assert len(result["action_items"]) == 2
    assert result["action_items"][0]["owner"] == "Alice"
    client_obj.get_summary.assert_called_once_with("m1")


def test_action_items_returns_empty_list_when_no_action_items(client_obj):
    client_obj.get_summary = MagicMock(return_value={"summary": "No action items here"})
    result = client_obj.action_items("m2")
    assert result["action_items"] == []
    assert result["meeting_id"] == "m2"


# ─── Error mapping (_raise_for_status) ────────────────────────────────────────

def test_raise_for_status_401_autherror(client_obj):
    from h2t_ops.connectors.meetgeek.client import _raise_for_status
    resp = MagicMock()
    resp.status_code = 401
    resp.text = "Unauthorized"
    with pytest.raises(AuthError):
        _raise_for_status(resp, "/v1/test")


def test_raise_for_status_404_notfounderror(client_obj):
    from h2t_ops.connectors.meetgeek.client import _raise_for_status
    resp = MagicMock()
    resp.status_code = 404
    resp.text = "Not Found"
    with pytest.raises(NotFoundError):
        _raise_for_status(resp, "/v1/test")


def test_raise_for_status_400_usageerror(client_obj):
    from h2t_ops.connectors.meetgeek.client import _raise_for_status
    resp = MagicMock()
    resp.status_code = 400
    resp.text = "Bad request"
    with pytest.raises(UsageError):
        _raise_for_status(resp, "/v1/test")


def test_raise_for_status_429_providererror(client_obj):
    from h2t_ops.connectors.meetgeek.client import _raise_for_status
    resp = MagicMock()
    resp.status_code = 429
    resp.text = "Rate limited"
    with pytest.raises(ProviderError):
        _raise_for_status(resp, "/v1/test")


def test_raise_for_status_500_providererror(client_obj):
    from h2t_ops.connectors.meetgeek.client import _raise_for_status
    resp = MagicMock()
    resp.status_code = 500
    resp.text = "Server error"
    with pytest.raises(ProviderError):
        _raise_for_status(resp, "/v1/test")


def test_network_exception_raises_networkerror(client_obj, monkeypatch):
    """NetworkError from _request propagates through _get unchanged."""
    def _fail(*a, **k):
        raise NetworkError("connection refused")

    monkeypatch.setattr(
        "h2t_ops.connectors.meetgeek.client.MeetGeekClient._request",
        _fail,
    )
    with pytest.raises(NetworkError):
        client_obj._get("/v1/meetings")


def test_request_raises_networkerror_on_429_exhaustion(client_obj, monkeypatch):
    """3x 429 responses should raise NetworkError mentioning rate limit, not 'server error'."""
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda _: None)
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"Retry-After": "0"}
    with patch("requests.request", return_value=resp_429):
        with pytest.raises(NetworkError) as ei:
            client_obj._request("GET", "/v1/meetings")
    assert "429" in str(ei.value) or "rate" in str(ei.value).lower()
