"""Tests for author_resolve — no network."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from h2t_ops.connectors.research import author_resolve


def test_resolve_via_handle_guess(monkeypatch):
    """If oEmbed confirms a handle guess, return confidence=confirmed."""
    def fake_oembed(video_id: str) -> dict:
        if "Acidbourbon" in video_id or "acidbourbon" in video_id:
            return {"author_name": "Acidbourbon", "title": "TD Tutorial"}
        return {}

    monkeypatch.setattr(author_resolve, "_oembed_channel_validate", fake_oembed)
    monkeypatch.setattr(
        author_resolve,
        "_exa_people_search",
        lambda name, keywords, api_key: None,
    )
    monkeypatch.setattr(
        author_resolve,
        "_alltd_uploader_check",
        lambda name: None,
    )

    result = author_resolve.resolve_author(
        "Acidbourbon",
        api_key="test-key",
        keywords=["TouchDesigner", "POP"],
    )

    assert result["confidence"] == "confirmed"
    assert result["channel_url"] is not None
    assert "Acidbourbon" in result["channel_url"] or "acidbourbon" in result["channel_url"]
    assert any("handle_guess" in step for step in result["resolution_path"])


def test_resolve_via_exa(monkeypatch):
    """If Exa people search returns a channel URL, use it."""
    monkeypatch.setattr(
        author_resolve,
        "_exa_people_search",
        lambda name, keywords, api_key: "https://youtube.com/@testchannel",
    )
    monkeypatch.setattr(author_resolve, "_oembed_channel_validate", lambda vid: {})
    monkeypatch.setattr(author_resolve, "_alltd_uploader_check", lambda name: None)

    result = author_resolve.resolve_author(
        "TestChannel",
        api_key="test-key",
    )

    assert result["confidence"] == "confirmed"
    assert result["channel_url"] == "https://youtube.com/@testchannel"
    assert any("exa_people" in step for step in result["resolution_path"])


def test_resolve_not_found(monkeypatch):
    """Not found is exit 0 with confidence=not_found, not an error."""
    monkeypatch.setattr(author_resolve, "_exa_people_search", lambda *a, **kw: None)
    monkeypatch.setattr(author_resolve, "_oembed_channel_validate", lambda vid: {})
    monkeypatch.setattr(author_resolve, "_alltd_uploader_check", lambda name: None)

    result = author_resolve.resolve_author("GhostAuthor99", api_key="k")

    assert result["confidence"] == "not_found"
    assert result["channel_url"] is None
    assert result["name"] == "GhostAuthor99"


def test_resolve_result_schema(monkeypatch):
    """Result always contains required keys."""
    monkeypatch.setattr(author_resolve, "_exa_people_search", lambda *a, **kw: None)
    monkeypatch.setattr(author_resolve, "_oembed_channel_validate", lambda vid: {})
    monkeypatch.setattr(author_resolve, "_alltd_uploader_check", lambda name: None)

    result = author_resolve.resolve_author("X", api_key="k")

    for key in ("name", "channel_url", "author_confirmed", "resolution_path", "confidence"):
        assert key in result, f"missing key: {key}"


def test_resolve_exa_provider_error_returns_error_confidence(monkeypatch):
    """ProviderError/AuthError from Exa returns confidence=error, not not_found."""
    from h2t_ops.core.errors import ProviderError

    def raise_provider_error(name, keywords, api_key):
        raise ProviderError("Exa API unavailable", details={})

    monkeypatch.setattr(author_resolve, "_exa_people_search", raise_provider_error)

    result = author_resolve.resolve_author("AnyAuthor", api_key="k")

    assert result["confidence"] == "error"
    assert "provider error" in result["resolution_path"][0]
    assert result["channel_url"] is None
