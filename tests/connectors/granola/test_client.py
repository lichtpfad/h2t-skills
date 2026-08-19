"""Tests for h2t_ops.connectors.granola.client.GranolaClient."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from h2t_ops.core.errors import (
    AuthError, ConfigError, NotFoundError, ProviderError, UsageError,
)


@pytest.fixture
def client_obj(monkeypatch):
    """GranolaClient bypassing __init__ (no network / secrets)."""
    monkeypatch.setenv("GRANOLA_API_KEY", "grn_test-key")
    from h2t_ops.connectors.granola.client import GranolaClient
    c = object.__new__(GranolaClient)
    c._api_key = "grn_test-key"
    c._base_url = "https://public-api.granola.ai"
    c._timeout = 10
    return c


def _resp(status: int, payload=None, headers=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.headers = headers or {}
    r.text = text
    r.json.return_value = payload if payload is not None else {}
    return r


# ─── Module-scope import guard ────────────────────────────────────────────────

def test_module_has_no_module_level_requests_import():
    """requests must not appear at module scope — lazy-import regression guard."""
    src = Path("h2t_ops/connectors/granola/client.py").read_text(encoding="utf-8")
    for i, line in enumerate(src.splitlines(), 1):
        if line.lstrip().startswith(("import requests", "from requests")):
            assert line[0] == " ", (
                f"line {i}: module-scope 'requests' import forbidden in client.py: {line!r}"
            )


# ─── Init / auth ──────────────────────────────────────────────────────────────

def test_init_missing_api_key_raises_configerror(monkeypatch):
    monkeypatch.delenv("GRANOLA_API_KEY", raising=False)
    with patch("h2t_ops.connectors.granola.client.load_secrets"):
        from h2t_ops.connectors.granola.client import GranolaClient
        with pytest.raises(ConfigError) as ei:
            GranolaClient()
    assert "GRANOLA_API_KEY" in str(ei.value)
    assert ei.value.hint is not None


def test_init_calls_load_secrets_before_reading_env(monkeypatch):
    monkeypatch.delenv("GRANOLA_API_KEY", raising=False)
    calls = []

    def fake_load():
        os.environ["GRANOLA_API_KEY"] = "grn_injected"
        calls.append("load_secrets")

    with patch("h2t_ops.connectors.granola.client.load_secrets", side_effect=fake_load):
        from h2t_ops.connectors.granola.client import GranolaClient
        client = GranolaClient()
    assert calls == ["load_secrets"]
    assert client._api_key == "grn_injected"
    os.environ.pop("GRANOLA_API_KEY", None)


def test_auth_check_true_on_200(client_obj):
    with patch.object(client_obj, "_request", return_value=_resp(200, {"notes": []})):
        assert client_obj.auth_check() is True


def test_auth_check_raises_autherror_on_401(client_obj):
    with patch.object(client_obj, "_request", return_value=_resp(401)):
        with pytest.raises(AuthError):
            client_obj.auth_check()


def test_bearer_header_uses_api_key(client_obj):
    assert client_obj._headers()["Authorization"] == "Bearer grn_test-key"


# ─── Retry / error mapping ────────────────────────────────────────────────────

def test_request_retries_5xx_then_returns(client_obj):
    seq = [_resp(500, text="boom"), _resp(500, text="boom"), _resp(200, {"ok": True})]
    fake = MagicMock(side_effect=seq)
    with patch("requests.request", fake), patch("time.sleep"):
        resp = client_obj._request("GET", "/v1/notes")
    assert resp.status_code == 200
    assert fake.call_count == 3


def test_request_honours_retry_after_on_429(client_obj):
    seq = [_resp(429, headers={"Retry-After": "2"}), _resp(200, {"ok": True})]
    sleeps = []
    with patch("requests.request", MagicMock(side_effect=seq)), \
            patch("time.sleep", side_effect=lambda s: sleeps.append(s)):
        resp = client_obj._request("GET", "/v1/notes")
    assert resp.status_code == 200
    assert sleeps == [2.0]


def test_get_maps_404_to_notfounderror(client_obj):
    with patch.object(client_obj, "_request", return_value=_resp(404, text="nope")):
        with pytest.raises(NotFoundError):
            client_obj._get("/v1/notes/not_missing")


def test_get_maps_400_to_usageerror(client_obj):
    with patch.object(client_obj, "_request", return_value=_resp(400, text="bad cursor")):
        with pytest.raises(UsageError):
            client_obj._get("/v1/notes")


def test_get_maps_malformed_json_to_providererror(client_obj):
    r = _resp(200)
    r.json.side_effect = ValueError("not json")
    with patch.object(client_obj, "_request", return_value=r):
        with pytest.raises(ProviderError):
            client_obj._get("/v1/notes")


# ─── list_notes ───────────────────────────────────────────────────────────────

def test_list_notes_passes_filters_and_caps_page_size(client_obj):
    captured = {}

    def fake_get(path, params=None):
        captured["path"] = path
        captured["params"] = params
        return {"notes": [], "hasMore": False, "cursor": None}

    with patch.object(client_obj, "_get", side_effect=fake_get):
        client_obj.list_notes(
            created_after="2026-08-01", created_before="2026-08-10",
            updated_after="2026-08-05", folder_id="fol_abc",
        )
    assert captured["path"] == "/v1/notes"
    assert captured["params"]["created_after"] == "2026-08-01"
    assert captured["params"]["created_before"] == "2026-08-10"
    assert captured["params"]["updated_after"] == "2026-08-05"
    assert captured["params"]["folder_id"] == "fol_abc"
    assert captured["params"]["page_size"] == 30  # API maximum


def test_list_notes_single_page_returns_rows_and_cursor(client_obj):
    page = {"notes": [{"id": "not_1"}, {"id": "not_2"}], "hasMore": True, "cursor": "cur_1"}
    with patch.object(client_obj, "_get", return_value=page):
        out = client_obj.list_notes()
    assert [r["id"] for r in out["rows"]] == ["not_1", "not_2"]
    assert out["next_cursor"] == "cur_1"
    assert out["has_more"] is True


def test_list_notes_limit_below_max_requests_exact_page_size(client_obj):
    with patch.object(client_obj, "_get", return_value={"notes": [], "hasMore": False, "cursor": None}) as g:
        client_obj.list_notes(limit=5)
    assert g.call_args.kwargs["params"]["page_size"] == 5


def test_list_notes_limit_above_page_max_pages_until_limit(client_obj):
    pages = [
        {"notes": [{"id": f"not_{i}"} for i in range(30)], "hasMore": True, "cursor": "cur_1"},
        {"notes": [{"id": f"not_{i}"} for i in range(30, 60)], "hasMore": True, "cursor": "cur_2"},
    ]
    calls = []

    def fake_get(path, params=None):
        calls.append(params)
        return pages[len(calls) - 1]

    with patch.object(client_obj, "_get", side_effect=fake_get):
        out = client_obj.list_notes(limit=45)
    assert len(out["rows"]) == 45
    assert calls[0].get("cursor") is None
    assert calls[1]["cursor"] == "cur_1"
    assert calls[1]["page_size"] == 15  # only the remainder is requested


def test_list_notes_stops_when_provider_has_no_more(client_obj):
    page = {"notes": [{"id": "not_1"}], "hasMore": False, "cursor": None}
    with patch.object(client_obj, "_get", return_value=page) as g:
        out = client_obj.list_notes(limit=100)
    assert len(out["rows"]) == 1
    assert g.call_count == 1


# ─── get_note ─────────────────────────────────────────────────────────────────

def test_get_note_without_transcript_sends_no_include(client_obj):
    with patch.object(client_obj, "_get", return_value={"id": "not_1"}) as g:
        out = client_obj.get_note("not_1")
    assert out["id"] == "not_1"
    assert g.call_args.args[0] == "/v1/notes/not_1"
    assert "include" not in (g.call_args.kwargs.get("params") or {})


def test_get_note_with_transcript_sends_include(client_obj):
    with patch.object(client_obj, "_get", return_value={"id": "not_1", "transcript": []}) as g:
        client_obj.get_note("not_1", include_transcript=True)
    assert g.call_args.kwargs["params"]["include"] == "transcript"


def test_get_note_falls_back_to_paged_transcript_on_413(client_obj):
    """413 TRANSCRIPT_TOO_LARGE is a routing signal, not a user-visible failure."""
    from h2t_ops.connectors.granola.client import _TranscriptTooLarge

    calls = []

    def fake_get(path, params=None):
        calls.append((path, params))
        if params and params.get("include") == "transcript":
            raise _TranscriptTooLarge(path)
        return {"id": "not_1", "title": "Big meeting"}

    with patch.object(client_obj, "_get", side_effect=fake_get), \
            patch.object(client_obj, "get_transcript",
                         return_value={"transcript": [{"text": "hi"}], "truncated": False}):
        out = client_obj.get_note("not_1", include_transcript=True)
    assert out["transcript"] == [{"text": "hi"}]
    assert out["title"] == "Big meeting"


# ─── get_transcript ───────────────────────────────────────────────────────────

def test_get_transcript_pages_until_exhausted(client_obj):
    pages = [
        {"transcript": [{"text": "a"}], "hasMore": True, "cursor": "c1"},
        {"transcript": [{"text": "b"}], "hasMore": False, "cursor": None},
    ]
    calls = []

    def fake_get(path, params=None):
        calls.append(params)
        return pages[len(calls) - 1]

    with patch.object(client_obj, "_get", side_effect=fake_get):
        out = client_obj.get_transcript("not_1")
    assert [i["text"] for i in out["transcript"]] == ["a", "b"]
    assert calls[0]["page_size"] == 100  # API maximum
    assert calls[1]["cursor"] == "c1"
    assert out["truncated"] is False


def test_get_transcript_reports_truncation_at_page_ceiling(client_obj, monkeypatch):
    monkeypatch.setenv("GRANOLA_MAX_PAGES", "2")
    endless = {"transcript": [{"text": "x"}], "hasMore": True, "cursor": "c"}
    with patch.object(client_obj, "_get", return_value=endless) as g:
        out = client_obj.get_transcript("not_1")
    assert g.call_count == 2
    assert out["truncated"] is True


# ─── folders / webhooks ───────────────────────────────────────────────────────

def test_list_folders_pages_until_exhausted(client_obj):
    pages = [
        {"folders": [{"id": "fol_a", "name": "Alpha"}], "hasMore": True, "cursor": "c1"},
        {"folders": [{"id": "fol_b", "name": "Beta"}], "hasMore": False, "cursor": None},
    ]
    calls = []
    with patch.object(client_obj, "_get", side_effect=lambda p, params=None: (calls.append(params), pages[len(calls) - 1])[1]):
        out = client_obj.list_folders()
    assert [f["name"] for f in out["rows"]] == ["Alpha", "Beta"]


def test_list_webhook_endpoints_returns_rows(client_obj):
    with patch.object(client_obj, "_get", return_value={"webhook_endpoints": [{"id": "whe_1"}]}) as g:
        out = client_obj.list_webhook_endpoints()
    assert out["rows"] == [{"id": "whe_1"}]
    assert g.call_args.args[0] == "/v1/webhook-endpoints"


# ─── folder name resolution ───────────────────────────────────────────────────

def test_resolve_folder_id_passes_through_explicit_id(client_obj):
    with patch.object(client_obj, "list_folders") as lf:
        assert client_obj.resolve_folder_id("fol_CdrBi9432jq7Vx") == "fol_CdrBi9432jq7Vx"
    lf.assert_not_called()


def test_resolve_folder_id_matches_name_case_insensitively(client_obj):
    folders = {"rows": [{"id": "fol_a", "name": "Opencall-Guru"}, {"id": "fol_b", "name": "Other"}]}
    with patch.object(client_obj, "list_folders", return_value=folders):
        assert client_obj.resolve_folder_id("opencall-guru") == "fol_a"


def test_resolve_folder_id_ambiguous_name_raises_usageerror_listing_candidates(client_obj):
    folders = {"rows": [{"id": "fol_a", "name": "Team"}, {"id": "fol_b", "name": "team"}]}
    with patch.object(client_obj, "list_folders", return_value=folders):
        with pytest.raises(UsageError) as ei:
            client_obj.resolve_folder_id("Team")
    assert "fol_a" in str(ei.value) and "fol_b" in str(ei.value)


def test_resolve_folder_id_unknown_name_raises_notfounderror(client_obj):
    with patch.object(client_obj, "list_folders", return_value={"rows": []}):
        with pytest.raises(NotFoundError):
            client_obj.resolve_folder_id("nope")


def test_list_folders_respects_documented_page_size_cap(client_obj):
    """/v1/folders caps page_size at 30 — a larger value is a 400, not a clamp."""
    from h2t_ops.connectors.granola.client import FOLDERS_PAGE_MAX
    assert FOLDERS_PAGE_MAX <= 30
    with patch.object(client_obj, "_get", return_value={"folders": [], "hasMore": False, "cursor": None}) as g:
        client_obj.list_folders()
    assert g.call_args.kwargs["params"]["page_size"] <= 30
