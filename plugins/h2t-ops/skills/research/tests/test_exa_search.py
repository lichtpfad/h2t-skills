"""Tests for exa_search.py CLI wrapper."""
import io
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import urllib.error

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "exa_search.py"


def test_script_exists():
    assert SCRIPT.is_file(), f"expected script at {SCRIPT}"


def test_version_flag():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "0.1.0" in result.stdout


# --- MODE_CONFIG tests ---
sys.path.insert(0, str(SCRIPT.parent))
import exa_search  # noqa: E402


def test_mode_config_has_all_seven_modes():
    expected = {"fast", "generic", "news", "academic", "competitor", "people", "deep"}
    assert set(exa_search.MODE_CONFIG.keys()) == expected


def test_mode_config_competitor_uses_company_category():
    cfg = exa_search.MODE_CONFIG["competitor"]
    assert cfg["type"] == "auto"
    assert cfg["category"] == "company"
    assert cfg["num_results"] == 10


def test_mode_config_deep_uses_deep_type_default_10():
    cfg = exa_search.MODE_CONFIG["deep"]
    assert cfg["type"] == "deep"
    assert cfg["category"] is None
    assert cfg["num_results"] == 10


def test_mode_config_fast_uses_fast_type():
    cfg = exa_search.MODE_CONFIG["fast"]
    assert cfg["type"] == "fast"
    assert cfg["num_results"] == 10


def test_category_blocks_company_blocks_dates_and_domains():
    blocks = exa_search.CATEGORY_BLOCKS["company"]
    assert "start_date" in blocks
    assert "end_date" in blocks
    assert "include_domains" in blocks
    assert "exclude_domains" in blocks


def test_category_blocks_people_blocks_text_and_dates():
    blocks = exa_search.CATEGORY_BLOCKS["people"]
    assert "include_text" in blocks
    assert "exclude_text" in blocks
    assert "exclude_domains" in blocks
    assert "start_date" in blocks


def test_category_blocks_financial_report_blocks_exclude_text():
    assert "exclude_text" in exa_search.CATEGORY_BLOCKS["financial report"]


def test_die_writes_stderr_and_exits_with_code(capsys):
    with pytest.raises(SystemExit) as excinfo:
        exa_search.die(4, "EXA_ERROR:ENV EXA_API_KEY missing")
    assert excinfo.value.code == 4
    captured = capsys.readouterr()
    assert "EXA_ERROR:ENV" in captured.err
    assert "EXA_API_KEY missing" in captured.err
    assert captured.out == ""


# --- validate_args helper & tests ---

def _args(**kwargs):
    defaults = dict(
        mode="generic",
        start_date=None, end_date=None,
        include_domains=None, exclude_domains=None,
        include_text=None, exclude_text=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_validate_competitor_with_start_date_exits_1(capsys):
    args = _args(mode="competitor", start_date="2025-01-01")
    with pytest.raises(SystemExit) as excinfo:
        exa_search.validate_args(args)
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "EXA_ERROR:ARGS" in err
    assert "mode=competitor" in err
    assert "category=company" in err
    assert "--start-date" in err


def test_validate_people_with_exclude_text_exits_1(capsys):
    args = _args(mode="people", exclude_text=["foo"])
    with pytest.raises(SystemExit) as excinfo:
        exa_search.validate_args(args)
    assert excinfo.value.code == 1
    assert "EXA_ERROR:ARGS" in capsys.readouterr().err


def test_validate_include_text_multi_item_exits_1(capsys):
    args = _args(mode="generic", include_text=["foo", "bar"])
    with pytest.raises(SystemExit) as excinfo:
        exa_search.validate_args(args)
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "single-item" in err


def test_validate_valid_combinations_pass():
    # news + dates + domains — all allowed
    exa_search.validate_args(_args(
        mode="news",
        start_date="2025-01-01",
        end_date="2026-04-18",
        include_domains=["techcrunch.com"],
    ))
    # competitor without restricted params — allowed
    exa_search.validate_args(_args(mode="competitor"))
    # single-item include_text — allowed
    exa_search.validate_args(_args(mode="generic", include_text=["solo"]))


# --- load_system_prompt tests ---

def test_load_system_prompt_parses_frontmatter_and_body(tmp_path, monkeypatch):
    sp_dir = tmp_path / "systemprompts"
    sp_dir.mkdir()
    (sp_dir / "generic.md").write_text(
        "---\n"
        "mode: generic\n"
        "exa_type: auto\n"
        "---\n"
        "You are a neutral research assistant. Cite sources.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(exa_search, "SYSTEMPROMPTS_DIR", sp_dir)
    body, schema = exa_search.load_system_prompt("generic")
    assert "neutral research assistant" in body
    assert schema == {}


def test_load_system_prompt_parses_output_schema_json(tmp_path, monkeypatch):
    sp_dir = tmp_path / "systemprompts"
    sp_dir.mkdir()
    (sp_dir / "competitor.md").write_text(
        "---\n"
        "mode: competitor\n"
        'output_schema: {"type": "object", "properties": {"name": {"type": "string"}}}\n'
        "---\n"
        "Competitive intel researcher.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(exa_search, "SYSTEMPROMPTS_DIR", sp_dir)
    body, schema = exa_search.load_system_prompt("competitor")
    assert "Competitive intel" in body
    assert schema == {"type": "object", "properties": {"name": {"type": "string"}}}


def test_load_system_prompt_missing_file_exits_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(exa_search, "SYSTEMPROMPTS_DIR", tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        exa_search.load_system_prompt("nonexistent")
    assert excinfo.value.code == 1
    assert "EXA_ERROR:ARGS" in capsys.readouterr().err


# --- build_body helper & tests ---

def _full_args(**kwargs):
    defaults = dict(
        mode="generic",
        query="Rejuve.bio Switzerland",
        num_results=None,
        additional_queries=None,
        start_date=None, end_date=None,
        include_domains=None, exclude_domains=None,
        include_text=None, exclude_text=None,
        country=None,
        full_text=False,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_build_body_generic_minimal():
    body = exa_search.build_body(_full_args(mode="generic"), "SP", {})
    assert body["query"] == "Rejuve.bio Switzerland"
    assert body["type"] == "auto"
    assert body["numResults"] == 10
    assert body["systemPrompt"] == "SP"
    assert body["contents"]["highlights"]["maxCharacters"] == 4000
    assert "category" not in body


def test_build_body_competitor_sets_category():
    body = exa_search.build_body(_full_args(mode="competitor"), "SP", {})
    assert body["category"] == "company"
    assert body["type"] == "auto"


def test_build_body_news_with_dates_and_domains():
    body = exa_search.build_body(_full_args(
        mode="news",
        start_date="2025-01-01",
        end_date="2026-04-18",
        include_domains=["techcrunch.com"],
    ), "SP", {})
    assert body["category"] == "news"
    assert body["startPublishedDate"] == "2025-01-01"
    assert body["endPublishedDate"] == "2026-04-18"
    assert body["includeDomains"] == ["techcrunch.com"]


def test_build_body_deep_with_additional_queries():
    body = exa_search.build_body(_full_args(
        mode="deep",
        additional_queries=["variation 1", "variation 2"],
    ), "SP", {})
    assert body["type"] == "deep"
    assert body["additionalQueries"] == ["variation 1", "variation 2"]


def test_build_body_with_schema_sets_structuredoutput():
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    body = exa_search.build_body(_full_args(mode="generic"), "SP", schema)
    assert body["outputSchema"] == schema
    assert body["structuredOutput"] is True


def test_build_body_num_results_override():
    body = exa_search.build_body(_full_args(mode="academic", num_results=25), "SP", {})
    assert body["numResults"] == 25


# --- call_exa HTTP client & tests ---


def _mock_urlopen_response(status, body):
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = json.dumps(body).encode("utf-8")
    resp.__enter__ = lambda self: resp
    resp.__exit__ = lambda self, *a: None
    return resp


def test_call_exa_success():
    payload = {"results": [{"title": "T", "url": "https://x"}], "costDollars": {"total": 0.007}}
    with patch("urllib.request.urlopen", return_value=_mock_urlopen_response(200, payload)):
        status, data, latency_ms = exa_search.call_exa(
            "/search", {"query": "q"}, api_key="testkey"
        )
    assert status == 200
    assert data["results"][0]["url"] == "https://x"
    assert latency_ms >= 0


# --- preflight tests ---


def test_preflight_missing_env_exits_4(monkeypatch, capsys):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    with pytest.raises(SystemExit) as excinfo:
        exa_search.preflight()
    assert excinfo.value.code == 4
    assert "EXA_ERROR:ENV" in capsys.readouterr().err


def test_preflight_ok_prints_ok(monkeypatch, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    mock_resp = _mock_urlopen_response(200, {})
    with patch("urllib.request.urlopen", return_value=mock_resp):
        exa_search.preflight()
    assert "OK" in capsys.readouterr().out


def test_preflight_network_failure_exits_4(monkeypatch, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("no route")):
        with pytest.raises(SystemExit) as excinfo:
            exa_search.preflight()
    assert excinfo.value.code == 4
    assert "EXA_ERROR:NETWORK" in capsys.readouterr().err


def test_preflight_http_error_treated_as_reachable(monkeypatch, capsys):
    """Regression: HTTPError (e.g. 403) means server is reachable, not a network failure."""
    monkeypatch.setenv("EXA_API_KEY", "stub")
    err = urllib.error.HTTPError(
        url="https://api.exa.ai/",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=io.BytesIO(b""),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        exa_search.preflight()
    out = capsys.readouterr().out
    assert "OK" in out


# --- slugify & output_paths tests ---


def test_slugify_lowercases_and_hyphenates():
    assert exa_search.slugify("Rejuve.bio Competitors Switzerland 2026") == "rejuve-bio-competitors-switzerland-2026"


def test_slugify_strips_special_chars():
    assert exa_search.slugify("AI & Biotech: Q4/2025!") == "ai-biotech-q4-2025"


def test_slugify_truncates_to_50_chars():
    long = "a" * 120
    assert len(exa_search.slugify(long)) == 50


def test_output_paths_structure(tmp_path):
    paths = exa_search.output_paths(
        output_dir=tmp_path, project="rejuve", topic="Competitors CH", date="2026-04-18"
    )
    assert paths["partial_md"].name == "rejuve-competitors-ch-2026-04-18.partial.md"
    assert paths["final_md"].name == "rejuve-competitors-ch-2026-04-18.md"
    assert paths["sources_json"].name == "rejuve-competitors-ch-2026-04-18.sources.json"
    assert paths["partial_md"].parent == tmp_path


def _sample_exa_response():
    return {
        "results": [
            {
                "title": "Rejuve.bio — About",
                "url": "https://rejuve.bio/about",
                "highlights": ["Rejuve.bio operates as a DAO focused on longevity research."],
                "publishedDate": "2026-02-14",
            },
            {
                "title": "Swiss Longevity 2026",
                "url": "https://swiss-longevity.ch/report",
                "highlights": ["Three Swiss longevity startups raised $12M total in 2026 Q1."],
                "publishedDate": "2026-01-20",
            },
        ],
        "costDollars": {"total": 0.012},
    }


def test_render_stdout_summary_includes_query_and_cost(capsys, tmp_path):
    # Use tmp_path to stay platform-agnostic — hardcoded "/tmp/..." breaks on
    # Windows because Path("/tmp/x") becomes WindowsPath("\\tmp\\x") when rendered.
    partial = tmp_path / "x.partial.md"
    sources = tmp_path / "x.sources.json"
    data = _sample_exa_response()
    exa_search.render_stdout_summary(
        data, query="Rejuve.bio competitors", mode="competitor",
        latency_ms=2100, partial_path=partial, json_path=sources,
    )
    out = capsys.readouterr().out
    assert "Rejuve.bio competitors" in out
    assert "competitor" in out
    assert "$0.012" in out
    assert "2100ms" in out or "2.1s" in out
    assert "rejuve.bio/about" in out
    # Filename is platform-agnostic; full path rendering differs on Windows.
    assert partial.name in out
    assert sources.name in out


def test_write_sources_json(tmp_path):
    path = tmp_path / "x.sources.json"
    meta = {"query": "q", "mode": "generic", "cost_usd": 0.01, "latency_ms": 1000}
    exa_search.write_sources_json(path, meta, _sample_exa_response())
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["meta"]["query"] == "q"
    assert loaded["response"]["costDollars"]["total"] == 0.012
    assert len(loaded["response"]["results"]) == 2


def test_write_partial_md_includes_meta_and_telemetry_row(tmp_path):
    path = tmp_path / "x.partial.md"
    exa_search.write_partial_md(
        path,
        meta=dict(
            query="Rejuve competitors", mode="competitor", depth="standard",
            project="rejuve", date="2026-04-18T12:00:00Z", status="completed",
            cache_hit=False,
        ),
        telemetry_rows=[
            {"num": 1, "tool": "exa_search.py search", "args": "type=auto,category=company",
             "http": 200, "latency_ms": 2100, "cost_usd": 0.012, "results": 2},
        ],
    )
    text = path.read_text(encoding="utf-8")
    assert "# Research: Rejuve competitors" in text
    assert "| **Mode** | competitor |" in text
    assert "exa_search.py search" in text
    assert "$0.012" in text
    assert "Integrity check:" in text


def test_post_telemetry_awaiting_endpoint_when_env_unset(monkeypatch, tmp_path):
    # MVP default: endpoint not configured yet → 'awaiting_endpoint', not 'disabled'.
    monkeypatch.delenv("H2T_EVALS_URL", raising=False)
    monkeypatch.delenv("H2T_EVALS_DISABLE", raising=False)
    status = exa_search.post_telemetry(
        event={"foo": "bar"}, buffer_path=tmp_path / "buf.jsonl"
    )
    assert status == "awaiting_endpoint"
    assert not (tmp_path / "buf.jsonl").exists()


def test_post_telemetry_disabled_when_explicit_opt_out(monkeypatch, tmp_path):
    # User explicit opt-out takes precedence over URL presence.
    monkeypatch.setenv("H2T_EVALS_DISABLE", "1")
    monkeypatch.setenv("H2T_EVALS_URL", "https://evals.example.com")
    status = exa_search.post_telemetry(
        event={"foo": "bar"}, buffer_path=tmp_path / "buf.jsonl"
    )
    assert status == "disabled"
    assert not (tmp_path / "buf.jsonl").exists()


def test_post_telemetry_buffers_on_network_failure(monkeypatch, tmp_path):
    monkeypatch.delenv("H2T_EVALS_DISABLE", raising=False)
    monkeypatch.setenv("H2T_EVALS_URL", "https://evals.example.com")
    buf = tmp_path / "buf.jsonl"
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
        status = exa_search.post_telemetry(event={"a": 1}, buffer_path=buf)
    assert status == "buffered"
    assert buf.exists()
    line = buf.read_text(encoding="utf-8").strip()
    assert json.loads(line) == {"a": 1}


def test_post_telemetry_sent_on_success(monkeypatch, tmp_path):
    monkeypatch.delenv("H2T_EVALS_DISABLE", raising=False)
    monkeypatch.setenv("H2T_EVALS_URL", "https://evals.example.com")
    buf = tmp_path / "buf.jsonl"
    with patch("urllib.request.urlopen", return_value=_mock_urlopen_response(202, {})):
        status = exa_search.post_telemetry(event={"a": 1}, buffer_path=buf)
    assert status == "sent"
    assert not buf.exists()


# --- main() argparse tests ---


def test_cli_preflight_invokes_preflight(monkeypatch, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    with patch("urllib.request.urlopen", return_value=_mock_urlopen_response(200, {})):
        rc = exa_search.main(["preflight"])
    assert rc == 0
    assert "OK" in capsys.readouterr().out


def test_cli_search_requires_query(capsys):
    with pytest.raises(SystemExit) as excinfo:
        exa_search.main(["search", "--mode", "generic"])
    # argparse itself exits with code 2 on missing required arg
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "--query" in err or "required" in err


def test_cli_search_unknown_mode_argparse_rejects(capsys):
    with pytest.raises(SystemExit) as excinfo:
        exa_search.main(["search", "--query", "x", "--mode", "notamode"])
    assert excinfo.value.code == 2
    assert "invalid choice" in capsys.readouterr().err.lower()


def test_cli_crawl_requires_url(capsys):
    with pytest.raises(SystemExit) as excinfo:
        exa_search.main(["crawl"])
    assert excinfo.value.code == 2


def test_run_search_happy_path_exits_0(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    sp_dir = tmp_path / "systemprompts"
    sp_dir.mkdir()
    (sp_dir / "generic.md").write_text("---\n---\nYou are a researcher.\n", encoding="utf-8")
    monkeypatch.setattr(exa_search, "SYSTEMPROMPTS_DIR", sp_dir)

    out_dir = tmp_path / "out"
    response = _sample_exa_response()
    with patch("urllib.request.urlopen", return_value=_mock_urlopen_response(200, response)):
        rc = exa_search.main([
            "search", "--query", "Rejuve.bio Switzerland",
            "--mode", "generic",
            "--output-dir", str(out_dir),
            "--project", "rejuve",
        ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "## Exa Search" in out
    assert "rejuve.bio/about" in out
    # Check files created
    files = list(out_dir.glob("rejuve-rejuve-bio-switzerland-*"))
    assert any(p.name.endswith(".partial.md") for p in files)
    assert any(p.name.endswith(".sources.json") for p in files)


def test_run_search_invalid_combo_exits_1(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    sp_dir = tmp_path / "systemprompts"
    sp_dir.mkdir()
    (sp_dir / "competitor.md").write_text("---\n---\nCompetitive researcher.\n", encoding="utf-8")
    monkeypatch.setattr(exa_search, "SYSTEMPROMPTS_DIR", sp_dir)

    with pytest.raises(SystemExit) as excinfo:
        exa_search.main([
            "search", "--query", "x",
            "--mode", "competitor",
            "--start-date", "2025-01-01",
            "--output-dir", str(tmp_path),
        ])
    assert excinfo.value.code == 1
    assert "EXA_ERROR:ARGS" in capsys.readouterr().err


def test_run_search_http_429_exits_2(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    sp_dir = tmp_path / "systemprompts"
    sp_dir.mkdir()
    (sp_dir / "generic.md").write_text("---\n---\nsp\n", encoding="utf-8")
    monkeypatch.setattr(exa_search, "SYSTEMPROMPTS_DIR", sp_dir)

    err = urllib.error.HTTPError(
        url="https://api.exa.ai/search", code=429, msg="Too Many",
        hdrs=None, fp=io.BytesIO(b'{"error": "rate_limit_exceeded"}'),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(SystemExit) as excinfo:
            exa_search.main([
                "search", "--query", "q",
                "--output-dir", str(tmp_path),
            ])
    assert excinfo.value.code == 2
    assert "EXA_ERROR:API" in capsys.readouterr().err


def test_main_reconfigures_stdout_to_utf8(monkeypatch):
    """Regression: cp1252 default on Windows crashes on emoji in Exa highlights."""
    calls = []

    class _Stream:
        encoding = "cp1252"

        def reconfigure(self, **kwargs):
            calls.append(kwargs)

        def write(self, *a, **kw):
            pass

        def flush(self):
            pass

    monkeypatch.setattr(sys, "stdout", _Stream())
    monkeypatch.setattr(sys, "stderr", _Stream())
    with pytest.raises(SystemExit):
        exa_search.main(["--version"])
    assert any(
        c.get("encoding") == "utf-8" and c.get("errors") == "replace"
        for c in calls
    ), f"expected stdout.reconfigure(encoding='utf-8', errors='replace'); got {calls}"


def test_run_crawl_writes_files(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    out_dir = tmp_path / "out"
    response = {
        "results": [{
            "title": "About Rejuve",
            "url": "https://rejuve.bio/about",
            "text": "Rejuve.bio operates as a DAO ... (full content)",
        }],
        "costDollars": {"total": 0.002},
    }
    with patch("urllib.request.urlopen", return_value=_mock_urlopen_response(200, response)):
        rc = exa_search.main([
            "crawl", "--url", "https://rejuve.bio/about",
            "--output-dir", str(out_dir),
            "--project", "rejuve",
        ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "rejuve.bio/about" in out
    files = list(out_dir.glob("rejuve-*"))
    assert any(p.name.endswith(".sources.json") for p in files)


def test_call_exa_sets_user_agent_header():
    """Regression: Cloudflare 403s the default Python-urllib UA; we must set our own."""
    captured = {}

    class _Capture(MagicMock):
        def __init__(self, *a, **kw):
            super().__init__()

        def __call__(self, req, timeout=None):
            captured["headers"] = dict(req.header_items())
            resp = MagicMock()
            resp.status = 200
            resp.read.return_value = b'{"results": []}'
            resp.__enter__ = lambda self: resp
            resp.__exit__ = lambda self, *a: None
            return resp

    cap = _Capture()
    with patch("urllib.request.urlopen", side_effect=cap):
        exa_search.call_exa("/search", {"query": "q"}, api_key="testkey")
    # urllib capitalises header names as Title-Case
    ua = captured["headers"].get("User-agent") or captured["headers"].get("User-Agent")
    assert ua is not None, f"User-Agent missing; captured={captured['headers']}"
    assert "exa_search.py" in ua


# --- call_exa typed exceptions (Task 1) ---

def test_call_exa_raises_transient_on_5xx():
    with patch("urllib.request.urlopen") as mock_urlopen:
        err = urllib.error.HTTPError(
            url="https://api.exa.ai/search", code=503,
            msg="Service Unavailable", hdrs=None,
            fp=io.BytesIO(b'{"error":"upstream"}'),
        )
        mock_urlopen.side_effect = err
        with pytest.raises(exa_search.ExaTransientError) as ei:
            exa_search.call_exa("/search", {"query": "x"}, api_key="k")
        assert ei.value.http_status == 503
        assert ei.value.latency_ms >= 0


def test_call_exa_raises_transient_on_429():
    with patch("urllib.request.urlopen") as mock_urlopen:
        err = urllib.error.HTTPError(
            url="https://api.exa.ai/search", code=429,
            msg="Too Many Requests", hdrs=None,
            fp=io.BytesIO(b'{"error":"rate"}'),
        )
        mock_urlopen.side_effect = err
        with pytest.raises(exa_search.ExaTransientError) as ei:
            exa_search.call_exa("/search", {"query": "x"}, api_key="k")
        assert ei.value.http_status == 429


def test_call_exa_raises_permanent_on_4xx():
    with patch("urllib.request.urlopen") as mock_urlopen:
        err = urllib.error.HTTPError(
            url="https://api.exa.ai/search", code=401,
            msg="Unauthorized", hdrs=None,
            fp=io.BytesIO(b'{"error":"bad key"}'),
        )
        mock_urlopen.side_effect = err
        with pytest.raises(exa_search.ExaPermanentError) as ei:
            exa_search.call_exa("/search", {"query": "x"}, api_key="k")
        assert ei.value.http_status == 401


def test_call_exa_raises_transient_on_urlerror():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("dns fail")
        with pytest.raises(exa_search.ExaTransientError) as ei:
            exa_search.call_exa("/search", {"query": "x"}, api_key="k")
        assert ei.value.http_status is None
        assert "dns fail" in str(ei.value)


def test_call_exa_raises_malformed_on_bad_json():
    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.read.return_value = b"<html>not json</html>"
    fake_resp.__enter__ = lambda self: fake_resp
    fake_resp.__exit__ = lambda *a: None
    with patch("urllib.request.urlopen", return_value=fake_resp):
        with pytest.raises(exa_search.ExaMalformedResponseError):
            exa_search.call_exa("/search", {"query": "x"}, api_key="k")


def test_call_exa_returns_tuple_on_success():
    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.read.return_value = b'{"results":[{"url":"u","title":"t"}],"costDollars":{"total":0.01}}'
    fake_resp.__enter__ = lambda self: fake_resp
    fake_resp.__exit__ = lambda *a: None
    with patch("urllib.request.urlopen", return_value=fake_resp):
        status, body, latency = exa_search.call_exa("/search", {"query": "x"}, api_key="k")
        assert status == 200
        assert body["results"][0]["url"] == "u"
        assert latency >= 0
