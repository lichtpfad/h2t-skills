"""The cases of the deleted fetch_url.py suite that test_fetch.py did not already hold (#541).

fetch_url.py was deleted in Task 12; h2t_ops/connectors/research/fetch.py is its copy, and
`h2t-ops research fetch|preflight` replaced its CLI. The library cases run unchanged
against the package module. The CLI cases run the connector command; where the connector
differs from the script on purpose (exit codes, the human rendering, the artifact
layout), the comment in the case says what the script did.

Spec: docs/superpowers/specs/2026-05-07-research-fetch-url-ladder.md
Issue: lichtpfad/h2t-skills#103
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from h2t_ops.connectors.research import fetch as fetch_url
from h2t_ops.connectors.research import store


@pytest.fixture(autouse=True)
def _live_module(monkeypatch):
    """Bind the module the connector will import (the network refusal is in conftest.py).

    test_commands.py pops the research modules from sys.modules to prove they load lazily,
    so the module imported at the top of this file can be a stale copy that the client no
    longer calls: a patch on it then misses, and the request goes out for real. Measured
    2026-10-17, when exactly that sent fake keys to api.exa.ai.
    """
    import importlib

    monkeypatch.setitem(globals(), "fetch_url", importlib.import_module("h2t_ops.connectors.research.fetch"))


def test_fetch_url_module_imports():
    assert hasattr(fetch_url, "__version__")
    assert fetch_url.__version__ == "0.0.1"










FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fetch"


def _load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")




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




def _http_error(code: int, body: bytes = b"", headers: dict[str, str] | None = None,
                url: str = "https://example.com/x"):
    return urllib.error.HTTPError(
        url=url, code=code, msg="err",
        hdrs=headers or {}, fp=io.BytesIO(body),
    )


















def test_detect_js_shell_false_for_real_article():
    html = _load_fixture("public_article.html")
    _, _, body_text, _, _, _ = fetch_url._inline_extract(html, base_url="x")
    assert fetch_url._detect_js_shell(html=html, body_text=body_text) is False




def test_detect_login_wall_true_for_meta_refresh_to_login():
    html = _load_fixture("redirect_to_login.html")
    assert fetch_url._detect_login_wall(html=html, final_url="https://example.com/article/x") is True


def test_detect_login_wall_true_for_final_url_login_path():
    html = "<html><body>noop</body></html>"
    assert fetch_url._detect_login_wall(html=html, final_url="https://example.com/login") is True


def test_detect_login_wall_false_for_real_article():
    html = _load_fixture("public_article.html")
    assert fetch_url._detect_login_wall(html=html, final_url="https://example.com/x") is False




def test_detect_paywall_false_for_public_article():
    html = _load_fixture("public_article.html")
    assert fetch_url._detect_paywall(html=html, site="example.com") is False












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


def _cli(argv: list[str]) -> int:
    """`h2t-ops research <argv>`: the command that replaced `fetch_url.py <argv>`."""
    from h2t_ops import cli

    if argv[:1] == ["preflight"]:  # fetch_url's preflight probed Jina
        argv = ["preflight", "--provider", "jina", *argv[1:]]
    return cli.dispatch(["research", *argv])


def _error(captured) -> dict:
    """The connector writes a failure's envelope to stderr."""
    return json.loads(captured.err.strip().splitlines()[-1])["error"]



def test_cli_args_no_url_returns_exit_1(capsys):
    # The script exited 1 with FETCH_ERROR:ARGS; the connector's usage exit is 2.
    assert _cli(["fetch"]) == 2
    assert "--url" in capsys.readouterr().err


def test_cli_args_explicit_stub_provider_returns_exit_1(capsys):
    rc = _cli(["fetch", "--url", "https://example.com/x", "--provider", "playwright", "--json"])
    assert rc == 1
    telemetry = _error(capsys.readouterr())["details"]["provider_envelope"]["telemetry"]
    assert telemetry["providers_skipped_reason"] == {"playwright": "not_configured_stub"}


def test_cli_fetch_writes_sources_json_sidecar(tmp_path, monkeypatch):
    # The script's sidecar carried meta/envelope/body. The connector writes an artifact that
    # points into its document store; test_client.py pins the artifact's own fields.
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        rc = _cli([
            "fetch",
            "--url", "https://example.com/x",
            "--output-dir", str(tmp_path),
            "--project", "test",
        ])
    assert rc == 0
    assert len(list(tmp_path.glob("test-*fetch-*.sources.json"))) == 1
    artifacts = list(tmp_path.glob("test-*fetch-*.artifact.json"))
    assert len(artifacts) == 1
    # The body lives in the document store the artifact points to. Follow the reference, not
    # a directory listing: the id holds a colon, and on NTFS `research-doc:<hex>.json` is an
    # alternate data stream of a file `research-doc` — glob sees no *.json there (CI on #552).
    refs = json.loads(artifacts[0].read_text(encoding="utf-8"))["research_refs"]
    document_json = Path(refs["document_json"])
    assert document_json == store.object_path(tmp_path, "documents", refs["document_id"])
    document = document_json.read_text(encoding="utf-8")
    assert "POPs in TouchDesigner" in document
    assert "https://example.com/x" in document


def test_cli_default_stdout_markdown_summary(tmp_path, capsys):
    # The script printed a "## Fetch:" summary; the connector's human output is the result.
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        rc = _cli([
            "fetch", "--url", "https://example.com/x",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    out = capsys.readouterr().out
    assert rc == 0
    assert '"provider_used": "direct"' in out


def test_cli_json_flag_prints_envelope(tmp_path, capsys):
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        rc = _cli([
            "fetch", "--url", "https://example.com/x", "--json",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    out = capsys.readouterr().out
    assert rc == 0
    parsed = json.loads(out)["result"]
    assert parsed["status"] == "OK"
    assert parsed["provider_used"] == "direct"


def test_cli_json_flag_prints_envelope_for_degraded_short_body(tmp_path, capsys):
    html = _load_fixture("short_body.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        rc = _cli([
            "fetch", "--url", "https://example.com/x", "--json",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    out = capsys.readouterr().out
    assert rc == 0
    parsed = json.loads(out)["result"]
    assert parsed["status"] == "DEGRADED"


def test_cli_failed_no_json_prints_stderr_only(tmp_path, capsys):
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(503)
        rc = _cli([
            "fetch", "--url", "https://example.com/x",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    captured = capsys.readouterr()
    # The script exited 2 with FETCH_ERROR:HTTP; a provider failure is exit 1 here.
    assert rc == 1
    assert captured.out.strip() == ""
    assert "Fetch failed" in captured.err


def test_cli_failed_with_json_prints_envelope_and_error(tmp_path, capsys):
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(503)
        rc = _cli([
            "fetch", "--url", "https://example.com/x", "--json",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.out.strip() == ""
    assert _error(captured)["details"]["provider_envelope"]["status"] == "FAILED"


def test_cli_gated_with_json_flag(tmp_path, capsys):
    html = _load_fixture("login_wall.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/article/x",
        )
        rc = _cli([
            "fetch", "--url", "https://example.com/article/x", "--json",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    captured = capsys.readouterr()
    # The script exited 5; a gate is the connector's auth exit, 4.
    assert rc == 4
    envelope = _error(captured)["details"]["provider_envelope"]
    assert envelope["status"] == "FAILED"
    assert envelope["content_gate"] == "login_required"


def test_keep_raw_off_by_default_no_raw_file(tmp_path):
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        _cli([
            "fetch", "--url", "https://example.com/x",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    assert list(tmp_path.glob("*.raw.html")) == []


def test_keep_raw_on_writes_raw_file(tmp_path):
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        _cli([
            "fetch", "--url", "https://example.com/x", "--keep-raw",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    raws = list(tmp_path.glob("*.raw.html"))
    assert len(raws) == 1
    content = raws[0].read_text(encoding="utf-8")
    assert "POPs in TouchDesigner" in content


def test_partial_md_written_for_ok(tmp_path):
    # The script's partial.md held the body; the connector's is a status summary.
    html = _load_fixture("public_article.html").encode("utf-8")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            html, url="https://example.com/x",
        )
        _cli([
            "fetch", "--url", "https://example.com/x",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    body = next(tmp_path.glob("*.partial.md")).read_text(encoding="utf-8")
    assert "- status: OK" in body


def test_partial_md_not_written_for_failed(tmp_path):
    # Divergence: the script wrote no partial.md for a failed fetch; the connector writes
    # one that says FAILED, and keeps the document out of the store (test_client.py,
    # test_research_client_fetch_failed_does_not_persist_document).
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = _http_error(503)
        _cli([
            "fetch", "--url", "https://example.com/x",
            "--output-dir", str(tmp_path), "--project", "test",
        ])
    body = next(tmp_path.glob("*.partial.md")).read_text(encoding="utf-8")
    assert "- status: FAILED" in body
    assert not (tmp_path / "objects").exists()


def test_preflight_ok_when_jina_reachable(capsys):
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = _make_http_response(
            b"OK", url="https://r.jina.ai/",
        )
        rc = _cli(["preflight"])
    assert rc == 0


def test_preflight_fails_when_jina_unreachable(capsys):
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("dns fail")
        rc = _cli(["preflight"])
    # The script exited 4; an unreachable host is the connector's network exit, 6.
    assert rc == 6


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
    stdout. The CLI must write utf-8 so it never requires PYTHONIOENCODING=utf-8
    to print non-ASCII envelopes.
    """
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
    ).encode()

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
        rc = _cli([
            "fetch", "--url", "https://example.com/x", "--json",
            "--output-dir", str(tmp_path), "--project", "test",
        ])

    fake_stdout.flush()
    fake_stderr.flush()
    raw_stdout_bytes = raw_out.getvalue()
    out_text = raw_stdout_bytes.decode("utf-8")

    assert rc == 0, f"expected rc=0, got {rc}; stdout={raw_stdout_bytes!r}"
    assert raw_stdout_bytes, "stdout must not be empty after --json print"
    parsed = json.loads(out_text)["result"]
    assert parsed["status"] == "OK"
    # Title must round-trip — no mojibake, no replacement chars.
    assert "ПОП" in parsed["title"]
    assert "—" in parsed["title"]
    assert "⚡" in parsed["title"]
    assert "Жизненный" in parsed["body_text"]




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
