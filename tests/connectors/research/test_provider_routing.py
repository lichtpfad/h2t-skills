from __future__ import annotations

import pytest

from h2t_ops.connectors.research import provider_routing
from h2t_ops.core.errors import UsageError


def test_provider_status_reports_missing_required_exa_key(monkeypatch):
    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    result = provider_routing.provider_status()

    exa_search = [
        item for item in result["providers"]
        if item["provider"] == "exa" and item["capability"] == "search"
    ][0]
    assert result["kind"] == "research_provider_status"
    assert exa_search["configured"] is False
    assert exa_search["missing_secrets"] == ["EXA_API_KEY"]
    assert exa_search["reason"] == "missing_required_secret"


def test_provider_status_marks_direct_and_jina_fetch_available_without_keys(monkeypatch):
    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    result = provider_routing.provider_status(capability="fetch")
    rows = {(item["provider"], item["capability"]): item for item in result["providers"]}

    assert rows[("direct", "fetch")]["configured"] is True
    assert rows[("direct", "fetch")]["reason"] == "available"
    assert rows[("jina", "fetch")]["configured"] is True
    assert rows[("jina", "fetch")]["optional_missing_secrets"] == ["JINA_API_KEY"]
    assert rows[("jina", "fetch")]["reason"] == "available_optional_secret_missing"


def test_select_route_picks_exa_when_key_exists(monkeypatch):
    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: name == "EXA_API_KEY")

    result = provider_routing.select_route("search")

    assert result["kind"] == "research_provider_route"
    assert result["capability"] == "search"
    assert result["selected_provider"] == "exa"
    assert result["configured"] is True


def test_select_route_raises_usage_error_when_required_key_missing(monkeypatch):
    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: False)

    with pytest.raises(UsageError, match="no configured research provider"):
        provider_routing.select_route("answer")


def test_select_route_rejects_unknown_capability():
    with pytest.raises(UsageError, match="unknown research capability"):
        provider_routing.select_route("unknown")
