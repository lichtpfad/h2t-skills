"""Provider-core tests for h2t_ops.connectors.research.exa."""
from __future__ import annotations

import io
import inspect
import json
import tomllib
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from h2t_ops.core.errors import AuthError, ConfigError, NetworkError, ProviderError, UsageError
from h2t_ops.connectors.research import exa


def _args(**kwargs):
    defaults = dict(
        mode="generic",
        start_date=None,
        end_date=None,
        include_domains=None,
        exclude_domains=None,
        include_text=None,
        exclude_text=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _full_args(**kwargs):
    defaults = dict(
        mode="generic",
        query="Rejuve.bio Switzerland",
        num_results=None,
        additional_queries=None,
        start_date=None,
        end_date=None,
        include_domains=None,
        exclude_domains=None,
        include_text=None,
        exclude_text=None,
        country=None,
        full_text=False,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _mock_urlopen_response(status, body):
    resp = MagicMock()
    resp.status = status
    if isinstance(body, bytes):
        resp.read.return_value = body
    else:
        resp.read.return_value = json.dumps(body).encode("utf-8")
    resp.__enter__ = lambda self: resp
    resp.__exit__ = lambda self, *a: None
    return resp


def _ok_response(results_count: int = 3, cost: float = 0.01) -> tuple[int, dict, int]:
    return (
        200,
        {
            "results": [
                {"url": f"https://example.com/{i}", "title": f"title {i}"}
                for i in range(results_count)
            ],
            "costDollars": {"total": cost},
        },
        100,
    )


def _patch_no_sleep(monkeypatch):
    monkeypatch.setattr(exa, "sleep_with_jitter", lambda s: None)


def test_mode_config_has_all_seven_modes():
    expected = {"fast", "generic", "news", "academic", "competitor", "people", "deep"}
    assert set(exa.MODE_CONFIG.keys()) == expected


def test_mode_config_competitor_uses_company_category():
    cfg = exa.MODE_CONFIG["competitor"]
    assert cfg["type"] == "auto"
    assert cfg["category"] == "company"
    assert cfg["num_results"] == 10


def test_mode_config_deep_uses_deep_type_default_10():
    cfg = exa.MODE_CONFIG["deep"]
    assert cfg["type"] == "deep"
    assert cfg["category"] is None
    assert cfg["num_results"] == 10


def test_mode_config_fast_uses_fast_type():
    cfg = exa.MODE_CONFIG["fast"]
    assert cfg["type"] == "fast"
    assert cfg["num_results"] == 10


def test_category_blocks_company_blocks_dates_and_domains():
    blocks = exa.CATEGORY_BLOCKS["company"]
    assert "start_date" in blocks
    assert "end_date" in blocks
    assert "include_domains" in blocks
    assert "exclude_domains" in blocks


def test_category_blocks_people_blocks_text_and_dates():
    blocks = exa.CATEGORY_BLOCKS["people"]
    assert "include_text" in blocks
    assert "exclude_text" in blocks
    assert "exclude_domains" in blocks
    assert "start_date" in blocks


def test_validate_competitor_with_start_date_raises_usageerror():
    with pytest.raises(UsageError):
        exa.validate_args(_args(mode="competitor", start_date="2025-01-01"))


def test_validate_people_with_exclude_text_raises_usageerror():
    with pytest.raises(UsageError):
        exa.validate_args(_args(mode="people", exclude_text=["foo"]))


def test_validate_include_text_multi_item_raises_usageerror():
    with pytest.raises(UsageError):
        exa.validate_args(_args(mode="generic", include_text=["foo", "bar"]))


def test_validate_valid_combinations_pass():
    exa.validate_args(
        _args(
            mode="news",
            start_date="2025-01-01",
            end_date="2026-04-18",
            include_domains=["techcrunch.com"],
        )
    )
    exa.validate_args(_args(mode="competitor"))
    exa.validate_args(_args(mode="generic", include_text=["solo"]))


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
    monkeypatch.setattr(exa, "SYSTEMPROMPTS_DIR", sp_dir)

    body, schema = exa.load_system_prompt("generic")

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
    monkeypatch.setattr(exa, "SYSTEMPROMPTS_DIR", sp_dir)

    body, schema = exa.load_system_prompt("competitor")

    assert "Competitive intel" in body
    assert schema == {"type": "object", "properties": {"name": {"type": "string"}}}


def test_load_system_prompt_missing_file_raises_configerror(tmp_path, monkeypatch):
    monkeypatch.setattr(exa, "SYSTEMPROMPTS_DIR", tmp_path)

    with pytest.raises(ConfigError):
        exa.load_system_prompt("missing")


def test_build_body_generic_minimal():
    body = exa.build_body(_full_args(mode="generic"), "SP", {})
    assert body["query"] == "Rejuve.bio Switzerland"
    assert body["type"] == "auto"
    assert body["numResults"] == 10
    assert body["systemPrompt"] == "SP"
    assert body["contents"]["highlights"]["maxCharacters"] == 4000
    assert "category" not in body


def test_build_body_competitor_sets_category():
    body = exa.build_body(_full_args(mode="competitor"), "SP", {})
    assert body["category"] == "company"
    assert body["type"] == "auto"


def test_build_body_news_with_dates_and_domains():
    body = exa.build_body(
        _full_args(
            mode="news",
            start_date="2025-01-01",
            end_date="2026-04-18",
            include_domains=["techcrunch.com"],
        ),
        "SP",
        {},
    )
    assert body["category"] == "news"
    assert body["startPublishedDate"] == "2025-01-01"
    assert body["endPublishedDate"] == "2026-04-18"
    assert body["includeDomains"] == ["techcrunch.com"]


def test_build_body_deep_with_additional_queries():
    body = exa.build_body(
        _full_args(mode="deep", additional_queries=["variation 1", "variation 2"]),
        "SP",
        {},
    )
    assert body["type"] == "deep"
    assert body["additionalQueries"] == ["variation 1", "variation 2"]


def test_build_body_with_schema_sets_structuredoutput():
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    body = exa.build_body(_full_args(mode="generic"), "SP", schema)
    assert body["outputSchema"] == schema
    assert body["structuredOutput"] is True


def test_build_body_num_results_override():
    body = exa.build_body(_full_args(mode="academic", num_results=25), "SP", {})
    assert body["numResults"] == 25


def test_call_exa_returns_tuple_on_success():
    payload = {"results": [{"title": "T", "url": "https://x"}], "costDollars": {"total": 0.007}}
    with patch("urllib.request.urlopen", return_value=_mock_urlopen_response(200, payload)):
        status, data, latency_ms = exa.call_exa("/search", {"query": "q"}, api_key="testkey")

    assert status == 200
    assert data["results"][0]["url"] == "https://x"
    assert latency_ms >= 0


def test_call_exa_raises_transient_on_5xx():
    err = urllib.error.HTTPError(
        url="https://api.exa.ai/search",
        code=503,
        msg="Service Unavailable",
        hdrs=None,
        fp=io.BytesIO(b'{"error":"down"}'),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(exa.ExaTransientError) as excinfo:
            exa.call_exa("/search", {"query": "q"}, api_key="testkey")
    assert excinfo.value.http_status == 503


def test_call_exa_raises_transient_on_429():
    err = urllib.error.HTTPError(
        url="https://api.exa.ai/search",
        code=429,
        msg="Too Many Requests",
        hdrs=None,
        fp=io.BytesIO(b'{"error":"rate limit"}'),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(exa.ExaTransientError) as excinfo:
            exa.call_exa("/search", {"query": "q"}, api_key="testkey")
    assert excinfo.value.http_status == 429


def test_call_exa_raises_permanent_on_4xx():
    err = urllib.error.HTTPError(
        url="https://api.exa.ai/search",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=io.BytesIO(b'{"error":"bad key"}'),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(exa.ExaPermanentError) as excinfo:
            exa.call_exa("/search", {"query": "q"}, api_key="testkey")
    assert excinfo.value.http_status == 401


def test_call_exa_raises_transient_on_urlerror():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("dns")):
        with pytest.raises(exa.ExaTransientError) as excinfo:
            exa.call_exa("/search", {"query": "q"}, api_key="testkey")
    assert excinfo.value.http_status is None


def test_call_exa_raises_malformed_on_bad_json():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen_response(200, b"<html>nope</html>")):
        with pytest.raises(exa.ExaMalformedResponseError):
            exa.call_exa("/search", {"query": "q"}, api_key="testkey")


def test_call_exa_raises_malformed_on_non_object_json():
    with patch("urllib.request.urlopen", return_value=_mock_urlopen_response(200, [])):
        with pytest.raises(exa.ExaMalformedResponseError):
            exa.call_exa("/search", {"query": "q"}, api_key="testkey")


def test_call_exa_sets_user_agent_header():
    seen = {}

    def fake_urlopen(req, timeout):
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        return _mock_urlopen_response(200, {"results": []})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        exa.call_exa("/search", {"query": "q"}, api_key="testkey")

    assert seen["headers"]["user-agent"] == f"exa_search.py/{exa.__version__} (h2t-ops:research)"


def test_preflight_ok_is_silent(capsys):
    with patch.object(exa, "call_exa", return_value=(200, {"results": []}, 10)) as call:
        exa.preflight("testkey")

    assert call.call_args.args[0] == "/search"
    assert call.call_args.args[2] == "testkey"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_preflight_network_failure_raises_networkerror():
    err = exa.ExaTransientError("dns", http_status=None, latency_ms=10)
    with patch.object(exa, "call_exa", side_effect=err):
        with pytest.raises(NetworkError):
            exa.preflight("testkey")


def test_preflight_auth_failure_raises_autherror():
    err = exa.ExaPermanentError("http 401", http_status=401, latency_ms=10)
    with patch.object(exa, "call_exa", side_effect=err):
        with pytest.raises(AuthError):
            exa.preflight("badkey")


def test_forbidden_cli_symbols_absent():
    forbidden = {
        "die",
        "slugify",
        "output_paths",
        "render_stdout_summary",
        "write_sources_json",
        "write_partial_md",
        "post_telemetry",
        "_build_parser",
        "main",
        "_run_search",
        "_run_crawl",
    }

    assert all(not hasattr(exa, name) for name in forbidden)


def test_all_does_not_export_private_helpers():
    assert "_classify_attempt_from_call" not in exa.__all__
    assert "_exit_code_for_failure" not in exa.__all__
    assert "_split_csv" not in exa.__all__


def test_search_with_retry_signature_keyword_only():
    signature = inspect.signature(exa.search_with_retry)

    for name in ("body", "api_key", "retry"):
        assert signature.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY


def test_split_csv():
    assert exa._split_csv(None) is None
    assert exa._split_csv("alpha, beta,,gamma ") == ["alpha", "beta", "gamma"]


def test_pyproject_includes_research_systemprompt_package_data():
    pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    package_data = data["tool"]["setuptools"]["package-data"]
    assert "systemprompts/*.md" in package_data["h2t_ops.connectors.research"]


def test_build_envelope_ok_shape():
    env = exa.build_envelope(
        status="OK",
        results=[{"url": "https://x"}],
        attempts=[
            {"engine": "exa", "endpoint": "/search", "http": 200, "latency_ms": 170, "error": None}
        ],
        meta={
            "query": "q",
            "mode": "generic",
            "num_results_requested": 10,
            "num_results_returned": 1,
            "timestamp": "2026-05-07T00:00:00+00:00",
        },
        total_cost_usd=0.012,
    )
    assert env["status"] == "OK"
    assert env["primary_engine"] == "exa"
    assert env["results"] == [{"url": "https://x"}]
    assert env["telemetry"]["total_latency_ms"] == 170
    assert env["telemetry"]["total_cost_usd"] == 0.012
    assert env["meta"]["envelope_version"] == exa.ENVELOPE_VERSION


def test_build_envelope_degraded_with_reason():
    env = exa.build_envelope(
        status="DEGRADED",
        results=[],
        attempts=[
            {
                "engine": "exa",
                "endpoint": "/search",
                "http": 200,
                "latency_ms": 50,
                "error": "exa_empty_results",
            }
        ],
        meta={"query": "q", "mode": "generic", "num_results_requested": 10, "num_results_returned": 0},
        total_cost_usd=0.0,
        reason_for_fallback="exa_empty_results",
    )
    assert env["status"] == "DEGRADED"
    assert env["telemetry"]["reason_for_fallback"] == "exa_empty_results"
    assert env["fallback_engine_used"] is None


def test_search_with_retry_ok_first_try(monkeypatch):
    _patch_no_sleep(monkeypatch)
    with patch.object(exa, "call_exa", return_value=_ok_response(3)) as m:
        env, exit_code = exa.search_with_retry(body={"query": "x"}, api_key="k", retry=True)
    assert m.call_count == 1
    assert env["status"] == "OK"
    assert exit_code == 0
    assert len(env["results"]) == 3
    assert len(env["telemetry"]["attempts"]) == 1


def test_search_with_retry_empty_then_empty_is_degraded(monkeypatch):
    _patch_no_sleep(monkeypatch)
    empty = (200, {"results": [], "costDollars": {"total": 0.0}}, 50)
    with patch.object(exa, "call_exa", side_effect=[empty, empty]) as m:
        env, exit_code = exa.search_with_retry(body={"query": "x"}, api_key="k", retry=True)
    assert m.call_count == 2
    assert env["status"] == "DEGRADED"
    assert exit_code == 0
    assert env["telemetry"]["reason_for_fallback"] == "exa_empty_results"
    assert all(a["error"] == "exa_empty_results" for a in env["telemetry"]["attempts"])


def test_search_with_retry_empty_then_ok_is_ok(monkeypatch):
    _patch_no_sleep(monkeypatch)
    empty = (200, {"results": [], "costDollars": {"total": 0.0}}, 50)
    with patch.object(exa, "call_exa", side_effect=[empty, _ok_response(2)]) as m:
        env, exit_code = exa.search_with_retry(body={"query": "x"}, api_key="k", retry=True)
    assert m.call_count == 2
    assert env["status"] == "OK"
    assert exit_code == 0
    assert env["telemetry"]["attempts"][0]["error"] == "exa_empty_results"
    assert env["telemetry"]["attempts"][1]["error"] is None


def test_search_with_retry_5xx_then_5xx_is_failed(monkeypatch):
    _patch_no_sleep(monkeypatch)
    err = exa.ExaTransientError("http 503", http_status=503, latency_ms=200)
    with patch.object(exa, "call_exa", side_effect=[err, err]) as m:
        env, exit_code = exa.search_with_retry(body={"query": "x"}, api_key="k", retry=True)
    assert m.call_count == 2
    assert env["status"] == "FAILED"
    assert exit_code == 2
    assert all(a["error"] == "exa_5xx_retryable" for a in env["telemetry"]["attempts"])


def test_search_with_retry_auth_error_is_failed_without_retry(monkeypatch):
    _patch_no_sleep(monkeypatch)
    err = exa.ExaPermanentError("http 401", http_status=401, latency_ms=40)
    with patch.object(exa, "call_exa", side_effect=err) as call:
        env, exit_code = exa.search_with_retry(body={"query": "x"}, api_key="k", retry=True)

    assert call.call_count == 1
    assert env["status"] == "FAILED"
    assert exit_code == 2
    assert env["telemetry"]["attempts"][0]["error"] == "exa_auth_error"


def test_search_with_retry_urlerror_then_urlerror_is_failed(monkeypatch):
    _patch_no_sleep(monkeypatch)
    err = exa.ExaTransientError("network: dns", http_status=None, latency_ms=300)
    with patch.object(exa, "call_exa", side_effect=[err, err]):
        env, exit_code = exa.search_with_retry(body={"query": "x"}, api_key="k", retry=True)
    assert env["status"] == "FAILED"
    assert exit_code == 3
    assert all(a["error"] == "exa_network_timeout" for a in env["telemetry"]["attempts"])


def test_search_with_retry_429_triggers_retry(monkeypatch):
    _patch_no_sleep(monkeypatch)
    err = exa.ExaTransientError("http 429", http_status=429, latency_ms=120)
    with patch.object(exa, "call_exa", side_effect=[err, _ok_response(1)]) as m:
        env, exit_code = exa.search_with_retry(body={"query": "x"}, api_key="k", retry=True)
    assert m.call_count == 2
    assert env["status"] == "OK"
    assert exit_code == 0
    assert env["telemetry"]["attempts"][0]["error"] == "exa_5xx_retryable"


def test_search_with_retry_non_dict_json_is_malformed(monkeypatch):
    _patch_no_sleep(monkeypatch)
    with patch.object(exa, "call_exa", return_value=(200, [], 40)):
        env, exit_code = exa.search_with_retry(body={"query": "x"}, api_key="k", retry=False)

    assert env["status"] == "FAILED"
    assert exit_code == 2
    assert env["results"] == []
    assert env["telemetry"]["attempts"][0]["error"] == "exa_malformed_json"


def test_search_with_retry_results_must_be_list(monkeypatch):
    _patch_no_sleep(monkeypatch)
    malformed = {"results": {"url": "https://example.com"}}
    with patch.object(exa, "call_exa", return_value=(200, malformed, 40)):
        env, exit_code = exa.search_with_retry(body={"query": "x"}, api_key="k", retry=False)

    assert env["status"] == "FAILED"
    assert exit_code == 2
    assert env["results"] == []
    assert env["telemetry"]["attempts"][0]["error"] == "exa_malformed_json"


def test_search_with_retry_no_retry_flag_disables_retries(monkeypatch):
    _patch_no_sleep(monkeypatch)
    empty = (200, {"results": [], "costDollars": {"total": 0.0}}, 50)
    with patch.object(exa, "call_exa", side_effect=[empty, empty]) as m:
        env, exit_code = exa.search_with_retry(body={"query": "x"}, api_key="k", retry=False)
    assert m.call_count == 1
    assert env["status"] == "DEGRADED"
    assert exit_code == 0
    assert len(env["telemetry"]["attempts"]) == 1


# ── find_similar ────────────────────────────────────────────────────────────

def test_find_similar_ok(monkeypatch):
    _patch_no_sleep(monkeypatch)
    response_body = {
        "results": [
            {"url": "https://example.com/a", "title": "Similar A"},
            {"url": "https://example.com/b", "title": "Similar B"},
        ],
        "costDollars": {"total": 0.005},
    }
    monkeypatch.setattr(
        exa,
        "call_exa",
        lambda endpoint, body, api_key, **kw: (200, response_body, 80),
    )

    envelope, exit_code = exa.find_similar(
        "https://derivative.ca", api_key="test-key", num_results=5
    )

    assert exit_code == 0
    assert envelope["status"] == "OK"
    assert len(envelope["results"]) == 2
    assert envelope["meta"]["source_url"] == "https://derivative.ca"
    assert envelope["telemetry"]["total_cost_usd"] == pytest.approx(0.005)


def test_find_similar_empty_results(monkeypatch):
    _patch_no_sleep(monkeypatch)
    monkeypatch.setattr(
        exa,
        "call_exa",
        lambda endpoint, body, api_key, **kw: (200, {"results": [], "costDollars": {"total": 0.0}}, 60),
    )

    envelope, exit_code = exa.find_similar("https://example.com", api_key="k")

    assert exit_code == 0
    assert envelope["status"] == "DEGRADED"
    assert envelope["results"] == []


def test_find_similar_auth_error(monkeypatch):
    def _raise(*a, **kw):
        raise exa.ExaPermanentError("http 401", http_status=401, latency_ms=10)

    monkeypatch.setattr(exa, "call_exa", _raise)

    envelope, exit_code = exa.find_similar("https://example.com", api_key="bad")

    assert exit_code == 4
    assert envelope["status"] == "FAILED"


# ── answer ──────────────────────────────────────────────────────────────────

def test_answer_ok(monkeypatch):
    response_body = {
        "answer": "TouchDesigner supports GPU-based particle systems via POP networks.",
        "citations": [
            {"url": "https://derivative.ca/doc", "title": "TD Docs"},
        ],
    }
    monkeypatch.setattr(
        exa,
        "call_exa",
        lambda endpoint, body, api_key, **kw: (200, response_body, 120),
    )

    envelope, exit_code = exa.answer("TouchDesigner POP basics", api_key="k")

    assert exit_code == 0
    assert envelope["status"] == "OK"
    assert "TouchDesigner" in envelope["answer_text"]
    assert len(envelope["citations"]) == 1
    assert envelope["meta"]["query"] == "TouchDesigner POP basics"


def test_answer_auth_error(monkeypatch):
    def _raise(*a, **kw):
        raise exa.ExaPermanentError("http 403", http_status=403, latency_ms=10)

    monkeypatch.setattr(exa, "call_exa", _raise)

    envelope, exit_code = exa.answer("anything", api_key="bad")

    assert exit_code == 4
    assert envelope["status"] == "FAILED"


# ── research (Exa Research API) ───────────────────────────────────────────────

def test_call_exa_get_sends_no_body():
    seen = {}

    def fake_urlopen(req, timeout):
        seen["method"] = req.get_method()
        seen["data"] = req.data
        return _mock_urlopen_response(200, {"status": "running"})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        status, data, latency = exa.call_exa(
            "/research/v1/r_x", {}, api_key="testkey", method="GET"
        )

    assert seen["method"] == "GET"
    assert seen["data"] is None
    assert data["status"] == "running"


def test_research_models_and_default():
    assert exa.RESEARCH_MODELS == ("exa-research-fast", "exa-research", "exa-research-pro")
    assert exa.RESEARCH_DEFAULT_MODEL == "exa-research-fast"


def test_create_research_posts_instructions_and_model(monkeypatch):
    seen = {}

    def fake_call(endpoint, body, api_key, **kw):
        seen["endpoint"] = endpoint
        seen["body"] = body
        seen["method"] = kw.get("method", "POST")
        return (201, {"researchId": "r_1", "status": "running", "model": body["model"]}, 30)

    monkeypatch.setattr(exa, "call_exa", fake_call)
    data = exa.create_research(
        "Summarize X", model="exa-research", output_schema={"type": "object"}, api_key="k"
    )

    assert seen["endpoint"] == "/research/v1"
    assert seen["method"] == "POST"
    assert seen["body"]["instructions"] == "Summarize X"
    assert seen["body"]["model"] == "exa-research"
    assert seen["body"]["outputSchema"] == {"type": "object"}
    assert data["researchId"] == "r_1"


def test_create_research_omits_schema_when_absent(monkeypatch):
    seen = {}

    def fake_call(endpoint, body, api_key, **kw):
        seen["body"] = body
        return (201, {"researchId": "r_2", "status": "running"}, 20)

    monkeypatch.setattr(exa, "call_exa", fake_call)
    exa.create_research("Q", model="exa-research-fast", output_schema=None, api_key="k")
    assert "outputSchema" not in seen["body"]


def test_get_research_uses_path_param_and_get(monkeypatch):
    seen = {}

    def fake_call(endpoint, body, api_key, **kw):
        seen["endpoint"] = endpoint
        seen["method"] = kw.get("method")
        return (200, {"researchId": "r_1", "status": "completed", "output": {"content": "done"}}, 15)

    monkeypatch.setattr(exa, "call_exa", fake_call)
    data = exa.get_research("r_1", api_key="k")

    assert seen["endpoint"] == "/research/v1/r_1"
    assert seen["method"] == "GET"
    assert data["status"] == "completed"


def test_research_task_async_returns_running(monkeypatch):
    monkeypatch.setattr(
        exa, "create_research",
        lambda instructions, *, model, output_schema, api_key: {"researchId": "r_9", "status": "running"},
    )
    env, exit_code = exa.research_task("Q", api_key="k", wait=False)
    assert exit_code == 0
    assert env["status"] == "RUNNING"
    assert env["research_id"] == "r_9"
    assert env["model"] == exa.RESEARCH_DEFAULT_MODEL


def test_research_task_wait_completes(monkeypatch):
    monkeypatch.setattr(exa, "sleep_with_jitter", lambda s: None)
    monkeypatch.setattr(
        exa, "create_research",
        lambda instructions, *, model, output_schema, api_key: {"researchId": "r_1", "status": "running"},
    )
    polls = iter([
        {"researchId": "r_1", "status": "running"},
        {"researchId": "r_1", "status": "completed",
         "output": {"content": "Answer.", "costDollars": {"total": 0.02, "numSearches": 3, "numPages": 5, "reasoningTokens": 900}},
         "citations": [{"url": "https://x", "title": "X"}]},
    ])
    monkeypatch.setattr(exa, "get_research", lambda rid, *, api_key: next(polls))

    env, exit_code = exa.research_task("Q", api_key="k", wait=True, poll_interval=0.0, timeout_s=10.0)

    assert exit_code == 0
    assert env["status"] == "OK"
    assert env["output"]["content"] == "Answer."
    assert env["results"] == [{"url": "https://x", "title": "X"}]
    assert env["telemetry"]["total_cost_usd"] == 0.02
    assert env["telemetry"]["num_searches"] == 3
    assert env["telemetry"]["num_pages"] == 5
    assert env["telemetry"]["reasoning_tokens"] == 900
    assert env["meta"]["query"] == "Q"


def test_research_task_failed_status(monkeypatch):
    monkeypatch.setattr(exa, "sleep_with_jitter", lambda s: None)
    monkeypatch.setattr(
        exa, "create_research",
        lambda instructions, *, model, output_schema, api_key: {"researchId": "r_1", "status": "running"},
    )
    monkeypatch.setattr(
        exa, "get_research",
        lambda rid, *, api_key: {"researchId": "r_1", "status": "failed", "error": "boom"},
    )
    env, exit_code = exa.research_task("Q", api_key="k", wait=True, poll_interval=0.0, timeout_s=10.0)
    assert env["status"] == "FAILED"
    assert exit_code == 1
    assert env["telemetry"]["reason_for_fallback"] == "boom"


def test_research_task_timeout(monkeypatch):
    monkeypatch.setattr(exa, "sleep_with_jitter", lambda s: None)
    ticks = iter([0.0, 5.0, 20.0])
    monkeypatch.setattr(exa.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(
        exa, "create_research",
        lambda instructions, *, model, output_schema, api_key: {"researchId": "r_1", "status": "running"},
    )
    monkeypatch.setattr(
        exa, "get_research",
        lambda rid, *, api_key: {"researchId": "r_1", "status": "running"},
    )
    env, exit_code = exa.research_task("Q", api_key="k", wait=True, poll_interval=0.0, timeout_s=10.0)
    assert env["status"] == "FAILED"
    assert exit_code == 3
    assert env["telemetry"]["reason_for_fallback"] == "research_timeout"


def test_research_task_create_auth_error(monkeypatch):
    def _raise(instructions, *, model, output_schema, api_key):
        raise exa.ExaPermanentError("http 401", http_status=401, latency_ms=10)
    monkeypatch.setattr(exa, "create_research", _raise)
    env, exit_code = exa.research_task("Q", api_key="bad", wait=True)
    assert env["status"] == "FAILED"
    assert exit_code == 4


def test_research_task_poll_error_is_failed(monkeypatch):
    monkeypatch.setattr(exa, "sleep_with_jitter", lambda s: None)
    monkeypatch.setattr(
        exa, "create_research",
        lambda instructions, *, model, output_schema, api_key: {"researchId": "r_1", "status": "running"},
    )

    def _raise(rid, *, api_key):
        raise exa.ExaPermanentError("http 500", http_status=500, latency_ms=10)

    monkeypatch.setattr(exa, "get_research", _raise)
    env, exit_code = exa.research_task("Q", api_key="k", wait=True, poll_interval=0.0, timeout_s=10.0)
    assert env["status"] == "FAILED"
    assert exit_code == 1
    assert env["telemetry"]["reason_for_fallback"] == "exa_poll_failed"


def test_research_task_poll_backoff_grows(monkeypatch):
    intervals = []
    monkeypatch.setattr(exa, "sleep_with_jitter", lambda s: intervals.append(s))
    monkeypatch.setattr(
        exa, "create_research",
        lambda instructions, *, model, output_schema, api_key: {"researchId": "r_1", "status": "running"},
    )
    polls = iter([
        {"researchId": "r_1", "status": "running"},
        {"researchId": "r_1", "status": "running"},
        {"researchId": "r_1", "status": "completed", "output": {"content": "ok"}, "citations": []},
    ])
    monkeypatch.setattr(exa, "get_research", lambda rid, *, api_key: next(polls))
    exa.research_task("Q", api_key="k", wait=True, poll_interval=2.0, timeout_s=1000.0)
    assert intervals == [2.0, 3.0]
