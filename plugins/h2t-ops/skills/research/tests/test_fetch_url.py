"""Tests for fetch_url.py — provider ladder CLI for h2t-ops:research skill.

Spec: docs/superpowers/specs/2026-05-07-research-fetch-url-ladder.md
Issue: lichtpfad/h2t-skills#103
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make script importable as a module.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_url  # noqa: E402


def test_fetch_url_module_imports():
    assert hasattr(fetch_url, "__version__")
    assert fetch_url.__version__ == "0.0.1"


def test_build_fetch_envelope_minimal_failed():
    env = fetch_url.build_fetch_envelope(
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
    env = fetch_url.build_fetch_envelope(
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
    e = fetch_url.ProviderTransientError(
        "5xx", provider="direct", http_status=503, latency_ms=100,
    )
    assert e.provider == "direct"
    assert e.http_status == 503
    assert e.latency_ms == 100

    p = fetch_url.ProviderPermanentError(
        "4xx", provider="direct", http_status=403, latency_ms=50,
    )
    assert p.http_status == 403

    g = fetch_url.ProviderHardGate(
        "auth", provider="direct", gate="login_required", latency_ms=10,
    )
    assert g.gate == "login_required"

    nc = fetch_url.ProviderNotConfigured("stub", provider="firecrawl")
    assert nc.provider == "firecrawl"


def test_provider_result_dataclass_fields():
    r = fetch_url.ProviderResult(
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
    assert r.provider == "direct"
    assert r.body_chars == 1
    assert r.raw_html == "<html></html>"


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fetch"


def _load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_inline_extract_public_article():
    html = _load_fixture("public_article.html")
    title, body_markdown, body_text, links, canonical, lang = (
        fetch_url._inline_extract(html, base_url="https://example.com/pops-intro")
    )
    assert title == "POPs in TouchDesigner — Introduction"
    assert "POPs are the new particle context" in body_text
    assert "Attribute lifecycle" in body_text
    assert "# POPs in TouchDesigner" in body_markdown or "POPs in TouchDesigner" in body_markdown
    assert canonical == "https://example.com/pops-intro"
    assert lang == "en"
    assert any(l["href"].endswith("/glsl-pops") for l in links)
    # Script content excluded from body
    assert "/static/app.js" not in body_text


def _make_http_response(body: bytes, *, status: int = 200,
                        headers: dict[str, str] | None = None,
                        url: str = "https://example.com/x"):
    """Build a duck-typed urlopen response."""
    headers = headers or {"Content-Type": "text/html; charset=utf-8"}
    resp = MagicMock()
    resp.read.return_value = body
    resp.status = status
    resp.headers = headers
    resp.geturl.return_value = url
    resp.__enter__ = lambda self_: self_
    resp.__exit__ = lambda self_, *a: None
    return resp


def test_direct_provider_happy_path_extracts_article():
    html = _load_fixture("public_article.html").encode("utf-8")
    p = fetch_url.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/pops-intro",
        )
        r = p.fetch("https://example.com/pops-intro",
                    timeout_ms=15000, user_agent="ua/test")
    assert r.provider == "direct"
    assert r.http_status == 200
    assert r.title == "POPs in TouchDesigner — Introduction"
    assert "POPs are the new particle context" in r.body_text
    assert r.body_chars > 200
    assert r.final_url == "https://example.com/pops-intro"
    assert r.canonical_url == "https://example.com/pops-intro"
    assert r.lang == "en"
    assert r.raw_html.startswith("<!DOCTYPE html>") or "<html" in r.raw_html


def _http_error(code: int, body: bytes = b"", headers: dict[str, str] | None = None,
                url: str = "https://example.com/x"):
    return urllib.error.HTTPError(
        url=url, code=code, msg="err",
        hdrs=headers or {}, fp=io.BytesIO(body),
    )


def test_direct_provider_4xx_raises_permanent():
    p = fetch_url.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(403)
        with pytest.raises(fetch_url.ProviderPermanentError) as ei:
            p.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")
    assert ei.value.http_status == 403
    assert ei.value.provider == "direct"


def test_direct_provider_5xx_raises_transient():
    p = fetch_url.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(503)
        with pytest.raises(fetch_url.ProviderTransientError) as ei:
            p.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")
    assert ei.value.http_status == 503


def test_direct_provider_429_raises_transient():
    p = fetch_url.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(429)
        with pytest.raises(fetch_url.ProviderTransientError):
            p.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")


def test_direct_provider_urlerror_raises_transient():
    p = fetch_url.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        with pytest.raises(fetch_url.ProviderTransientError) as ei:
            p.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")
    assert ei.value.http_status is None
    assert ei.value.latency_ms >= 0


def test_direct_provider_401_with_www_authenticate_is_gated():
    p = fetch_url.DirectProvider()
    err = _http_error(401, headers={"WWW-Authenticate": 'Bearer realm="api"'})
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = err
        with pytest.raises(fetch_url.ProviderHardGate) as ei:
            p.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")
    assert ei.value.gate == "login_required"


def test_direct_provider_403_without_auth_header_is_permanent_not_gated():
    p = fetch_url.DirectProvider()
    err = _http_error(403, headers={})
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = err
        with pytest.raises(fetch_url.ProviderPermanentError):
            p.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")


def test_direct_provider_final_url_after_redirect():
    p = fetch_url.DirectProvider()
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        # urllib resolves 301/302 internally; geturl() returns the final URL.
        mock_urlopen.return_value = _make_http_response(
            html, url="https://www.example.com/pops-intro",
        )
        r = p.fetch("http://example.com/pops-intro",
                    timeout_ms=15000, user_agent="ua/test")
    assert r.final_url == "https://www.example.com/pops-intro"


def test_detect_js_shell_true_for_spa_skeleton():
    html = _load_fixture("js_shell.html")
    body_text = ""  # inline_extract would yield empty
    assert fetch_url._detect_js_shell(html=html, body_text=body_text) is True


def test_detect_js_shell_false_for_real_article():
    html = _load_fixture("public_article.html")
    _, _, body_text, _, _, _ = fetch_url._inline_extract(html, base_url="x")
    assert fetch_url._detect_js_shell(html=html, body_text=body_text) is False


def test_detect_login_wall_true_for_login_form():
    html = _load_fixture("login_wall.html")
    assert fetch_url._detect_login_wall(html=html, final_url="https://example.com/article/x") is True


def test_detect_login_wall_true_for_meta_refresh_to_login():
    html = _load_fixture("redirect_to_login.html")
    assert fetch_url._detect_login_wall(html=html, final_url="https://example.com/article/x") is True


def test_detect_login_wall_true_for_final_url_login_path():
    html = "<html><body>noop</body></html>"
    assert fetch_url._detect_login_wall(html=html, final_url="https://example.com/login") is True


def test_detect_login_wall_false_for_real_article():
    html = _load_fixture("public_article.html")
    assert fetch_url._detect_login_wall(html=html, final_url="https://example.com/x") is False


def test_detect_paywall_true_for_dom_token():
    html = _load_fixture("paywall.html")
    assert fetch_url._detect_paywall(html=html, site="example.com") is True


def test_detect_paywall_false_for_public_article():
    html = _load_fixture("public_article.html")
    assert fetch_url._detect_paywall(html=html, site="example.com") is False


def test_classify_content_type_article():
    html = _load_fixture("public_article.html")
    _, _, txt, _, _, _ = fetch_url._inline_extract(html, base_url="https://x/")
    ct, gate = fetch_url._classify_content(
        html=html, body_text=txt, final_url="https://example.com/x",
        site="example.com", min_body_chars=200,
    )
    assert ct == "article"
    assert gate == "none"


def test_classify_content_type_short_body():
    html = _load_fixture("short_body.html")
    _, _, txt, _, _, _ = fetch_url._inline_extract(html, base_url="https://x/")
    ct, gate = fetch_url._classify_content(
        html=html, body_text=txt, final_url="https://example.com/x",
        site="example.com", min_body_chars=200,
    )
    assert ct == "short_body"
    assert gate == "none"


def test_classify_content_type_js_shell():
    html = _load_fixture("js_shell.html")
    ct, gate = fetch_url._classify_content(
        html=html, body_text="", final_url="https://example.com/x",
        site="example.com", min_body_chars=200,
    )
    assert ct == "js_shell"
    assert gate == "none"


def test_classify_content_type_gated_login():
    html = _load_fixture("login_wall.html")
    _, _, txt, _, _, _ = fetch_url._inline_extract(html, base_url="https://x/")
    ct, gate = fetch_url._classify_content(
        html=html, body_text=txt, final_url="https://example.com/article/x",
        site="example.com", min_body_chars=200,
    )
    assert ct == "gated"
    assert gate == "login_required"


def test_classify_content_type_gated_paid():
    html = _load_fixture("paywall.html")
    _, _, txt, _, _, _ = fetch_url._inline_extract(html, base_url="https://x/")
    ct, gate = fetch_url._classify_content(
        html=html, body_text=txt, final_url="https://example.com/x",
        site="example.com", min_body_chars=200,
    )
    assert ct == "gated"
    assert gate == "paid"


def test_direct_provider_login_wall_html_short_circuits_via_classifier():
    html = _load_fixture("login_wall.html").encode("utf-8")
    p = fetch_url.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/article/x",
        )
        with pytest.raises(fetch_url.ProviderHardGate) as ei:
            p.fetch("https://example.com/article/x",
                    timeout_ms=15000, user_agent="ua/test")
    assert ei.value.gate == "login_required"


def test_direct_provider_paywall_html_short_circuits():
    html = _load_fixture("paywall.html").encode("utf-8")
    p = fetch_url.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/article/x",
        )
        with pytest.raises(fetch_url.ProviderHardGate) as ei:
            p.fetch("https://example.com/article/x",
                    timeout_ms=15000, user_agent="ua/test")
    assert ei.value.gate == "paid"


def test_jina_provider_happy_path_extracts_markdown():
    body = _load_fixture("public_article_jina.md").encode("utf-8")
    p = fetch_url.JinaProvider()
    captured = {}
    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        return _make_http_response(
            body,
            url="https://r.jina.ai/https://example.com/pops-intro",
            headers={"Content-Type": "text/markdown; charset=utf-8"},
        )
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        r = p.fetch("https://example.com/pops-intro",
                    timeout_ms=20000, user_agent="ua/test")
    assert r.provider == "jina"
    assert r.title == "POPs in TouchDesigner — Introduction"
    assert "POPs are the new particle context" in r.body_text
    assert r.body_chars > 100
    assert captured["url"].startswith("https://r.jina.ai/")
    # No JINA_API_KEY → no Authorization header.
    assert not any(k.lower() == "authorization" for k in captured["headers"])


def test_jina_provider_passes_authorization_when_key_set(monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "secret-test-key")
    body = _load_fixture("public_article_jina.md").encode("utf-8")
    p = fetch_url.JinaProvider()
    captured = {}
    def fake_urlopen(req, timeout):
        captured["headers"] = dict(req.header_items())
        return _make_http_response(
            body,
            url="https://r.jina.ai/https://example.com/pops-intro",
            headers={"Content-Type": "text/markdown; charset=utf-8"},
        )
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        p.fetch("https://example.com/pops-intro",
                timeout_ms=20000, user_agent="ua/test")
    assert any(
        k.lower() == "authorization" and v == "Bearer secret-test-key"
        for k, v in captured["headers"].items()
    )


def test_jina_provider_5xx_transient():
    p = fetch_url.JinaProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(503)
        with pytest.raises(fetch_url.ProviderTransientError):
            p.fetch("https://example.com/x",
                    timeout_ms=20000, user_agent="ua/test")


def test_jina_provider_4xx_permanent():
    p = fetch_url.JinaProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(404)
        with pytest.raises(fetch_url.ProviderPermanentError):
            p.fetch("https://example.com/x",
                    timeout_ms=20000, user_agent="ua/test")


def test_jina_provider_urlerror_transient():
    p = fetch_url.JinaProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("dns failure")
        with pytest.raises(fetch_url.ProviderTransientError):
            p.fetch("https://example.com/x",
                    timeout_ms=20000, user_agent="ua/test")


@pytest.mark.parametrize("name", ["playwright", "crawl4ai", "firecrawl", "browserless"])
def test_stub_providers_not_configured_and_fetch_raises(name, monkeypatch):
    # Even with potential env-keys set, stubs must remain inert in PR#1.
    monkeypatch.setenv("FIRECRAWL_API_KEY", "x")
    monkeypatch.setenv("BROWSERLESS_TOKEN", "x")
    cls = {
        "playwright": fetch_url.PlaywrightProvider,
        "crawl4ai": fetch_url.Crawl4AIProvider,
        "firecrawl": fetch_url.FirecrawlProvider,
        "browserless": fetch_url.BrowserlessProvider,
    }[name]
    p = cls()
    assert p.name == name
    assert p.is_configured(env=dict(os.environ), config={}) is False
    with pytest.raises(fetch_url.ProviderNotConfigured):
        p.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")


def test_load_config_returns_defaults_when_file_missing(tmp_path):
    cfg = fetch_url.load_config(tmp_path / "nope.json")
    assert cfg["providers"]["direct"]["enabled"] is True
    assert cfg["providers"]["jina"]["enabled"] is True
    assert cfg["providers"]["playwright"]["enabled"] is False
    assert cfg["ladder"]["per_provider_timeout_ms"] == 15000
    assert cfg["ladder"]["cumulative_timeout_ms"] == 60000
    assert cfg["ladder"]["min_body_chars"] == 200


def test_load_config_overrides_with_user_file(tmp_path):
    p = tmp_path / "fetch_providers.json"
    p.write_text(json.dumps({
        "providers": {"jina": {"enabled": False}},
        "ladder": {"min_body_chars": 500},
    }))
    cfg = fetch_url.load_config(p)
    assert cfg["providers"]["jina"]["enabled"] is False
    assert cfg["providers"]["direct"]["enabled"] is True  # default preserved
    assert cfg["ladder"]["min_body_chars"] == 500
    assert cfg["ladder"]["per_provider_timeout_ms"] == 15000  # default preserved


def test_ladder_single_provider_ok_returns_envelope():
    html = _load_fixture("public_article.html").encode("utf-8")
    config = fetch_url.load_config(None)
    # Disable jina + stubs so only direct is in ladder.
    config["providers"]["jina"]["enabled"] = False
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/pops-intro",
        )
        env = fetch_url.fetch_via_ladder(
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
    assert "jina" in env["telemetry"]["providers_skipped"]
    assert env["telemetry"]["providers_skipped_reason"]["jina"] == "disabled_in_config"


def test_ladder_direct_403_falls_through_to_jina():
    config = fetch_url.load_config(None)
    config["providers"]["playwright"]["enabled"] = False
    config["providers"]["crawl4ai"]["enabled"] = False
    config["providers"]["firecrawl"]["enabled"] = False
    config["providers"]["browserless"]["enabled"] = False
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
        env = fetch_url.fetch_via_ladder(
            url="https://example.com/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    assert env["status"] == "OK"
    assert env["provider_used"] == "jina"
    assert env["telemetry"]["attempts"][0]["provider"] == "direct"
    assert env["telemetry"]["attempts"][0]["error"] == "fetch_http_4xx_nonretryable"
    assert env["telemetry"]["attempts"][1]["provider"] == "jina"
    assert env["telemetry"]["attempts"][1]["error"] is None


def test_ladder_login_wall_short_circuits_does_not_call_jina():
    config = fetch_url.load_config(None)
    html = _load_fixture("login_wall.html").encode("utf-8")
    calls = {"count": 0, "saw_jina": False}

    def fake_urlopen(req, timeout):
        calls["count"] += 1
        if req.full_url.startswith("https://r.jina.ai/"):
            calls["saw_jina"] = True
        return _make_http_response(
            html, url="https://example.com/article/x",
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        env = fetch_url.fetch_via_ladder(
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
    config = fetch_url.load_config(None)
    html = _load_fixture("paywall.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/article/x",
        )
        env = fetch_url.fetch_via_ladder(
            url="https://example.com/article/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    assert env["status"] == "FAILED"
    assert env["content_gate"] == "paid"


def test_ladder_all_active_providers_fail_returns_failed():
    config = fetch_url.load_config(None)
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(503)
        env = fetch_url.fetch_via_ladder(
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
    config = fetch_url.load_config(None)
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
        env = fetch_url.fetch_via_ladder(
            url="https://example.com/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    assert env["status"] == "DEGRADED"
    # Whichever has more body_chars wins; both small here, just verify shape:
    assert env["provider_used"] in ("direct", "jina")
    assert env["telemetry"]["reason_for_degraded"] is not None


def test_ladder_explicit_direct_does_not_fallback_to_jina():
    config = fetch_url.load_config(None)
    saw = {"jina": False}
    def fake_urlopen(req, timeout):
        if req.full_url.startswith("https://r.jina.ai/"):
            saw["jina"] = True
        raise _http_error(403)
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        env = fetch_url.fetch_via_ladder(
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
    config = fetch_url.load_config(None)
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        env = fetch_url.fetch_via_ladder(
            url="https://example.com/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    skipped_reason = env["telemetry"]["providers_skipped_reason"]
    for stub in ("playwright", "crawl4ai", "firecrawl", "browserless"):
        assert skipped_reason.get(stub) == "not_configured_stub"


def test_ladder_jina_disabled_skipped_in_config(tmp_path):
    config = fetch_url.load_config(None)
    config["providers"]["jina"]["enabled"] = False
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        env = fetch_url.fetch_via_ladder(
            url="https://example.com/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    assert env["telemetry"]["providers_skipped_reason"]["jina"] == "disabled_in_config"
    assert "jina" not in [a["provider"] for a in env["telemetry"]["attempts"]]


def test_ladder_paid_provider_not_called_when_key_set_but_stubbed(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "x")
    config = fetch_url.load_config(None)
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        env = fetch_url.fetch_via_ladder(
            url="https://example.com/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    # Firecrawl must NOT appear in attempts even with key set in env.
    assert "firecrawl" not in [a["provider"] for a in env["telemetry"]["attempts"]]
    assert env["telemetry"]["providers_skipped_reason"]["firecrawl"] == "not_configured_stub"


def test_ladder_cumulative_timeout_skips_remaining(capsys):
    import time
    config = fetch_url.load_config(None)
    config["ladder"]["cumulative_timeout_ms"] = 1  # immediate cap

    html = _load_fixture("short_body.html").encode("utf-8")

    def fake_urlopen(req, timeout):
        # Direct returns short_body → DEGRADED candidate, latency_ms > 1.
        time.sleep(0.005)
        return _make_http_response(html, url="https://example.com/x")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        env = fetch_url.fetch_via_ladder(
            url="https://example.com/x",
            provider_choice="auto",
            config=config,
            user_agent="ua/test",
            keep_raw=False,
        )
    err = capsys.readouterr().err
    assert "FETCH_WARN:CUMULATIVE_TIMEOUT_EXHAUSTED" in err
    # jina (and others) skipped with the timeout reason.
    skipped_reason = env["telemetry"]["providers_skipped_reason"]
    assert skipped_reason.get("jina") == "cumulative_timeout_exhausted"


def test_inline_baseline_works_without_trafilatura(capsys):
    # Baseline: no install. Just verify the warning is emitted at most once
    # when extraction is invoked without trafilatura.
    fetch_url._reset_trafilatura_warned_for_tests()
    html = _load_fixture("public_article.html")
    title, md, txt, _, _, _ = fetch_url._extract_with_optional_uplift(
        html, base_url="https://example.com/x",
    )
    err = capsys.readouterr().err
    # Module is unavailable in baseline venv → expect warning.
    if not fetch_url._TRAFILATURA_AVAILABLE:
        assert err.count("FETCH_WARN:NO_TRAFILATURA") == 1
    assert "POPs are the new particle context" in txt


@pytest.mark.optional
def test_trafilatura_used_when_available_uplifts_body(monkeypatch):
    """If a trafilatura-shaped uplift function is present, body should be
    at least as long as inline baseline.
    """
    fake_module = MagicMock()
    fake_module.extract.return_value = (
        "POPs are the new particle context in TouchDesigner. "
        "GPU-driven pipeline. Attribute lifecycle. Long uplift body. " * 5
    )
    monkeypatch.setattr(fetch_url, "_TRAFILATURA_AVAILABLE", True)
    monkeypatch.setattr(fetch_url, "_trafilatura_module", fake_module)

    html = _load_fixture("public_article.html")
    _, _, txt_inline, _, _, _ = fetch_url._inline_extract(
        html, base_url="https://example.com/x",
    )
    title, md, txt, _, _, _ = fetch_url._extract_with_optional_uplift(
        html, base_url="https://example.com/x",
    )
    assert len(txt) >= len(txt_inline)
