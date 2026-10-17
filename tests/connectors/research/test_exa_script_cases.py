"""The cases of the deleted exa_search.py suite that test_exa.py did not already hold (#541).

exa_search.py was deleted in Task 12. Its library half lives on as
h2t_ops/connectors/research/exa.py, and `h2t-ops research search|crawl|preflight` replaced
its CLI. The library cases run against the package module; the CLI cases run the connector
command, and a comment says where the connector differs from the script on purpose (exit
codes follow the connector standard, failures go to stderr as an envelope).

Cases of the script's own surface were not carried over, because that surface is gone and
the package already tests its replacement:

- script_exists, version_flag, die, main_reconfigures_stdout_to_utf8: the script's process
  framing. The connector's UTF-8 output is tests/core/test_output.py.
- mode_config_has_all_seven_modes: test_exa.py::test_mode_config_has_all_ten_modes.
- validate_* (3), load_system_prompt_missing_file_exits_1: the same cases in test_exa.py,
  raising UsageError / ConfigError instead of exiting.
- preflight_* (4): test_exa.py::test_preflight_ok_is_silent, ..._network_failure_raises_
  networkerror, ..._auth_failure_raises_autherror, and test_client.py::test_preflight_
  missing_exa_key_fails_before_provider_call. The script read a 403 as "reachable"; the
  connector reads it as an auth failure, on purpose.
- slugify (3), output_paths, render_stdout_summary, write_sources_json, write_partial_md,
  default_stdout_is_markdown_summary, envelope_in_sources_json_always_written,
  run_crawl_writes_files: the script's file and stdout formats. The connector's are
  test_client.py::test_artifact_paths_*, ..._search_ok_writes_artifacts and
  ..._crawl_ok_writes_artifacts.
- envelope_flag_4xx_prints_envelope_and_stderr: run_search_permanent_error below.
- main_calls_h2t_secrets_bootstrap, main_handles_missing_secrets_file: the script's own
  secrets loader (h2t_secrets.py, deleted). test_client.py::test_resolve_key_h2t_secrets_file
  and the *_missing_exa_key_* cases cover the connector's.

emit_eval_records_research_cost was dropped at first, because the connector had no SkillEval
emission. Fix round 1 ported `_emit_eval` into exa.py, called after search and crawl as the
script did, and the case is back at the end of this file with a round trip through
`h2t-ops evals report`.
"""
import io
import json
import urllib.error
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from h2t_ops.connectors.research import exa as exa_search


@pytest.fixture(autouse=True)
def _live_module(monkeypatch):
    """Bind the module the connector will import (the network refusal is in conftest.py).

    test_commands.py pops the research modules from sys.modules to prove they load lazily,
    so the module imported at the top of this file can be a stale copy that the client no
    longer calls: a patch on it then misses, and the request goes out for real. Measured
    2026-10-17, when exactly that sent fake keys to api.exa.ai.
    """
    import importlib

    monkeypatch.setitem(globals(), "exa_search", importlib.import_module("h2t_ops.connectors.research.exa"))


def test_category_blocks_financial_report_blocks_exclude_text():
    assert "exclude_text" in exa_search.CATEGORY_BLOCKS["financial report"]


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


# --- load_system_prompt tests ---


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


# --- slugify & output_paths tests ---


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


# Research telemetry unified on SkillEval (D4, #312); bespoke post_telemetry removed.
# Its old awaiting_endpoint/disabled/buffered/sent contract tests deleted with the fn.
# Coverage is now test_emit_eval_records_research_cost (SkillEval local emit).


# --- main() argparse tests ---


def _cli(argv: list[str]) -> int:
    """`h2t-ops research <argv>`: the command that replaced `exa_search.py <argv>`."""
    from h2t_ops import cli

    return cli.dispatch(["research", *argv])


def _failure(captured) -> dict:
    """The connector writes a failure's envelope to stderr, on its last line."""
    return json.loads(captured.err.strip().splitlines()[-1])["error"]


def _search(tmp_path, *extra) -> list[str]:
    return ["search", "--query", "x", "--mode", "generic", "--num-results", "3",
            "--output-dir", str(tmp_path / "out"), "--project", "p", "--json", *extra]


def _attempts(failure: dict) -> list[dict]:
    return failure["details"]["provider_envelope"]["telemetry"]["attempts"]


def test_cli_preflight_invokes_preflight(monkeypatch, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    with patch("urllib.request.urlopen", return_value=_mock_urlopen_response(200, {})):
        rc = _cli(["preflight", "--json"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["result"]["status"] == "OK"


def test_cli_search_requires_query(capsys):
    assert _cli(["search", "--mode", "generic"]) == 2
    err = capsys.readouterr().err
    assert "--query" in err or "required" in err


def test_cli_search_unknown_mode_argparse_rejects(capsys):
    assert _cli(["search", "--query", "x", "--mode", "notamode"]) == 2
    assert "invalid choice" in capsys.readouterr().err.lower()


def test_cli_crawl_requires_url(capsys):
    assert _cli(["crawl"]) == 2


def test_run_search_happy_path_exits_0(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    out_dir = tmp_path / "out"
    response = _sample_exa_response()
    with patch("urllib.request.urlopen", return_value=_mock_urlopen_response(200, response)):
        rc = _cli([
            "search", "--query", "Rejuve.bio Switzerland",
            "--mode", "generic",
            "--output-dir", str(out_dir),
            "--project", "rejuve", "--json",
        ])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)["result"]
    assert result["status"] == "OK"
    assert "https://rejuve.bio/about" in [r["url"] for r in result["results"]]
    # The script named its files <project>-<topic>-<date>; the connector adds the kind.
    files = list(out_dir.glob("rejuve-rejuve-bio-switzerland-search-*"))
    assert any(p.name.endswith(".partial.md") for p in files)
    assert any(p.name.endswith(".sources.json") for p in files)


def test_run_search_invalid_combo_exits_1(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    rc = _cli([
        "search", "--query", "x",
        "--mode", "competitor",
        "--start-date", "2025-01-01",
        "--project", "stub",
        "--output-dir", str(tmp_path), "--json",
    ])
    # The script exited 1 with EXA_ERROR:ARGS; the connector's usage exit is 2.
    assert rc == 2
    assert "EXA_ERROR:ARGS" in _failure(capsys.readouterr())["message"]


def test_run_search_http_429_exits_2(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)
    err = urllib.error.HTTPError(
        url="https://api.exa.ai/search", code=429, msg="Too Many",
        hdrs=None, fp=io.BytesIO(b'{"error":"rate"}'),
    )
    with patch("urllib.request.urlopen", side_effect=[err, err]):
        rc = _cli(_search(tmp_path))
    # The script exited 2 (EXA_ERROR:API); a provider failure is exit 1 here.
    assert rc == 1
    assert len(_attempts(_failure(capsys.readouterr()))) == 2


# --- call_exa typed exceptions (Task 1) ---


# --- _run_search exception → exit code mapping (Task 1 review fix) ---


def _make_search_systemprompts(tmp_path):
    """Helper: minimal systemprompts dir for _run_search integration tests."""
    sp_dir = tmp_path / "systemprompts"
    sp_dir.mkdir()
    (sp_dir / "generic.md").write_text("---\n---\nsp\n", encoding="utf-8")
    return sp_dir


def test_run_search_permanent_error_exits_2_with_api_message(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    err = exa_search.ExaPermanentError("http 401", http_status=401, latency_ms=50, body={"error": "bad"})
    with patch.object(exa_search, "call_exa", side_effect=err):
        rc = _cli(_search(tmp_path))
    # A rejected key is the auth exit, 4 (the script exited 2).
    assert rc == 4
    failure = _failure(capsys.readouterr())
    assert failure["type"] == "auth"
    assert _attempts(failure)[0]["http"] == 401


def test_run_search_transient_with_status_exits_2_with_api_message(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)
    err = exa_search.ExaTransientError("http 503", http_status=503, latency_ms=200, body={"error": "down"})
    with patch.object(exa_search, "call_exa", side_effect=err):
        rc = _cli(_search(tmp_path))
    assert rc == 1
    failure = _failure(capsys.readouterr())
    assert failure["type"] == "provider"
    assert _attempts(failure)[0]["http"] == 503


def test_run_search_transient_no_status_exits_3_with_network_message(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)
    err = exa_search.ExaTransientError("timed out", http_status=None, latency_ms=300)
    with patch.object(exa_search, "call_exa", side_effect=err):
        rc = _cli(_search(tmp_path))
    # The script exited 3; the connector's network exit is 6.
    assert rc == 6
    assert _failure(capsys.readouterr())["type"] == "network"


def test_run_search_malformed_exits_2_with_malformed_message(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    err = exa_search.ExaMalformedResponseError("non-JSON body", latency_ms=100)
    with patch.object(exa_search, "call_exa", side_effect=err):
        rc = _cli(_search(tmp_path))
    assert rc == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert _attempts(_failure(captured))[0]["error"] == "exa_malformed_json"


# --- sleep_with_jitter (Task 2) ---

def test_sleep_with_jitter_calls_time_sleep_with_jitter_range():
    sleeps = []
    with patch("time.sleep", side_effect=lambda s: sleeps.append(s)), \
         patch("random.uniform", return_value=0.25):
        exa_search.sleep_with_jitter(2.0)
    assert sleeps == [2.25]


def test_sleep_with_jitter_zero_base():
    sleeps = []
    with patch("time.sleep", side_effect=lambda s: sleeps.append(s)), \
         patch("random.uniform", return_value=0.0):
        exa_search.sleep_with_jitter(0.0)
    assert sleeps == [0.0]


# --- build_envelope (Task 3) ---


def test_build_envelope_failed_empty_results():
    env = exa_search.build_envelope(
        status="FAILED",
        results=[],
        attempts=[{"engine": "exa", "endpoint": "/search", "http": 401,
                   "latency_ms": 50, "error": "exa_4xx_nonretryable"}],
        meta={"query": "q", "mode": "generic", "num_results_requested": 10,
              "num_results_returned": 0, "timestamp": "2026-05-07T00:00:00+00:00"},
        total_cost_usd=0.0,
    )
    assert env["status"] == "FAILED"
    assert env["results"] == []


# --- search_with_retry (Task 4) ---

def _ok_response(results_count: int = 3, cost: float = 0.01) -> tuple[int, dict, int]:
    return (200, {
        "results": [{"url": f"u{i}", "title": f"t{i}"} for i in range(results_count)],
        "costDollars": {"total": cost},
    }, 100)


def _patch_no_sleep(monkeypatch):
    monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)


def test_search_with_retry_5xx_then_ok_is_ok(monkeypatch):
    _patch_no_sleep(monkeypatch)
    err = exa_search.ExaTransientError("http 503", http_status=503, latency_ms=200)
    with patch.object(exa_search, "call_exa", side_effect=[err, _ok_response(1)]):
        env, exit_code = exa_search.search_with_retry(
            body={"query": "x"}, api_key="k", retry=True,
        )
    assert env["status"] == "OK"
    assert exit_code == 0
    assert len(env["telemetry"]["attempts"]) == 2


def test_search_with_retry_4xx_no_retry_is_failed(monkeypatch):
    _patch_no_sleep(monkeypatch)
    err = exa_search.ExaPermanentError("http 401", http_status=401, latency_ms=80, body={"e": "k"})
    with patch.object(exa_search, "call_exa", side_effect=[err]) as m:
        env, exit_code = exa_search.search_with_retry(
            body={"query": "x"}, api_key="k", retry=True,
        )
    assert m.call_count == 1
    assert env["status"] == "FAILED"
    assert exit_code == 2
    # The script labelled a 401 exa_4xx_nonretryable; the package names it an auth error.
    assert env["telemetry"]["attempts"][0]["error"] == "exa_auth_error"


def test_search_with_retry_urlerror_then_ok_is_ok(monkeypatch):
    _patch_no_sleep(monkeypatch)
    err = exa_search.ExaTransientError("network: dns", http_status=None, latency_ms=300)
    with patch.object(exa_search, "call_exa", side_effect=[err, _ok_response(1)]):
        env, exit_code = exa_search.search_with_retry(
            body={"query": "x"}, api_key="k", retry=True,
        )
    assert env["status"] == "OK"
    assert exit_code == 0


def test_search_with_retry_malformed_no_retry(monkeypatch):
    _patch_no_sleep(monkeypatch)
    err = exa_search.ExaMalformedResponseError("non-JSON body", latency_ms=70)
    with patch.object(exa_search, "call_exa", side_effect=[err]) as m:
        env, exit_code = exa_search.search_with_retry(
            body={"query": "x"}, api_key="k", retry=True,
        )
    assert m.call_count == 1
    assert env["status"] == "FAILED"
    assert exit_code == 2
    assert env["telemetry"]["attempts"][0]["error"] == "exa_malformed_json"


def test_search_with_retry_meta_fields_populated(monkeypatch):
    _patch_no_sleep(monkeypatch)
    with patch.object(exa_search, "call_exa", return_value=_ok_response(2)):
        env, _ = exa_search.search_with_retry(
            body={"query": "find me", "numResults": 10, "type": "auto"},
            api_key="k", retry=True, mode="generic",
        )
    assert env["meta"]["query"] == "find me"
    assert env["meta"]["mode"] == "generic"
    assert env["meta"]["num_results_requested"] == 10
    assert env["meta"]["num_results_returned"] == 2
    assert "timestamp" in env["meta"]


# --- backoff budget cap (Task 5) ---

def test_warn_emitted_when_budget_exhausted(monkeypatch, capsys):
    sleeps_called = []

    def fake_sleep(s):
        sleeps_called.append(s)
    monkeypatch.setattr(exa_search, "sleep_with_jitter", fake_sleep)
    monkeypatch.setattr(exa_search, "RETRY_BUDGET_SECONDS", 0.5)
    err = exa_search.ExaTransientError("http 503", http_status=503, latency_ms=200)
    with patch.object(exa_search, "call_exa", side_effect=[err, err]):
        env, exit_code = exa_search.search_with_retry(
            body={"query": "x"}, api_key="k", retry=True,
        )
    # The script also printed EXA_WARN:RETRY_BUDGET_EXHAUSTED; the library prints nothing.
    assert capsys.readouterr().err == ""
    assert env["status"] == "FAILED"
    assert exit_code == 2
    assert sleeps_called == []


# --- CLI flags --envelope, --no-retry (Task 6) ---

def _make_search_argv(extra: list[str] | None = None) -> list[str]:
    argv = ["search", "--query", "anything", "--mode", "generic", "--num-results", "3",
            "--project", "p"]
    if extra:
        argv.extend(extra)
    return argv


def _setup_sp(monkeypatch, tmp_path):
    """Override SYSTEMPROMPTS_DIR for hermetic CLI tests."""
    sp_dir = tmp_path / "systemprompts"
    sp_dir.mkdir(exist_ok=True)
    (sp_dir / "generic.md").write_text("---\n---\nsp\n", encoding="utf-8")
    monkeypatch.setattr(exa_search, "SYSTEMPROMPTS_DIR", sp_dir)


def test_envelope_flag_prints_json_to_stdout(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("EXA_API_KEY", "k")
    with patch.object(exa_search, "call_exa", return_value=(200, {
        "results": [{"url": "u", "title": "t", "highlights": ["snippet"]}],
        "costDollars": {"total": 0.01},
    }, 100)):
        rc = _cli(["search", "--query", "anything", "--mode", "generic", "--num-results", "3",
                   "--output-dir", str(tmp_path / "out"), "--project", "p", "--envelope"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)["result"]  # --envelope is --json
    assert payload["status"] == "OK"
    assert payload["primary_engine"] == "exa"


def test_no_retry_flag_disables_retries_via_cli(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)
    empty = (200, {"results": [], "costDollars": {"total": 0.0}}, 50)
    with patch.object(exa_search, "call_exa", side_effect=[empty, empty]) as m:
        rc = _cli(_search(tmp_path, "--no-retry"))
    assert m.call_count == 1
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["result"]["status"] == "DEGRADED"


# --- FAILED + --envelope: JSON envelope must reach stdout (Task 6 Fix 1) ---

def _make_search_argv_with_envelope(tmp_path):
    out_dir = tmp_path / "out"
    return ["search", "--query", "x", "--mode", "generic", "--num-results", "3",
            "--output-dir", str(out_dir), "--project", "p", "--envelope"]


def test_envelope_flag_5xx_exhausted_prints_envelope(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)
    err = urllib.error.HTTPError(
        url="https://api.exa.ai/search", code=503, msg="Service Unavailable",
        hdrs=None, fp=io.BytesIO(b'{"error":"down"}'),
    )
    with patch("urllib.request.urlopen", side_effect=[err, err]):
        rc = _cli(_search(tmp_path))
    assert rc == 1
    failure = _failure(capsys.readouterr())
    assert failure["details"]["provider_envelope"]["status"] == "FAILED"
    attempts = _attempts(failure)
    assert len(attempts) == 2
    assert all(a["error"] == "exa_5xx_retryable" for a in attempts)


def test_envelope_flag_network_exhausted_prints_envelope(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("dns")):
        rc = _cli(_search(tmp_path))
    assert rc == 6
    failure = _failure(capsys.readouterr())
    assert failure["details"]["provider_envelope"]["status"] == "FAILED"
    assert all(a["error"] == "exa_network_timeout" for a in _attempts(failure))


def test_envelope_flag_malformed_prints_envelope(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)
    fake_resp = MagicMock()
    fake_resp.status = 200
    fake_resp.read.return_value = b"<html>not json</html>"
    fake_resp.__enter__ = lambda self: fake_resp
    fake_resp.__exit__ = lambda *a: None
    with patch("urllib.request.urlopen", return_value=fake_resp):
        rc = _cli(_search(tmp_path))
    assert rc == 1
    captured = capsys.readouterr()
    assert "JSONDecodeError" not in captured.err
    assert "Traceback" not in captured.err
    assert _attempts(_failure(captured))[0]["error"] == "exa_malformed_json"


def test_envelope_flag_failed_writes_sources_json(monkeypatch, tmp_path):
    """FAILED status still writes the artifacts so post-hoc analysis works."""
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)
    err = urllib.error.HTTPError(
        url="https://api.exa.ai/search", code=401, msg="Unauthorized",
        hdrs=None, fp=io.BytesIO(b'{"error":"bad"}'),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        assert _cli(_search(tmp_path)) == 4
    out_dir = tmp_path / "out"
    assert len(list(out_dir.glob("*.sources.json"))) == 1
    # The script kept the envelope in the sidecar's meta; the artifact records the status.
    artifact = json.loads(next(out_dir.glob("*.artifact.json")).read_text(encoding="utf-8"))
    assert artifact["provider_status"] == "FAILED"


# --- crawl envelope sidecar (Task 7) ---

def test_crawl_writes_envelope_to_sources_json(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "k")
    with patch.object(exa_search, "call_exa", return_value=(200, {
        "results": [{"url": "https://x.example", "text": "body"}],
        "costDollars": {"total": 0.001},
    }, 200)):
        rc = _cli([
            "crawl", "--url", "https://x.example",
            "--output-dir", str(tmp_path), "--project", "p", "--json",
        ])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)["result"]
    assert result["status"] == "OK"
    assert result["primary_engine"] == "exa"
    assert len(list(tmp_path.glob("*.sources.json"))) == 1


def test_crawl_empty_is_degraded(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "k")
    with patch.object(exa_search, "call_exa", return_value=(200, {
        "results": [], "costDollars": {"total": 0.0},
    }, 80)):
        rc = _cli([
            "crawl", "--url", "https://x.example",
            "--output-dir", str(tmp_path), "--project", "p", "--json",
        ])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["result"]["status"] == "DEGRADED"


# --- h2t_secrets bootstrap integration (Task 4 of secrets-loader) ---




def test_emit_eval_records_research_cost(tmp_path, monkeypatch):
    """_emit_eval writes a local SkillEval session carrying research cost + core.*."""
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    monkeypatch.setenv("H2T_EVALS_ROOT", str(tmp_path / "evals"))
    envelope = {
        "status": "OK",
        "results": [1, 2, 3],
        "telemetry": {"total_cost_usd": 0.037, "total_latency_ms": 1200,
                      "attempts": [{"http": 200, "latency_ms": 1200, "error": None}]},
        "meta": {"timestamp": "2026-07-12T00:00:00Z"},
    }
    exa_search._emit_eval(envelope, exit_code=0, project="h2t-skills", mode="generic")
    files = list((tmp_path / "evals" / "research" / "sessions").glob("*.json"))
    assert len(files) == 1
    keys = {m["key"] for m in json.loads(files[0].read_text())["metrics"]}
    assert "skills.research_cost_usd" in keys
    assert "core.task_success" in keys


def _sessions(root) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((root / "research" / "sessions").glob("*.json"))]


def test_a_search_writes_a_session_that_evals_report_reads(monkeypatch, tmp_path, capsys):
    """The round trip: `research search` writes the record, `evals report` counts it."""
    evals = tmp_path / "evals"
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    monkeypatch.setenv("H2T_EVALS_ROOT", str(evals))
    monkeypatch.setenv("EXA_API_KEY", "k")
    with patch.object(exa_search, "call_exa", return_value=(200, {
        "results": [{"url": "u", "title": "t", "highlights": ["s"]}],
        "costDollars": {"total": 0.02},
    }, 100)):
        assert _cli(_search(tmp_path)) == 0
    [session] = _sessions(evals)
    assert session["skill"] == "research" and session["project"] == "p"
    cost = {m["key"]: m.get("value_num") for m in session["metrics"]}
    assert cost["skills.research_cost_usd"] == 0.02

    from h2t_ops import cli

    capsys.readouterr()
    assert cli.dispatch(["evals", "report", "--json"]) == 0
    report = json.dumps(json.loads(capsys.readouterr().out)["result"])
    assert '"research"' in report


def test_a_failed_search_records_a_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    monkeypatch.setenv("H2T_EVALS_ROOT", str(tmp_path / "evals"))
    monkeypatch.setenv("EXA_API_KEY", "k")
    err = exa_search.ExaPermanentError("http 401", http_status=401, latency_ms=5, body={})
    with patch.object(exa_search, "call_exa", side_effect=err):
        assert _cli(_search(tmp_path)) == 4
    [session] = _sessions(tmp_path / "evals")
    assert session["status"] == "failure"


def test_a_crawl_writes_a_session(monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_EVALS_MODE", "local")
    monkeypatch.setenv("H2T_EVALS_ROOT", str(tmp_path / "evals"))
    monkeypatch.setenv("EXA_API_KEY", "k")
    with patch.object(exa_search, "call_exa", return_value=(200, {
        "results": [{"url": "https://x.example", "text": "body"}],
        "costDollars": {"total": 0.001},
    }, 200)):
        assert _cli(["crawl", "--url", "https://x.example", "--output-dir", str(tmp_path),
                     "--project", "p", "--json"]) == 0
    [session] = _sessions(tmp_path / "evals")
    assert session["status"] == "success"


def test_eval_mode_off_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_EVALS_MODE", "off")
    monkeypatch.setenv("H2T_EVALS_ROOT", str(tmp_path / "evals"))
    monkeypatch.setenv("EXA_API_KEY", "k")
    with patch.object(exa_search, "call_exa", return_value=(200, {
        "results": [{"url": "u", "title": "t"}], "costDollars": {"total": 0.0}}, 1)):
        assert _cli(_search(tmp_path)) == 0
    assert not (tmp_path / "evals").exists()
