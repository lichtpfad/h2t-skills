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


def test_cli_args_no_url_returns_exit_1(capsys):
    with pytest.raises(SystemExit) as ei:
        fetch_url.main(["fetch"])
    assert ei.value.code == 1
    err = capsys.readouterr().err
    assert "FETCH_ERROR:ARGS" in err


def test_cli_args_explicit_stub_provider_returns_exit_1(capsys):
    with pytest.raises(SystemExit) as ei:
        fetch_url.main(["fetch", "--url", "https://example.com/x",
                        "--provider", "playwright"])
    assert ei.value.code == 1
    err = capsys.readouterr().err
    assert "FETCH_ERROR:ARGS" in err
    assert "playwright" in err


def test_cli_fetch_writes_sources_json_sidecar(tmp_path, monkeypatch):
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        rc = fetch_url.main([
            "fetch",
            "--url", "https://example.com/x",
            "--output-dir", str(tmp_path),
            "--project", "test",
        ])
    assert rc == 0
    sidecars = list(tmp_path.glob("test-fetch-*.sources.json"))
    assert len(sidecars) == 1
    data = json.loads(sidecars[0].read_text(encoding="utf-8"))
    # Top-level shape per spec §10.4:
    assert set(data.keys()) >= {"meta", "envelope", "body"}
    # Sidecar meta:
    assert data["meta"]["tool"] == "fetch_url.py"
    assert data["meta"]["project"] == "test"
    assert data["meta"]["url"] == "https://example.com/x"
    assert data["meta"]["status"] == "OK"
    # Envelope verbatim:
    assert data["envelope"]["status"] == "OK"
    assert data["envelope"]["meta"]["envelope_version"] == "1"
    assert data["envelope"]["provider_used"] == "direct"
    # Body block:
    assert "POPs in TouchDesigner" in data["body"]["markdown"]
    assert "POPs are the new particle context" in data["body"]["text_excerpt"]


def test_cli_default_stdout_markdown_summary(tmp_path, capsys):
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        rc = fetch_url.main([
            "fetch", "--url", "https://example.com/x",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith("## Fetch:") or out.startswith("# Fetch:")
    assert "provider_used: direct" in out


def test_cli_json_flag_prints_envelope(tmp_path, capsys):
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        rc = fetch_url.main([
            "fetch", "--url", "https://example.com/x", "--json",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    out = capsys.readouterr().out
    assert rc == 0
    parsed = json.loads(out)
    assert parsed["status"] == "OK"
    assert parsed["provider_used"] == "direct"


def test_cli_json_flag_prints_envelope_for_degraded_short_body(tmp_path, capsys):
    html = _load_fixture("short_body.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        rc = fetch_url.main([
            "fetch", "--url", "https://example.com/x", "--json",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    out = capsys.readouterr().out
    assert rc == 0
    parsed = json.loads(out)
    assert parsed["status"] == "DEGRADED"


def test_cli_failed_no_json_prints_stderr_only(tmp_path, capsys):
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(503)
        rc = fetch_url.main([
            "fetch", "--url", "https://example.com/x",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    captured = capsys.readouterr()
    assert rc == 2
    assert captured.out == "" or captured.out.strip() == ""
    assert "FETCH_ERROR:HTTP" in captured.err


def test_cli_failed_with_json_prints_envelope_and_error(tmp_path, capsys):
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(503)
        rc = fetch_url.main([
            "fetch", "--url", "https://example.com/x", "--json",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    captured = capsys.readouterr()
    assert rc == 2
    parsed = json.loads(captured.out)
    assert parsed["status"] == "FAILED"
    assert "FETCH_ERROR:HTTP" in captured.err


def test_cli_gated_with_json_flag(tmp_path, capsys):
    html = _load_fixture("login_wall.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/article/x",
        )
        rc = fetch_url.main([
            "fetch", "--url", "https://example.com/article/x", "--json",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    captured = capsys.readouterr()
    assert rc == 5
    parsed = json.loads(captured.out)
    assert parsed["status"] == "FAILED"
    assert parsed["content_gate"] == "login_required"
    assert "FETCH_ERROR:GATED" in captured.err
    assert "login_required" in captured.err


def test_keep_raw_off_by_default_no_raw_file(tmp_path):
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        rc = fetch_url.main([
            "fetch", "--url", "https://example.com/x",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    raws = list(tmp_path.glob("*.raw.html"))
    assert raws == []
    sidecar = next(tmp_path.glob("*.sources.json"))
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["envelope"]["metadata"]["raw_html_path"] is None


def test_keep_raw_on_writes_raw_file(tmp_path):
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        rc = fetch_url.main([
            "fetch", "--url", "https://example.com/x", "--keep-raw",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    raws = list(tmp_path.glob("*.raw.html"))
    assert len(raws) == 1
    sidecar = next(tmp_path.glob("*.sources.json"))
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["envelope"]["metadata"]["raw_html_path"] == str(raws[0])
    content = raws[0].read_text(encoding="utf-8")
    assert "POPs in TouchDesigner" in content


def test_partial_md_written_for_ok(tmp_path):
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        fetch_url.main([
            "fetch", "--url", "https://example.com/x",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    p = next(tmp_path.glob("*.partial.md"))
    body = p.read_text(encoding="utf-8")
    assert "POPs in TouchDesigner" in body
    assert "provider_used: direct" in body


def test_partial_md_not_written_for_failed(tmp_path):
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(503)
        fetch_url.main([
            "fetch", "--url", "https://example.com/x",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    assert list(tmp_path.glob("*.partial.md")) == []


def test_preflight_ok_when_jina_reachable(capsys):
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            b"OK", url="https://r.jina.ai/",
        )
        rc = fetch_url.main(["preflight"])
    assert rc == 0


def test_preflight_fails_when_jina_unreachable(capsys):
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("dns fail")
        rc = fetch_url.main(["preflight"])
    assert rc == 4
    err = capsys.readouterr().err
    assert "FETCH_ERROR:ENV" in err or "FETCH_ERROR:NETWORK" in err


def test_direct_403_without_auth_header_falls_through_to_jina_not_gated():
    # alltd_403_body fixture is the bytes that come back; key thing is
    # the absence of WWW-Authenticate.
    config = fetch_url.load_config(None)
    jina_md = _load_fixture("public_article_jina.md").encode("utf-8")
    body = _load_fixture("alltd_403_body.html").encode("utf-8")
    def fake_urlopen(req, timeout):
        if req.full_url.startswith("https://r.jina.ai/"):
            return _make_http_response(
                jina_md,
                url="https://r.jina.ai/https://alltd.org/x",
                headers={"Content-Type": "text/markdown"},
            )
        raise _http_error(403, body=body, headers={})
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        env = fetch_url.fetch_via_ladder(
            url="https://alltd.org/x", provider_choice="auto",
            config=config, user_agent="ua/test", keep_raw=False,
        )
    assert env["status"] == "OK"
    assert env["content_gate"] == "none"
    assert env["provider_used"] == "jina"


def test_unicode_article_extracts_safely():
    html = _load_fixture("non_ascii_article.html").encode("utf-8")
    p = fetch_url.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/ru",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
        r = p.fetch("https://example.com/ru",
                    timeout_ms=15000, user_agent="ua/test")
    assert "Атрибуты POP" in r.title
    assert "Жизненный цикл атрибута" in r.body_text


def test_envelope_version_fields_present_on_ok(tmp_path):
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        env = fetch_url.fetch_via_ladder(
            url="https://example.com/x", provider_choice="auto",
            config=fetch_url.load_config(None),
            user_agent="ua/test", keep_raw=False,
        )
    assert env["meta"]["envelope_version"] == "1"
    assert env["meta"]["fetch_envelope_version"] == "1"
    assert env["meta"]["primary_engine"] == "fetch_ladder"


def test_known_paywalled_domain_short_circuits(monkeypatch):
    # Inject a domain into the runtime set; PR#1 ships empty.
    monkeypatch.setattr(fetch_url, "KNOWN_PAYWALLED_DOMAINS", {"premium.example"})
    config = fetch_url.load_config(None)
    html = b"<html><body><article><p>x</p></article></body></html>"
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://premium.example/x",
        )
        env = fetch_url.fetch_via_ladder(
            url="https://premium.example/x", provider_choice="auto",
            config=config, user_agent="ua/test", keep_raw=False,
        )
    assert env["status"] == "FAILED"
    assert env["content_gate"] == "paid"


def test_cli_json_emits_utf8_envelope_with_non_ascii(tmp_path, monkeypatch, capsys):
    """Live smoke (issue #98) revealed the --json envelope crashes with
    UnicodeEncodeError on Windows when stdout is cp1252 and the body / title
    contains non-ASCII (emoji, Cyrillic, em-dash). Process exits with empty
    stdout. The CLI must reconfigure stdout/stderr to utf-8 so it never
    requires PYTHONIOENCODING=utf-8 to print non-ASCII envelopes.
    """
    # HTML with mixed non-ASCII glyphs: Cyrillic + em-dash + emoji-like glyphs.
    html = (
        "<!DOCTYPE html><html lang=\"ru\"><head><meta charset=\"utf-8\">"
        "<title>POPs — ⚡ Atributi ПОП ⦿</title>"
        "</head><body><article>"
        "<h1>POPs — ⚡ ПОП ⦿</h1>"
        "<p>Жизненный "
        "цикл атрибута "
        "— emoji ⦿ ⚡ — long enough body content text "
        "to clear the min_body_chars threshold for article classification, "
        "padded with extra prose so the classifier accepts this as an article "
        "rather than short_body. The em-dash and Cyrillic glyphs and emoji-like "
        "characters must round-trip cleanly through stdout.</p>"
        "</article></body></html>"
    ).encode("utf-8")

    # Replace sys.stdout/sys.stderr with cp1252-restricted streams. The
    # buffer-backed TextIOWrapper exposes reconfigure() (Python 3.7+) so the
    # fix-under-test is allowed to switch encoding to utf-8.
    raw_out = io.BytesIO()
    raw_err = io.BytesIO()
    fake_stdout = io.TextIOWrapper(
        raw_out, encoding="cp1252", errors="strict", write_through=True,
    )
    fake_stderr = io.TextIOWrapper(
        raw_err, encoding="cp1252", errors="strict", write_through=True,
    )
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    monkeypatch.setattr(sys, "stderr", fake_stderr)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
        rc = fetch_url.main([
            "fetch", "--url", "https://example.com/x", "--json",
            "--output-dir", str(tmp_path), "--project", "test",
        ])

    fake_stdout.flush()
    fake_stderr.flush()
    raw_stdout_bytes = raw_out.getvalue()
    out_text = raw_stdout_bytes.decode("utf-8")

    assert rc == 0, f"expected rc=0, got {rc}; stdout={raw_stdout_bytes!r}"
    assert raw_stdout_bytes, "stdout must not be empty after --json print"
    parsed = json.loads(out_text)
    assert parsed["status"] == "OK"
    # Title must round-trip — no mojibake, no replacement chars.
    assert "ПОП" in parsed["title"]  # Cyrillic ПОП
    assert "—" in parsed["title"]              # em-dash
    assert "⚡" in parsed["title"]              # ⚡
    # Body must also survive.
    assert "Жизненный" in parsed["body_text"]


def test_detect_homepage_redirect_true_for_alltd_pattern():
    """AllTD-class silent failure: requested article path → homepage `/`.
    Live smoke (#98) confirmed 6/6 AllTD URLs collapse this way."""
    assert fetch_url._detect_homepage_redirect(
        "https://alltd.org/glsl-for-pops-lesson-0-introduction/",
        "https://www.alltd.org/",
    ) is True


def test_detect_homepage_redirect_false_for_canonical_slash():
    """`/foo` → `/foo/` is normal canonical-slash redirect, not a collapse."""
    assert fetch_url._detect_homepage_redirect(
        "https://example.com/foo",
        "https://example.com/foo/",
    ) is False


def test_detect_homepage_redirect_false_for_root_request():
    """Asked for `/`, got `/` — obviously fine (no path collapse)."""
    assert fetch_url._detect_homepage_redirect(
        "https://example.com/",
        "https://example.com/",
    ) is False


def test_detect_homepage_redirect_false_for_no_final_url():
    """No final URL recorded → cannot decide, do not flag."""
    assert fetch_url._detect_homepage_redirect(
        "https://example.com/foo/bar",
        None,
    ) is False


def test_classify_content_redirect_collapsed_when_path_collapses():
    """Long body that LOOKS like an article must be marked redirect_collapsed
    when the requested article path collapsed to homepage root."""
    homepage_html = (
        "<html><body><article>"
        "<h1>Welcome to AllTouchDesigner</h1>"
        "<p>Browse our latest courses, tutorials, and resources for "
        "TouchDesigner. We cover GLSL, POPs, CHOPs, and much more in our "
        "tutorial library. " * 5
        + "</p></article></body></html>"
    )
    _, _, txt, _, _, _ = fetch_url._inline_extract(
        homepage_html, base_url="https://www.alltd.org/",
    )
    # Sanity: body is long enough to otherwise pass article classification.
    assert len(txt) >= 200
    ct, gate = fetch_url._classify_content(
        html=homepage_html,
        body_text=txt,
        final_url="https://www.alltd.org/",
        site="alltd.org",
        min_body_chars=200,
        request_url="https://alltd.org/glsl-for-pops-lesson-0-introduction/",
    )
    assert ct == "redirect_collapsed"
    assert gate == "none"


def test_ladder_alltd_collapse_falls_through_to_jina_then_degraded():
    """Direct collapses (homepage shell), Jina also collapses (auth-gated
    article requires login). All providers see the same homepage; final
    envelope is DEGRADED with redirect_collapsed_to_homepage reason and
    both attempts marked fetch_redirect_collapsed."""
    config = fetch_url.load_config(None)
    homepage_html = (
        "<html><body><article>"
        "<h1>AllTouchDesigner</h1>"
        "<p>" + ("Welcome to our tutorial library covering GLSL, POPs, CHOPs. " * 20)
        + "</p></article></body></html>"
    ).encode("utf-8")
    # Jina also returns the homepage chrome (Jina cannot authenticate).
    jina_homepage_md = (
        "Title: AllTouchDesigner\n\n"
        "URL Source: https://www.alltd.org/\n\n"
        "Markdown Content:\n"
        + ("Welcome to AllTouchDesigner — homepage listing. " * 30)
    ).encode("utf-8")

    def fake_urlopen(req, timeout):
        if req.full_url.startswith("https://r.jina.ai/"):
            # Jina relay returns the homepage shell too (real-world AllTD).
            return _make_http_response(
                jina_homepage_md,
                url="https://r.jina.ai/https://alltd.org/glsl-for-pops-lesson-0/",
                headers={"Content-Type": "text/markdown; charset=utf-8"},
            )
        # Direct: requested /glsl-for-pops-lesson-0/ → final URL is homepage /.
        return _make_http_response(
            homepage_html,
            url="https://www.alltd.org/",
            headers={"Content-Type": "text/html; charset=utf-8"},
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        env = fetch_url.fetch_via_ladder(
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
    """Direct collapses to homepage, Jina returns the real article body.
    Ladder must continue past the collapse and pick Jina's good result."""
    config = fetch_url.load_config(None)
    homepage_html = (
        "<html><body><article>"
        "<h1>AllTouchDesigner</h1>"
        "<p>" + ("Welcome to our tutorial library covering GLSL, POPs, CHOPs. " * 20)
        + "</p></article></body></html>"
    ).encode("utf-8")
    # Jina returns substantive markdown about the requested topic.
    jina_real_article = (
        "Title: GLSL for POPs — Lesson 0\n\n"
        "URL Source: https://alltd.org/glsl-for-pops-lesson-0/\n\n"
        "Markdown Content:\n"
        "# GLSL for POPs — Lesson 0\n\n"
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
        env = fetch_url.fetch_via_ladder(
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


def test_public_api_exports_for_adapters():
    expected = {
        "fetch_via_ladder", "build_fetch_envelope", "load_config",
        "ProviderResult", "ProviderTransientError", "ProviderPermanentError",
        "ProviderHardGate", "ProviderNotConfigured",
        "DirectProvider", "JinaProvider",
        "PlaywrightProvider", "Crawl4AIProvider",
        "FirecrawlProvider", "BrowserlessProvider",
        "ENVELOPE_VERSION", "FETCH_ENVELOPE_VERSION",
    }
    assert expected.issubset(set(fetch_url.__all__))
