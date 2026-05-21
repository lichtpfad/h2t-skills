"""Provider-level tests for the research fetch runtime."""
from __future__ import annotations

import io
import json
import os
import time
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from h2t_ops.connectors.research import fetch


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fetch"


def _load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _make_http_response(
    body: bytes,
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
    url: str = "https://example.com/x",
):
    headers = headers or {"Content-Type": "text/html; charset=utf-8"}
    resp = MagicMock()
    resp.read.return_value = body
    resp.status = status
    resp.headers = headers
    resp.geturl.return_value = url
    resp.__enter__ = lambda self_: self_
    resp.__exit__ = lambda self_, *a: None
    return resp


def _http_error(
    code: int,
    body: bytes = b"",
    headers: dict[str, str] | None = None,
    url: str = "https://example.com/x",
):
    return urllib.error.HTTPError(
        url=url, code=code, msg="err", hdrs=headers or {}, fp=io.BytesIO(body),
    )


def test_build_fetch_envelope_minimal_failed():
    env = fetch.build_fetch_envelope(
        status="FAILED",
        url="https://example.com/x",
        final_url=None,
        provider_used="none",
        content_type="unknown",
        content_gate="none",
        title=None,
        body_markdown="",
        body_text="",
        body_chars=0,
        links=[],
        attempts=[],
        providers_skipped={},
        reason_for_failed="all_providers_failed",
        reason_for_degraded=None,
        raw_html_path=None,
        site=None,
        canonical_url=None,
        lang=None,
        detected_reason=None,
        user_agent="ua/test",
    )
    assert env["status"] == "FAILED"
    assert env["url"] == "https://example.com/x"
    assert env["provider_used"] == "none"
    assert env["meta"]["primary_engine"] == "fetch_ladder"
    assert env["meta"]["envelope_version"] == "1"
    assert env["meta"]["fetch_envelope_version"] == "1"
    assert env["telemetry"]["total_latency_ms"] == 0
    assert env["telemetry"]["reason_for_failed"] == "all_providers_failed"
    assert env["metadata"]["raw_html_path"] is None


def test_build_fetch_envelope_ok_with_attempts_sums_latency():
    attempts = [
        {"provider": "direct", "http": 403, "latency_ms": 100, "error": "fetch_http_4xx_nonretryable"},
        {"provider": "jina", "http": 200, "latency_ms": 250, "error": None},
    ]
    env = fetch.build_fetch_envelope(
        status="OK",
        url="https://example.com/x",
        final_url="https://example.com/x",
        provider_used="jina",
        content_type="article",
        content_gate="none",
        title="Hello",
        body_markdown="# Hello\n\nWorld",
        body_text="Hello\n\nWorld",
        body_chars=12,
        links=[],
        attempts=attempts,
        providers_skipped={"playwright": "not_configured_stub"},
        reason_for_failed=None,
        reason_for_degraded=None,
        raw_html_path=None,
        site="example.com",
        canonical_url=None,
        lang=None,
        detected_reason=None,
        user_agent="ua/test",
    )
    assert env["telemetry"]["total_latency_ms"] == 350
    assert env["telemetry"]["providers_skipped"] == ["playwright"]
    assert env["telemetry"]["providers_skipped_reason"] == {"playwright": "not_configured_stub"}
    assert env["provider_used"] == "jina"
    assert env["title"] == "Hello"


def test_provider_exceptions_have_required_attrs():
    transient = fetch.ProviderTransientError(
        "5xx", provider="direct", http_status=503, latency_ms=100,
    )
    assert transient.provider == "direct"
    assert transient.http_status == 503
    assert transient.latency_ms == 100

    permanent = fetch.ProviderPermanentError(
        "4xx", provider="direct", http_status=403, latency_ms=50,
    )
    assert permanent.http_status == 403

    gated = fetch.ProviderHardGate(
        "auth", provider="direct", gate="login_required", latency_ms=10,
    )
    assert gated.gate == "login_required"

    not_configured = fetch.ProviderNotConfigured("stub", provider="firecrawl")
    assert not_configured.provider == "firecrawl"


def test_provider_result_dataclass_fields():
    result = fetch.ProviderResult(
        provider="direct",
        http_status=200,
        latency_ms=120,
        final_url="https://example.com/x",
        title="T",
        body_markdown="# T\n",
        body_text="T",
        body_chars=1,
        links=[],
        canonical_url=None,
        lang=None,
        raw_html="<html></html>",
    )
    assert result.provider == "direct"
    assert result.body_chars == 1
    assert result.raw_html == "<html></html>"


def test_inline_extract_public_article():
    html = _load_fixture("public_article.html")
    title, body_markdown, body_text, links, canonical, lang = fetch._inline_extract(
        html, base_url="https://example.com/pops-intro",
    )
    assert title and "POPs in TouchDesigner" in title
    assert "POPs are the new particle context" in body_text
    assert "Attribute lifecycle" in body_text
    assert "POPs in TouchDesigner" in body_markdown
    assert canonical == "https://example.com/pops-intro"
    assert lang == "en"
    assert any(link["href"].endswith("/glsl-pops") for link in links)
    assert "/static/app.js" not in body_text


def test_inline_baseline_works_without_trafilatura(monkeypatch):
    monkeypatch.setattr(fetch, "_TRAFILATURA_AVAILABLE", False)
    fetch._reset_trafilatura_warned_for_tests()
    title, _, body_text, _, _, _ = fetch._extract_with_optional_uplift(
        _load_fixture("public_article.html"),
        base_url="https://example.com/x",
    )
    assert title and "POPs in TouchDesigner" in title
    assert "POPs are the new particle context" in body_text


def test_unicode_article_extracts_safely():
    html = _load_fixture("non_ascii_article.html").encode("utf-8")
    provider = fetch.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html,
            url="https://example.com/ru",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
        result = provider.fetch("https://example.com/ru", timeout_ms=15000, user_agent="ua/test")
    assert "Атрибуты POP" in result.title
    assert "Жизненный цикл атрибута" in result.body_text


def test_direct_provider_happy_path_extracts_article():
    provider = fetch.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            _load_fixture("public_article.html").encode("utf-8"),
            url="https://example.com/pops-intro",
        )
        result = provider.fetch(
            "https://example.com/pops-intro", timeout_ms=15000, user_agent="ua/test",
        )
    assert result.provider == "direct"
    assert result.http_status == 200
    assert result.title and "POPs in TouchDesigner" in result.title
    assert "POPs are the new particle context" in result.body_text
    assert result.body_chars > 200
    assert result.final_url == "https://example.com/pops-intro"
    assert result.canonical_url == "https://example.com/pops-intro"
    assert result.lang == "en"
    assert result.raw_html and "<html" in result.raw_html


def test_direct_provider_4xx_raises_permanent():
    provider = fetch.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(403)
        with pytest.raises(fetch.ProviderPermanentError) as exc:
            provider.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")
    assert exc.value.http_status == 403
    assert exc.value.provider == "direct"


def test_direct_provider_5xx_raises_transient():
    provider = fetch.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(503)
        with pytest.raises(fetch.ProviderTransientError) as exc:
            provider.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")
    assert exc.value.http_status == 503


def test_direct_provider_429_raises_transient():
    provider = fetch.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(429)
        with pytest.raises(fetch.ProviderTransientError):
            provider.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")


def test_direct_provider_urlerror_raises_transient():
    provider = fetch.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        with pytest.raises(fetch.ProviderTransientError) as exc:
            provider.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")
    assert exc.value.http_status is None
    assert exc.value.latency_ms >= 0


def test_direct_provider_401_with_www_authenticate_is_gated():
    provider = fetch.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(401, headers={"WWW-Authenticate": 'Bearer realm="api"'})
        with pytest.raises(fetch.ProviderHardGate) as exc:
            provider.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")
    assert exc.value.gate == "login_required"


def test_direct_provider_403_without_auth_header_is_permanent_not_gated():
    provider = fetch.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(403, headers={})
        with pytest.raises(fetch.ProviderPermanentError):
            provider.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")


def test_direct_provider_403_with_login_wall_body_is_gated():
    provider = fetch.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(
            403,
            body=_load_fixture("login_wall.html").encode("utf-8"),
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
        with pytest.raises(fetch.ProviderHardGate) as exc:
            provider.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")
    assert exc.value.gate == "login_required"
    assert exc.value.http_status == 403


def test_direct_provider_403_with_paywall_body_is_gated():
    provider = fetch.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(
            403,
            body=_load_fixture("paywall.html").encode("utf-8"),
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
        with pytest.raises(fetch.ProviderHardGate) as exc:
            provider.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")
    assert exc.value.gate == "paid"
    assert exc.value.http_status == 403


def test_direct_provider_final_url_after_redirect():
    provider = fetch.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            _load_fixture("public_article.html").encode("utf-8"),
            url="https://www.example.com/pops-intro",
        )
        result = provider.fetch(
            "http://example.com/pops-intro", timeout_ms=15000, user_agent="ua/test",
        )
    assert result.final_url == "https://www.example.com/pops-intro"


def test_detect_js_shell_true_for_spa_skeleton():
    assert fetch._detect_js_shell(html=_load_fixture("js_shell.html"), body_text="") is True


def test_detect_login_wall_true_for_login_form():
    assert fetch._detect_login_wall(
        html=_load_fixture("login_wall.html"),
        final_url="https://example.com/article/x",
    ) is True


def test_detect_paywall_true_for_dom_token():
    assert fetch._detect_paywall(html=_load_fixture("paywall.html"), site="example.com") is True


def test_classify_content_type_article():
    html = _load_fixture("public_article.html")
    _, _, body_text, _, _, _ = fetch._inline_extract(html, base_url="https://x/")
    content_type, gate = fetch._classify_content(
        html=html,
        body_text=body_text,
        final_url="https://example.com/x",
        site="example.com",
        min_body_chars=200,
    )
    assert content_type == "article"
    assert gate == "none"


def test_classify_content_type_short_body():
    html = _load_fixture("short_body.html")
    _, _, body_text, _, _, _ = fetch._inline_extract(html, base_url="https://x/")
    content_type, gate = fetch._classify_content(
        html=html,
        body_text=body_text,
        final_url="https://example.com/x",
        site="example.com",
        min_body_chars=200,
    )
    assert content_type == "short_body"
    assert gate == "none"


def test_classify_content_type_js_shell():
    content_type, gate = fetch._classify_content(
        html=_load_fixture("js_shell.html"),
        body_text="",
        final_url="https://example.com/x",
        site="example.com",
        min_body_chars=200,
    )
    assert content_type == "js_shell"
    assert gate == "none"


def test_classify_content_type_gated_login():
    html = _load_fixture("login_wall.html")
    _, _, body_text, _, _, _ = fetch._inline_extract(html, base_url="https://x/")
    content_type, gate = fetch._classify_content(
        html=html,
        body_text=body_text,
        final_url="https://example.com/article/x",
        site="example.com",
        min_body_chars=200,
    )
    assert content_type == "gated"
    assert gate == "login_required"


def test_classify_content_type_gated_paid():
    html = _load_fixture("paywall.html")
    _, _, body_text, _, _, _ = fetch._inline_extract(html, base_url="https://x/")
    content_type, gate = fetch._classify_content(
        html=html,
        body_text=body_text,
        final_url="https://example.com/x",
        site="example.com",
        min_body_chars=200,
    )
    assert content_type == "gated"
    assert gate == "paid"


def test_detect_homepage_redirect_true_for_alltd_pattern():
    assert fetch._detect_homepage_redirect(
        "https://alltd.org/glsl-for-pops-lesson-0-introduction/",
        "https://www.alltd.org/",
    ) is True


def test_jina_provider_happy_path_extracts_markdown():
    provider = fetch.JinaProvider()
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        return _make_http_response(
            _load_fixture("public_article_jina.md").encode("utf-8"),
            url="https://r.jina.ai/https://example.com/pops-intro",
            headers={"Content-Type": "text/markdown; charset=utf-8"},
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = provider.fetch(
            "https://example.com/pops-intro", timeout_ms=20000, user_agent="ua/test",
        )
    assert result.provider == "jina"
    assert result.title == "POPs in TouchDesigner — Introduction"
    assert "POPs are the new particle context" in result.body_text
    assert result.body_chars > 100
    assert str(captured["url"]).startswith("https://r.jina.ai/")
    assert not any(key.lower() == "authorization" for key in captured["headers"])


def test_jina_provider_passes_authorization_when_key_set(monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "secret-test-key")
    provider = fetch.JinaProvider()
    captured: dict[str, dict[str, str]] = {}

    def fake_urlopen(req, timeout):
        captured["headers"] = dict(req.header_items())
        return _make_http_response(
            _load_fixture("public_article_jina.md").encode("utf-8"),
            url="https://r.jina.ai/https://example.com/pops-intro",
            headers={"Content-Type": "text/markdown; charset=utf-8"},
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        provider.fetch("https://example.com/pops-intro", timeout_ms=20000, user_agent="ua/test")
    assert any(
        key.lower() == "authorization" and value == "Bearer secret-test-key"
        for key, value in captured["headers"].items()
    )


def test_jina_provider_uses_configured_endpoint():
    provider = fetch.JinaProvider(config={"endpoint": "https://reader.example/custom"})
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        return _make_http_response(
            _load_fixture("public_article_jina.md").encode("utf-8"),
            url="https://reader.example/custom/https://example.com/pops-intro",
            headers={"Content-Type": "text/markdown; charset=utf-8"},
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        provider.fetch("https://example.com/pops-intro", timeout_ms=20000, user_agent="ua/test")
    assert captured["url"] == "https://reader.example/custom/https://example.com/pops-intro"


def test_jina_provider_5xx_transient():
    provider = fetch.JinaProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(503)
        with pytest.raises(fetch.ProviderTransientError):
            provider.fetch("https://example.com/x", timeout_ms=20000, user_agent="ua/test")


def test_jina_provider_4xx_permanent():
    provider = fetch.JinaProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(404)
        with pytest.raises(fetch.ProviderPermanentError):
            provider.fetch("https://example.com/x", timeout_ms=20000, user_agent="ua/test")


def test_jina_provider_urlerror_transient():
    provider = fetch.JinaProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("dns failure")
        with pytest.raises(fetch.ProviderTransientError):
            provider.fetch("https://example.com/x", timeout_ms=20000, user_agent="ua/test")


@pytest.mark.parametrize("name", ["playwright", "crawl4ai", "firecrawl", "browserless"])
def test_stub_providers_not_configured_and_fetch_raises(name, monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "x")
    monkeypatch.setenv("BROWSERLESS_TOKEN", "x")
    provider_class = {
        "playwright": fetch.PlaywrightProvider,
        "crawl4ai": fetch.Crawl4AIProvider,
        "firecrawl": fetch.FirecrawlProvider,
        "browserless": fetch.BrowserlessProvider,
    }[name]
    provider = provider_class()
    assert provider.name == name
    assert provider.is_configured(env=dict(os.environ), config={}) is False
    with pytest.raises(fetch.ProviderNotConfigured):
        provider.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")


def test_load_config_returns_defaults_when_file_missing(tmp_path):
    config = fetch.load_config(tmp_path / "nope.json")
    assert config["providers"]["direct"]["enabled"] is True
    assert config["providers"]["jina"]["enabled"] is True
    assert config["providers"]["playwright"]["enabled"] is False
    assert config["ladder"]["per_provider_timeout_ms"] == 15000
    assert config["ladder"]["cumulative_timeout_ms"] == 60000
    assert config["ladder"]["min_body_chars"] == 200


def test_load_config_overrides_with_user_file(tmp_path):
    config_path = tmp_path / "fetch_providers.json"
    config_path.write_text(
        json.dumps({
            "providers": {"jina": {"enabled": False}},
            "ladder": {"min_body_chars": 500},
        }),
        encoding="utf-8",
    )
    config = fetch.load_config(config_path)
    assert config["providers"]["jina"]["enabled"] is False
    assert config["providers"]["direct"]["enabled"] is True
    assert config["ladder"]["min_body_chars"] == 500
    assert config["ladder"]["per_provider_timeout_ms"] == 15000


def test_ladder_single_provider_ok_returns_envelope():
    html = _load_fixture("public_article.html").encode("utf-8")
    config = fetch.load_config(None)
    config["providers"]["jina"]["enabled"] = False
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/pops-intro",
        )
        env = fetch.fetch_via_ladder(
            url="https://example.com/pops-intro",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
            min_body_chars=200,
        )
    assert env["status"] == "OK"
    assert env["provider_used"] == "direct"
    assert env["telemetry"]["attempts"][0]["provider"] == "direct"
    assert env["telemetry"]["attempts"][0]["error"] is None
    assert env["content_type"] == "article"
    assert env["title"] == "POPs in TouchDesigner — Introduction"
    assert env["body_chars"] > 200
    assert env["telemetry"]["providers_skipped_reason"]["jina"] == "disabled_in_config"


def test_ladder_direct_403_falls_through_to_jina():
    config = fetch.load_config(None)
    jina_md = _load_fixture("public_article_jina.md").encode("utf-8")

    def fake_urlopen(req, timeout):
        if req.full_url.startswith("https://r.jina.ai/"):
            return _make_http_response(
                jina_md,
                url="https://r.jina.ai/https://example.com/x",
                headers={"Content-Type": "text/markdown; charset=utf-8"},
            )
        raise _http_error(403, headers={})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        env = fetch.fetch_via_ladder(
            url="https://example.com/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    assert env["status"] == "OK"
    assert env["provider_used"] == "jina"
    assert env["content_gate"] == "none"
    assert env["telemetry"]["attempts"][0]["provider"] == "direct"
    assert env["telemetry"]["attempts"][0]["error"] == "fetch_http_4xx_nonretryable"
    assert env["telemetry"]["attempts"][1]["provider"] == "jina"
    assert env["telemetry"]["attempts"][1]["error"] is None


def test_ladder_gated_403_body_does_not_fall_through_to_jina():
    config = fetch.load_config(None)
    calls = {"jina": 0}

    def fake_urlopen(req, timeout):
        if req.full_url.startswith("https://r.jina.ai/"):
            calls["jina"] += 1
            return _make_http_response(
                _load_fixture("public_article_jina.md").encode("utf-8"),
                url="https://r.jina.ai/https://example.com/x",
                headers={"Content-Type": "text/markdown; charset=utf-8"},
            )
        raise _http_error(
            403,
            body=_load_fixture("login_wall.html").encode("utf-8"),
            headers={"Content-Type": "text/html; charset=utf-8"},
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        env = fetch.fetch_via_ladder(
            url="https://example.com/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    assert env["status"] == "FAILED"
    assert env["content_gate"] == "login_required"
    assert calls["jina"] == 0
    attempts = env["telemetry"]["attempts"]
    assert len(attempts) == 1
    assert attempts[0]["provider"] == "direct"
    assert attempts[0]["http"] == 403
    assert attempts[0]["error"] == "fetch_gated_login_required"


def test_ladder_login_wall_short_circuits_does_not_call_jina():
    config = fetch.load_config(None)
    html = _load_fixture("login_wall.html").encode("utf-8")
    calls = {"saw_jina": False}

    def fake_urlopen(req, timeout):
        if req.full_url.startswith("https://r.jina.ai/"):
            calls["saw_jina"] = True
        return _make_http_response(html, url="https://example.com/article/x")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        env = fetch.fetch_via_ladder(
            url="https://example.com/article/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    assert env["status"] == "FAILED"
    assert env["content_gate"] == "login_required"
    assert calls["saw_jina"] is False


def test_ladder_paywall_short_circuits():
    config = fetch.load_config(None)
    html = _load_fixture("paywall.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/article/x",
        )
        env = fetch.fetch_via_ladder(
            url="https://example.com/article/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    assert env["status"] == "FAILED"
    assert env["content_gate"] == "paid"


def test_ladder_all_active_providers_fail_returns_failed():
    config = fetch.load_config(None)
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(503)
        env = fetch.fetch_via_ladder(
            url="https://example.com/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    assert env["status"] == "FAILED"
    assert env["provider_used"] == "none"
    providers_attempted = [a["provider"] for a in env["telemetry"]["attempts"]]
    assert providers_attempted == ["direct", "jina"]
    assert env["telemetry"]["reason_for_failed"] == "all_providers_failed"


def test_ladder_degraded_picks_best_candidate_by_body_chars():
    config = fetch.load_config(None)
    short_html = _load_fixture("short_body.html").encode("utf-8")
    jina_short = b"Title: Tiny\n\nMarkdown Content:\nHi.\n"

    def fake_urlopen(req, timeout):
        if req.full_url.startswith("https://r.jina.ai/"):
            return _make_http_response(
                jina_short,
                url="https://r.jina.ai/https://example.com/x",
                headers={"Content-Type": "text/markdown"},
            )
        return _make_http_response(short_html, url="https://example.com/x")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        env = fetch.fetch_via_ladder(
            url="https://example.com/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    assert env["status"] == "DEGRADED"
    assert env["provider_used"] in ("direct", "jina")
    assert env["telemetry"]["reason_for_degraded"] is not None


def test_ladder_explicit_direct_does_not_fallback_to_jina():
    config = fetch.load_config(None)
    saw = {"jina": False}

    def fake_urlopen(req, timeout):
        if req.full_url.startswith("https://r.jina.ai/"):
            saw["jina"] = True
        raise _http_error(403)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        env = fetch.fetch_via_ladder(
            url="https://example.com/x",
            provider_choice="direct",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    assert env["status"] == "FAILED"
    assert saw["jina"] is False
    providers_attempted = [a["provider"] for a in env["telemetry"]["attempts"]]
    assert providers_attempted == ["direct"]


def test_ladder_stubs_skipped_with_reason_in_auto():
    config = fetch.load_config(None)
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        env = fetch.fetch_via_ladder(
            url="https://example.com/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    skipped_reason = env["telemetry"]["providers_skipped_reason"]
    for stub in ("playwright", "crawl4ai", "firecrawl", "browserless"):
        assert skipped_reason.get(stub) == "not_configured_stub"


def test_ladder_jina_disabled_skipped_in_config():
    config = fetch.load_config(None)
    config["providers"]["jina"]["enabled"] = False
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        env = fetch.fetch_via_ladder(
            url="https://example.com/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    assert env["telemetry"]["providers_skipped_reason"]["jina"] == "disabled_in_config"
    assert "jina" not in [a["provider"] for a in env["telemetry"]["attempts"]]


def test_ladder_cumulative_timeout_skips_remaining():
    config = fetch.load_config(None)
    config["ladder"]["cumulative_timeout_ms"] = 1
    html = _load_fixture("short_body.html").encode("utf-8")

    def fake_urlopen(req, timeout):
        time.sleep(0.005)
        return _make_http_response(html, url="https://example.com/x")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        env = fetch.fetch_via_ladder(
            url="https://example.com/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    assert env["telemetry"]["providers_skipped_reason"].get("jina") == "cumulative_timeout_exhausted"


def test_ladder_keep_raw_writes_raw_file(tmp_path):
    config = fetch.load_config(None)
    raw_path = tmp_path / "raw" / "article.raw.html"

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            _load_fixture("public_article.html").encode("utf-8"),
            url="https://example.com/pops-intro",
        )
        env = fetch.fetch_via_ladder(
            url="https://example.com/pops-intro",
            provider_choice="direct",
            config=config,
            user_agent="ua/test",
            keep_raw=True,
            output_paths={"raw_html": raw_path},
        )

    assert env["status"] == "OK"
    assert env["metadata"]["raw_html_path"] == str(raw_path)
    assert raw_path.is_file()
    assert "POPs in TouchDesigner" in raw_path.read_text(encoding="utf-8")


def test_ladder_uses_jina_provider_config_for_endpoint_and_timeout():
    config = fetch.load_config(None)
    config["ladder"]["default_order"] = ["jina"]
    config["ladder"]["per_provider_timeout_ms"] = 1
    config["providers"]["jina"]["endpoint"] = "https://reader.example/jina"
    config["providers"]["jina"]["timeout_ms"] = 24680
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        return _make_http_response(
            _load_fixture("public_article_jina.md").encode("utf-8"),
            url="https://reader.example/jina/https://example.com/pops-intro",
            headers={"Content-Type": "text/markdown; charset=utf-8"},
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        env = fetch.fetch_via_ladder(
            url="https://example.com/pops-intro",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )

    assert env["status"] == "OK"
    assert captured["url"] == "https://reader.example/jina/https://example.com/pops-intro"
    assert captured["timeout"] == 24.68


def test_ladder_alltd_collapse_falls_through_to_jina_then_degraded():
    config = fetch.load_config(None)
    homepage_html = (
        "<html><body><article>"
        "<h1>AllTouchDesigner</h1>"
        "<p>" + ("Welcome to our tutorial library covering GLSL, POPs, CHOPs. " * 20)
        + "</p></article></body></html>"
    ).encode("utf-8")
    jina_homepage_md = (
        "Title: AllTouchDesigner\n\n"
        "URL Source: https://www.alltd.org/\n\n"
        "Markdown Content:\n"
        + ("Welcome to AllTouchDesigner homepage listing. " * 30)
    ).encode("utf-8")

    def fake_urlopen(req, timeout):
        if req.full_url.startswith("https://r.jina.ai/"):
            return _make_http_response(
                jina_homepage_md,
                url="https://r.jina.ai/https://alltd.org/glsl-for-pops-lesson-0/",
                headers={"Content-Type": "text/markdown; charset=utf-8"},
            )
        return _make_http_response(
            homepage_html,
            url="https://www.alltd.org/",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        env = fetch.fetch_via_ladder(
            url="https://alltd.org/glsl-for-pops-lesson-0/",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    assert env["status"] == "DEGRADED"
    assert env["content_type"] == "redirect_collapsed"
    assert env["telemetry"]["reason_for_degraded"] == "redirect_collapsed_to_homepage"
    attempts = env["telemetry"]["attempts"]
    direct_attempt = next(a for a in attempts if a["provider"] == "direct")
    jina_attempt = next(a for a in attempts if a["provider"] == "jina")
    assert direct_attempt["error"] == "fetch_redirect_collapsed"
    assert jina_attempt["error"] == "fetch_redirect_collapsed"


def test_ladder_alltd_collapse_recovers_via_jina():
    config = fetch.load_config(None)
    homepage_html = (
        "<html><body><article>"
        "<h1>AllTouchDesigner</h1>"
        "<p>" + ("Welcome to our tutorial library covering GLSL, POPs, CHOPs. " * 20)
        + "</p></article></body></html>"
    ).encode("utf-8")
    jina_real_article = (
        "Title: GLSL for POPs - Lesson 0\n\n"
        "URL Source: https://alltd.org/glsl-for-pops-lesson-0/\n\n"
        "Markdown Content:\n"
        "# GLSL for POPs - Lesson 0\n\n"
        + ("Real lesson content discussing GLSL POPs setup in detail. " * 25)
    ).encode("utf-8")

    def fake_urlopen(req, timeout):
        if req.full_url.startswith("https://r.jina.ai/"):
            return _make_http_response(
                jina_real_article,
                url="https://r.jina.ai/https://alltd.org/glsl-for-pops-lesson-0/",
                headers={"Content-Type": "text/markdown; charset=utf-8"},
            )
        return _make_http_response(
            homepage_html,
            url="https://www.alltd.org/",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        env = fetch.fetch_via_ladder(
            url="https://alltd.org/glsl-for-pops-lesson-0/",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    assert env["status"] == "OK"
    assert env["provider_used"] == "jina"
    attempts = env["telemetry"]["attempts"]
    assert attempts[0]["provider"] == "direct"
    assert attempts[0]["error"] == "fetch_redirect_collapsed"
    assert attempts[1]["provider"] == "jina"
    assert attempts[1]["error"] is None
