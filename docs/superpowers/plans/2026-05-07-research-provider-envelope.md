# Research Provider Envelope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать machine-readable envelope `{status, primary_engine, fallback_engine_used, results, telemetry}` в `exa_search.py` с retry policy, под backward-compat constraints из spec. Закрыть silent-class "exit 0 + 0 results = success".

**Architecture:** Refactor `call_exa` на typed exceptions (single-file), добавить retry loop с `sleep_with_jitter` helper, добавить envelope builder, флаги `--envelope` / `--no-retry`, embed envelope в `.sources.json` sidecar, обновить SKILL.md. Default stdout остаётся markdown summary.

**Tech Stack:** Python 3.11 stdlib (`urllib`, `json`, `time`, `random`), pytest, `unittest.mock`. Никаких новых pip deps.

**Spec:** `docs/superpowers/specs/2026-05-07-research-provider-envelope.md`
**Issue:** lichtpfad/h2t-skills#100

---

## File Structure

| Path | Type | Responsibility |
|---|---|---|
| `plugins/h2t-ops/skills/research/scripts/exa_search.py` | modify | Refactor call_exa, add envelope/retry/helpers, new flags |
| `plugins/h2t-ops/skills/research/tests/test_exa_search.py` | modify | 15+ new tests, update version assertion |
| `plugins/h2t-ops/skills/research/SKILL.md` | modify | New "Provider Status Envelope" section, update Step 4 + Antipatterns, version bump |
| `plugins/h2t-ops/skills/research/REPORT-SPEC.md` | modify | Version footer bump |
| `plugins/h2t-ops/skills/research/reference.md` | modify | New "Envelope schema" section |
| `plugins/h2t-ops/.claude-plugin/plugin.json` | modify (via bump_plugin.py) | h2t-ops 1.1.0 → 1.1.1 |

**Test runner:** `~/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v`

**Single python alias for plan:**
```
PYTEST="C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest"
PYTHON="C:/Users/stani/.h2t/venv/Scripts/python.exe"
TEST_FILE="plugins/h2t-ops/skills/research/tests/test_exa_search.py"
```

**Frequent commits:** один логический task = один commit. Conventional Commits scope `(research)`.

---

## Task 1: Refactor call_exa to typed exceptions (prerequisite)

**Why first:** spec §9.1 — без этого retry wrapper не сможет классифицировать failures. Текущий `call_exa` делает `die(3)` на URLError; retry должен видеть exception, а не sys.exit.

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py:164-204` (EXA_API const + call_exa)
- Test: `plugins/h2t-ops/skills/research/tests/test_exa_search.py` (add at end)

- [ ] **Step 1: Write failing tests for typed exceptions**

Append to `tests/test_exa_search.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
$PYTEST $TEST_FILE -v -k "call_exa_" 2>&1 | tail -20
```

Expected: 6 FAIL with `AttributeError: module 'exa_search' has no attribute 'ExaTransientError'`.

- [ ] **Step 3: Add typed exceptions and refactor call_exa**

In `scripts/exa_search.py`, replace lines 164–204 (`EXA_API = ...` through end of `call_exa`):

```python
EXA_API = "https://api.exa.ai"


class ExaTransientError(Exception):
    """Retryable: HTTP 5xx, 429, URLError, timeout."""

    def __init__(self, message: str, *, http_status: int | None, latency_ms: int, body: Any = None):
        super().__init__(message)
        self.http_status = http_status
        self.latency_ms = latency_ms
        self.body = body


class ExaPermanentError(Exception):
    """Non-retryable: HTTP 4xx (other than 429)."""

    def __init__(self, message: str, *, http_status: int, latency_ms: int, body: Any = None):
        super().__init__(message)
        self.http_status = http_status
        self.latency_ms = latency_ms
        self.body = body


class ExaMalformedResponseError(Exception):
    """HTTP 2xx but body is not valid JSON or missing required fields."""

    def __init__(self, message: str, *, latency_ms: int):
        super().__init__(message)
        self.latency_ms = latency_ms


def call_exa(
    endpoint: str,
    body: dict[str, Any],
    api_key: str,
    timeout: int = 60,
) -> tuple[int, dict[str, Any], int]:
    """POST to Exa. Returns (http_status, response_json, latency_ms) on 2xx with valid JSON.

    Raises:
      - ExaTransientError on HTTP 5xx, 429, URLError, timeout (retryable upstream).
      - ExaPermanentError on HTTP 4xx other than 429 (caller decides exit).
      - ExaMalformedResponseError on HTTP 2xx with non-JSON body.

    No die() inside this function — all exit decisions live at CLI top level.
    """
    req = urllib.request.Request(
        f"{EXA_API}{endpoint}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"exa_search.py/{__version__} (h2t-ops:research)",
        },
        method="POST",
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = int((time.monotonic() - start) * 1000)
            raw = resp.read().decode("utf-8")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ExaMalformedResponseError(
                    f"non-JSON body from Exa (first 120 chars): {raw[:120]!r}",
                    latency_ms=latency,
                ) from e
            return resp.status, data, latency
    except urllib.error.HTTPError as e:
        latency = int((time.monotonic() - start) * 1000)
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = {"error": "non_json_error_response"}
        if e.code == 429 or 500 <= e.code < 600:
            raise ExaTransientError(
                f"http {e.code}", http_status=e.code, latency_ms=latency, body=err_body,
            ) from e
        raise ExaPermanentError(
            f"http {e.code}", http_status=e.code, latency_ms=latency, body=err_body,
        ) from e
    except urllib.error.URLError as e:
        latency = int((time.monotonic() - start) * 1000)
        raise ExaTransientError(
            f"network: {e.reason}", http_status=None, latency_ms=latency,
        ) from e
```

- [ ] **Step 4: Update _run_search and _run_crawl to handle new exceptions**

In `_run_search` (line 457), replace the `call_exa` invocation block (lines 463–467):

```python
def _run_search(args: argparse.Namespace) -> int:
    validate_args(args)
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        die(4, "EXA_ERROR:ENV EXA_API_KEY missing")
    system_prompt, schema = load_system_prompt(args.mode)
    body = build_body(args, system_prompt, schema)
    try:
        status, data, latency_ms = call_exa("/search", body, api_key)
    except ExaPermanentError as e:
        err_body = json.dumps(e.body)[:300]
        die(2, f"EXA_ERROR:API http={e.http_status} body={err_body!r}")
    except ExaTransientError as e:
        if e.http_status is None:
            die(3, f"EXA_ERROR:NETWORK {e} after {e.latency_ms}ms")
        die(2, f"EXA_ERROR:API http={e.http_status} body={json.dumps(e.body)[:300]!r}")
    except ExaMalformedResponseError as e:
        die(2, f"EXA_ERROR:MALFORMED {e}")
    # ... existing code from line 469 onwards (Persist + report)
```

In `_run_crawl` (line 536), apply the same try/except wrapper around `call_exa("/contents", ...)`.

- [ ] **Step 5: Update 3 existing tests broken by refactor**

The current test file has these tests that assume the old contract (call_exa returns tuple on 429, exits 3 on URLError). Refactor breaks them. Update each:

**5a.** Delete `test_call_exa_http_429_returns_error_body` entirely (lines 281–294 in current file). The new `test_call_exa_raises_transient_on_429` from Step 1 covers the same behaviour with the new contract.

**5b.** Delete `test_call_exa_network_timeout_exits_3` entirely (lines 297–304). Replaced by `test_call_exa_raises_transient_on_urlerror` from Step 1.

**5c.** Rewrite `test_run_search_http_429_exits_2` (currently around line 571) — after retry loop, 429 needs to fire twice with sleep stubbed. Replace its body with:

```python
def test_run_search_http_429_exits_2(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EXA_API_KEY", "stub")
    sp_dir = tmp_path / "systemprompts"
    sp_dir.mkdir()
    (sp_dir / "generic.md").write_text("---\n---\nsp\n", encoding="utf-8")
    monkeypatch.setattr(exa_search, "SYSTEMPROMPTS_DIR", sp_dir)
    monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)

    err = urllib.error.HTTPError(
        url="https://api.exa.ai/search", code=429, msg="Too Many",
        hdrs=None, fp=io.BytesIO(b'{"error":"rate"}'),
    )
    with patch("urllib.request.urlopen", side_effect=[err, err]):
        with pytest.raises(SystemExit) as excinfo:
            exa_search.main([
                "search", "--query", "x", "--mode", "generic",
                "--output-dir", str(tmp_path), "--project", "p",
            ])
    assert excinfo.value.code == 2
    assert "EXA_ERROR:API" in capsys.readouterr().err
```

Note: after Task 1 the rewrite passes immediately (no retry loop yet, so the first `err` triggers `die(2)`, the second is never consumed). After Task 4 lands retry, the same test still passes because `side_effect=[err, err]` provides two errors and `sleep_with_jitter` is monkeypatched to no-op.

The `monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)` line is harmless after Task 1 even before the helper exists — `setattr` adds the attribute to the module unconditionally. **Do not** wrap with try/except.

- [ ] **Step 6: Run tests to verify pass + no regressions**

```bash
$PYTEST $TEST_FILE -v 2>&1 | tail -30
```

Expected: 6 new typed-exception tests PASS, all previously passing tests still PASS.

- [ ] **Step 7: Commit**

```bash
git add plugins/h2t-ops/skills/research/scripts/exa_search.py plugins/h2t-ops/skills/research/tests/test_exa_search.py
git commit -m "refactor(research): typed exceptions in call_exa

Introduce ExaTransientError, ExaPermanentError, ExaMalformedResponseError.
call_exa returns tuple on success or raises typed exception. die() moves
to CLI top level (_run_search, _run_crawl). Replace 2 obsolete tests
(429-tuple, URLError-exit-3) with new exception-based tests.
test_run_search_http_429_exits_2 marked xfail pending sleep_with_jitter.

Refs: lichtpfad/h2t-skills#100"
```

---

## Task 2: Add sleep_with_jitter helper

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py` (add module-level helper)
- Test: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append to `test_exa_search.py`:

```python
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
```

- [ ] **Step 2: Run to verify FAIL**

```bash
$PYTEST $TEST_FILE -v -k "sleep_with_jitter" 2>&1 | tail -10
```

Expected: 2 FAIL with `AttributeError`.

- [ ] **Step 3: Add helper**

In `exa_search.py`, after imports (after line 21), add:

```python
import random
```

And after `EXA_API` const (after the typed exceptions block from Task 1), add:

```python
JITTER_MAX_SECONDS = 0.5


def sleep_with_jitter(base_seconds: float) -> None:
    """Sleep for base_seconds + uniform(0, JITTER_MAX_SECONDS) jitter.

    Extracted as a module-level function so tests can monkeypatch it
    without touching real time.sleep, and so retry loop calls are
    homogeneous and easy to count in tests.
    """
    time.sleep(base_seconds + random.uniform(0.0, JITTER_MAX_SECONDS))
```

- [ ] **Step 4: Run to verify PASS**

```bash
$PYTEST $TEST_FILE -v -k "sleep_with_jitter" 2>&1 | tail -10
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/scripts/exa_search.py plugins/h2t-ops/skills/research/tests/test_exa_search.py
git commit -m "feat(research): add sleep_with_jitter helper for retry backoff

Module-level helper makes test mocking trivial via monkeypatch.

Refs: lichtpfad/h2t-skills#100"
```

---

## Task 3: Build envelope skeleton

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py` (add `build_envelope`)
- Test: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing tests**

Append to `test_exa_search.py`:

```python
# --- build_envelope (Task 3) ---

def test_build_envelope_ok_shape():
    attempts = [{"engine": "exa", "endpoint": "/search", "http": 200, "latency_ms": 100, "error": None}]
    env = exa_search.build_envelope(
        status="OK",
        results=[{"url": "u", "title": "t"}],
        attempts=attempts,
        meta={"query": "q", "mode": "generic", "num_results_requested": 10,
              "num_results_returned": 1, "timestamp": "2026-05-07T00:00:00+00:00"},
        total_cost_usd=0.01,
    )
    assert env["status"] == "OK"
    assert env["primary_engine"] == "exa"
    assert env["fallback_engine_used"] is None
    assert env["results"] == [{"url": "u", "title": "t"}]
    assert env["telemetry"]["attempts"] == attempts
    assert env["telemetry"]["reason_for_fallback"] is None
    assert env["telemetry"]["total_latency_ms"] == 100
    assert env["telemetry"]["total_cost_usd"] == 0.01
    assert env["meta"]["envelope_version"] == "1"
    assert env["meta"]["num_results_returned"] == 1


def test_build_envelope_degraded_with_reason():
    attempts = [
        {"engine": "exa", "endpoint": "/search", "http": 200, "latency_ms": 80, "error": "exa_empty_results"},
        {"engine": "exa", "endpoint": "/search", "http": 200, "latency_ms": 90, "error": "exa_empty_results"},
    ]
    env = exa_search.build_envelope(
        status="DEGRADED",
        results=[],
        attempts=attempts,
        meta={"query": "q", "mode": "generic", "num_results_requested": 10,
              "num_results_returned": 0, "timestamp": "2026-05-07T00:00:00+00:00"},
        total_cost_usd=0.0,
        reason_for_fallback="exa_empty_results",
    )
    assert env["status"] == "DEGRADED"
    assert env["results"] == []
    assert env["telemetry"]["reason_for_fallback"] == "exa_empty_results"
    assert env["telemetry"]["total_latency_ms"] == 170


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
```

- [ ] **Step 2: Run to verify FAIL**

```bash
$PYTEST $TEST_FILE -v -k "build_envelope" 2>&1 | tail -10
```

Expected: 3 FAIL with `AttributeError: build_envelope`.

- [ ] **Step 3: Implement build_envelope**

In `exa_search.py`, after `sleep_with_jitter`, add:

```python
ENVELOPE_VERSION = "1"


def build_envelope(
    *,
    status: str,
    results: list[Any],
    attempts: list[dict[str, Any]],
    meta: dict[str, Any],
    total_cost_usd: float,
    reason_for_fallback: str | None = None,
    fallback_engine_used: str | None = None,
) -> dict[str, Any]:
    """Assemble the provider envelope per spec §3."""
    total_latency_ms = sum(a["latency_ms"] for a in attempts)
    return {
        "status": status,
        "primary_engine": "exa",
        "fallback_engine_used": fallback_engine_used,
        "results": results,
        "telemetry": {
            "attempts": attempts,
            "reason_for_fallback": reason_for_fallback,
            "total_latency_ms": total_latency_ms,
            "total_cost_usd": total_cost_usd,
        },
        "meta": {**meta, "envelope_version": ENVELOPE_VERSION},
    }
```

- [ ] **Step 4: Run to verify PASS**

```bash
$PYTEST $TEST_FILE -v -k "build_envelope" 2>&1 | tail -10
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/scripts/exa_search.py plugins/h2t-ops/skills/research/tests/test_exa_search.py
git commit -m "feat(research): add build_envelope per spec §3

Single-purpose builder for {status, primary_engine, results, telemetry, meta}.
envelope_version=1 baked in for forward-compat.

Refs: lichtpfad/h2t-skills#100"
```

---

## Task 4: Retry loop — search_with_retry wrapper

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py` (add `search_with_retry`)
- Test: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing tests covering all retry paths**

Append to `test_exa_search.py`:

```python
# --- search_with_retry (Task 4) ---

def _ok_response(results_count: int = 3, cost: float = 0.01) -> tuple[int, dict, int]:
    return (200, {
        "results": [{"url": f"u{i}", "title": f"t{i}"} for i in range(results_count)],
        "costDollars": {"total": cost},
    }, 100)


def _patch_no_sleep(monkeypatch):
    monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)


def test_search_with_retry_ok_first_try(monkeypatch):
    _patch_no_sleep(monkeypatch)
    with patch.object(exa_search, "call_exa", return_value=_ok_response(3)) as m:
        env, exit_code = exa_search.search_with_retry(
            body={"query": "x"}, api_key="k", retry=True,
        )
    assert m.call_count == 1
    assert env["status"] == "OK"
    assert exit_code == 0
    assert len(env["results"]) == 3
    assert len(env["telemetry"]["attempts"]) == 1


def test_search_with_retry_empty_then_empty_is_degraded(monkeypatch):
    _patch_no_sleep(monkeypatch)
    empty = (200, {"results": [], "costDollars": {"total": 0.0}}, 50)
    with patch.object(exa_search, "call_exa", side_effect=[empty, empty]) as m:
        env, exit_code = exa_search.search_with_retry(
            body={"query": "x"}, api_key="k", retry=True,
        )
    assert m.call_count == 2
    assert env["status"] == "DEGRADED"
    assert exit_code == 0
    assert env["telemetry"]["reason_for_fallback"] == "exa_empty_results"
    assert all(a["error"] == "exa_empty_results" for a in env["telemetry"]["attempts"])


def test_search_with_retry_empty_then_ok_is_ok(monkeypatch):
    _patch_no_sleep(monkeypatch)
    empty = (200, {"results": [], "costDollars": {"total": 0.0}}, 50)
    with patch.object(exa_search, "call_exa", side_effect=[empty, _ok_response(2)]) as m:
        env, exit_code = exa_search.search_with_retry(
            body={"query": "x"}, api_key="k", retry=True,
        )
    assert m.call_count == 2
    assert env["status"] == "OK"
    assert exit_code == 0
    assert env["telemetry"]["attempts"][0]["error"] == "exa_empty_results"
    assert env["telemetry"]["attempts"][1]["error"] is None


def test_search_with_retry_5xx_then_5xx_is_failed(monkeypatch):
    _patch_no_sleep(monkeypatch)
    err = exa_search.ExaTransientError("http 503", http_status=503, latency_ms=200)
    with patch.object(exa_search, "call_exa", side_effect=[err, err]) as m:
        env, exit_code = exa_search.search_with_retry(
            body={"query": "x"}, api_key="k", retry=True,
        )
    assert m.call_count == 2
    assert env["status"] == "FAILED"
    assert exit_code == 2
    assert all(a["error"] == "exa_5xx_retryable" for a in env["telemetry"]["attempts"])


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
    assert env["telemetry"]["attempts"][0]["error"] == "exa_4xx_nonretryable"


def test_search_with_retry_urlerror_then_urlerror_is_failed(monkeypatch):
    _patch_no_sleep(monkeypatch)
    err = exa_search.ExaTransientError("network: dns", http_status=None, latency_ms=300)
    with patch.object(exa_search, "call_exa", side_effect=[err, err]):
        env, exit_code = exa_search.search_with_retry(
            body={"query": "x"}, api_key="k", retry=True,
        )
    assert env["status"] == "FAILED"
    assert exit_code == 3
    assert all(a["error"] == "exa_network_timeout" for a in env["telemetry"]["attempts"])


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


def test_search_with_retry_429_triggers_retry(monkeypatch):
    _patch_no_sleep(monkeypatch)
    err = exa_search.ExaTransientError("http 429", http_status=429, latency_ms=120)
    with patch.object(exa_search, "call_exa", side_effect=[err, _ok_response(1)]) as m:
        env, exit_code = exa_search.search_with_retry(
            body={"query": "x"}, api_key="k", retry=True,
        )
    assert m.call_count == 2
    assert env["status"] == "OK"
    assert env["telemetry"]["attempts"][0]["error"] == "exa_5xx_retryable"  # 429 also retryable bucket


def test_search_with_retry_no_retry_flag_disables_retries(monkeypatch):
    _patch_no_sleep(monkeypatch)
    empty = (200, {"results": [], "costDollars": {"total": 0.0}}, 50)
    with patch.object(exa_search, "call_exa", side_effect=[empty, empty]) as m:
        env, exit_code = exa_search.search_with_retry(
            body={"query": "x"}, api_key="k", retry=False,
        )
    assert m.call_count == 1
    assert env["status"] == "DEGRADED"
    assert exit_code == 0
    assert len(env["telemetry"]["attempts"]) == 1


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
```

Note: the 429 test asserts `error == "exa_5xx_retryable"` because the spec lumps 429 into the "retryable HTTP" bucket. If you prefer a separate `exa_rate_limit` label, add it but update the spec §3.3 first.

- [ ] **Step 2: Run to verify FAIL**

```bash
$PYTEST $TEST_FILE -v -k "search_with_retry" 2>&1 | tail -30
```

Expected: 12 FAIL with `AttributeError: search_with_retry`.

- [ ] **Step 3: Implement search_with_retry**

In `exa_search.py`, after `build_envelope`, add:

```python
RETRY_BACKOFF_SECONDS: dict[str, float] = {
    "exa_5xx_retryable":   2.0,  # also covers 429
    "exa_network_timeout": 1.5,
    "exa_empty_results":   1.0,
}
RETRY_BUDGET_SECONDS = 10.0


def _classify_attempt_from_call(
    body: dict[str, Any],
    api_key: str,
) -> tuple[dict[str, Any], int | None, dict[str, Any] | None]:
    """One call_exa wrapped to produce (attempt_record, http_status, response_body).

    attempt_record always contains: engine, endpoint, http (or None), latency_ms, error.
    On success: error=None and response_body is the parsed Exa response.
    On any handled exception: response_body is None.
    """
    try:
        status, data, latency = call_exa("/search", body, api_key)
        results = data.get("results")
        if results is None:
            return (
                {"engine": "exa", "endpoint": "/search", "http": status,
                 "latency_ms": latency, "error": "exa_malformed_json"},
                None, None,
            )
        if len(results) == 0:
            return (
                {"engine": "exa", "endpoint": "/search", "http": status,
                 "latency_ms": latency, "error": "exa_empty_results"},
                status, data,
            )
        return (
            {"engine": "exa", "endpoint": "/search", "http": status,
             "latency_ms": latency, "error": None},
            status, data,
        )
    except ExaPermanentError as e:
        return (
            {"engine": "exa", "endpoint": "/search", "http": e.http_status,
             "latency_ms": e.latency_ms, "error": "exa_4xx_nonretryable"},
            None, None,
        )
    except ExaTransientError as e:
        if e.http_status is None:
            label = "exa_network_timeout"
        else:
            label = "exa_5xx_retryable"
        return (
            {"engine": "exa", "endpoint": "/search", "http": e.http_status,
             "latency_ms": e.latency_ms, "error": label},
            None, None,
        )
    except ExaMalformedResponseError as e:
        return (
            {"engine": "exa", "endpoint": "/search", "http": None,
             "latency_ms": e.latency_ms, "error": "exa_malformed_json"},
            None, None,
        )


def _exit_code_for_failure(error_label: str) -> int:
    if error_label == "exa_network_timeout":
        return 3
    return 2


def search_with_retry(
    *,
    body: dict[str, Any],
    api_key: str,
    retry: bool,
    mode: str = "generic",
) -> tuple[dict[str, Any], int]:
    """Run /search with optional 1-retry loop. Returns (envelope, exit_code).

    Retryable error labels: exa_5xx_retryable, exa_network_timeout, exa_empty_results.
    Non-retryable: exa_4xx_nonretryable, exa_malformed_json.
    Hard cap: cumulative sleep ≤ RETRY_BUDGET_SECONDS.
    """
    attempts: list[dict[str, Any]] = []
    last_data: dict[str, Any] | None = None
    last_status: int | None = None
    cumulative_sleep = 0.0
    max_attempts = 2 if retry else 1

    for i in range(max_attempts):
        attempt, status, data = _classify_attempt_from_call(body, api_key)
        attempts.append(attempt)
        last_status = status
        if data is not None:
            last_data = data
        error = attempt["error"]

        # Success on this attempt
        if error is None:
            break
        # Non-retryable
        if error in ("exa_4xx_nonretryable", "exa_malformed_json"):
            break
        # No more attempts left
        if i == max_attempts - 1:
            break
        # Backoff before next attempt
        backoff = RETRY_BACKOFF_SECONDS.get(error, 1.0)
        if cumulative_sleep + backoff > RETRY_BUDGET_SECONDS:
            print(
                f"EXA_WARN:RETRY_BUDGET_EXHAUSTED skipped backoff={backoff}s "
                f"after cumulative={cumulative_sleep}s",
                file=sys.stderr,
            )
            break
        sleep_with_jitter(backoff)
        cumulative_sleep += backoff

    # Determine final status + exit
    last_error = attempts[-1]["error"]
    if last_error is None:
        status_label = "OK"
        exit_code = 0
        results = (last_data or {}).get("results", [])
        cost = float((last_data or {}).get("costDollars", {}).get("total", 0.0))
        reason = None
    elif last_error == "exa_empty_results":
        status_label = "DEGRADED"
        exit_code = 0
        results = []
        cost = float((last_data or {}).get("costDollars", {}).get("total", 0.0))
        reason = "exa_empty_results"
    else:
        status_label = "FAILED"
        exit_code = _exit_code_for_failure(last_error)
        results = []
        cost = 0.0
        reason = None

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    envelope = build_envelope(
        status=status_label,
        results=results,
        attempts=attempts,
        meta={
            "query": body.get("query", ""),
            "mode": mode,
            "num_results_requested": body.get("numResults", 0),
            "num_results_returned": len(results),
            "timestamp": timestamp,
        },
        total_cost_usd=cost,
        reason_for_fallback=reason,
    )
    return envelope, exit_code
```

- [ ] **Step 4: Run tests to verify PASS**

```bash
$PYTEST $TEST_FILE -v -k "search_with_retry" 2>&1 | tail -25
```

Expected: 12 PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/scripts/exa_search.py plugins/h2t-ops/skills/research/tests/test_exa_search.py
git commit -m "feat(research): add search_with_retry with status envelope

Retry policy per spec §4: 5xx/429/network/empty-2xx retryable (1 retry),
4xx/malformed non-retryable. Cumulative backoff capped at 10s with
EXA_WARN:RETRY_BUDGET_EXHAUSTED to stderr. Returns (envelope, exit_code).

Refs: lichtpfad/h2t-skills#100"
```

---

## Task 5: Test backoff budget cap

**Files:**
- Test: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write test for budget exhaustion warning**

Append:

```python
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
    captured = capsys.readouterr()
    assert "EXA_WARN:RETRY_BUDGET_EXHAUSTED" in captured.err
    assert env["status"] == "FAILED"
    assert exit_code == 2
    assert sleeps_called == []
```

- [ ] **Step 2: Run to verify PASS** (already implemented in Task 4)

```bash
$PYTEST $TEST_FILE -v -k "warn_emitted_when_budget" 2>&1 | tail -10
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add plugins/h2t-ops/skills/research/tests/test_exa_search.py
git commit -m "test(research): cover backoff budget exhaustion warning

Refs: lichtpfad/h2t-skills#100"
```

---

## Task 6: Wire envelope into _run_search; add --envelope and --no-retry CLI flags

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py` (`_build_parser`, `_run_search`)
- Test: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing CLI integration tests**

Append:

```python
# --- CLI flags --envelope, --no-retry (Task 6) ---

def _make_search_argv(extra: list[str] | None = None) -> list[str]:
    argv = ["search", "--query", "anything", "--mode", "generic", "--num-results", "3"]
    if extra:
        argv.extend(extra)
    return argv


def test_default_stdout_is_markdown_summary(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)
    with patch.object(exa_search, "call_exa", return_value=(200, {
        "results": [{"url": "u", "title": "t", "highlights": ["snippet"]}],
        "costDollars": {"total": 0.01},
    }, 100)):
        rc = exa_search.main(_make_search_argv(["--output-dir", str(tmp_path), "--project", "p"]))
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith("## Exa Search:")
    # No JSON envelope on stdout in default mode
    assert not out.lstrip().startswith("{")


def test_envelope_flag_prints_json_to_stdout(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)
    with patch.object(exa_search, "call_exa", return_value=(200, {
        "results": [{"url": "u", "title": "t", "highlights": ["snippet"]}],
        "costDollars": {"total": 0.01},
    }, 100)):
        rc = exa_search.main(_make_search_argv(
            ["--output-dir", str(tmp_path), "--project", "p", "--envelope"]
        ))
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)  # stdout must be valid JSON
    assert payload["status"] == "OK"
    assert payload["primary_engine"] == "exa"
    assert "## Exa Search:" not in out


def test_no_retry_flag_disables_retries_via_cli(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)
    empty = (200, {"results": [], "costDollars": {"total": 0.0}}, 50)
    with patch.object(exa_search, "call_exa", side_effect=[empty, empty]) as m:
        rc = exa_search.main(_make_search_argv(
            ["--output-dir", str(tmp_path), "--project", "p", "--envelope", "--no-retry"]
        ))
    assert m.call_count == 1
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "DEGRADED"


def test_envelope_in_sources_json_always_written(monkeypatch, tmp_path):
    monkeypatch.setenv("EXA_API_KEY", "k")
    monkeypatch.setattr(exa_search, "sleep_with_jitter", lambda s: None)
    with patch.object(exa_search, "call_exa", return_value=(200, {
        "results": [{"url": "u", "title": "t", "highlights": []}],
        "costDollars": {"total": 0.02},
    }, 100)):
        rc = exa_search.main(_make_search_argv(
            ["--output-dir", str(tmp_path), "--project", "p"]  # no --envelope
        ))
    assert rc == 0
    sources_files = list(tmp_path.glob("*.sources.json"))
    assert len(sources_files) == 1
    data = json.loads(sources_files[0].read_text(encoding="utf-8"))
    assert "envelope" in data["meta"]
    assert data["meta"]["envelope"]["status"] == "OK"
    assert data["meta"]["envelope"]["primary_engine"] == "exa"
```

- [ ] **Step 2: Run to verify FAIL**

```bash
$PYTEST $TEST_FILE -v -k "envelope_flag or no_retry_flag or default_stdout or sources_json_always" 2>&1 | tail -20
```

Expected: 4 FAIL (flags missing or behaviour wrong).

- [ ] **Step 3: Add flags in `_build_parser`**

Find `_build_parser` (line 388). In the `s = sub.add_parser("search", ...)` block, after the existing `s.add_argument("--project", ...)` line, add:

```python
    s.add_argument("--envelope", action="store_true",
                   help="Print JSON envelope to stdout instead of markdown summary.")
    s.add_argument("--no-retry", action="store_true", dest="no_retry",
                   help="Disable retry policy (for tests/debug).")
```

- [ ] **Step 4: Rewire `_run_search` to use search_with_retry**

Replace the body of `_run_search` (line 457 onwards) with:

```python
def _run_search(args: argparse.Namespace) -> int:
    validate_args(args)
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        die(4, "EXA_ERROR:ENV EXA_API_KEY missing")
    system_prompt, schema = load_system_prompt(args.mode)
    body = build_body(args, system_prompt, schema)

    envelope, exit_code = search_with_retry(
        body=body, api_key=api_key, retry=not args.no_retry, mode=args.mode,
    )

    # FAILED → emit EXA_ERROR:* to stderr (preserve existing fail-loud contract).
    if envelope["status"] == "FAILED":
        last = envelope["telemetry"]["attempts"][-1]
        if last["error"] == "exa_4xx_nonretryable":
            die(2, f"EXA_ERROR:API http={last['http']}")
        if last["error"] == "exa_5xx_retryable":
            die(2, f"EXA_ERROR:API http={last['http']} (after retries)")
        if last["error"] == "exa_network_timeout":
            die(3, f"EXA_ERROR:NETWORK after {last['latency_ms']}ms (after retries)")
        if last["error"] == "exa_malformed_json":
            die(2, "EXA_ERROR:MALFORMED non-JSON or missing 'results' field")
        die(2, f"EXA_ERROR:UNKNOWN {last['error']}")  # defensive

    # Persist (always — both .sources.json and .partial.md, OK and DEGRADED both)
    out_dir = Path(args.output_dir)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    paths = output_paths(out_dir, args.project, args.query, date)

    # Reconstruct an Exa-shaped response for existing writers (back-compat).
    response_for_writers = {
        "results": envelope["results"],
        "costDollars": {"total": envelope["telemetry"]["total_cost_usd"]},
    }
    meta = {
        "query": args.query,
        "mode": args.mode,
        "depth": args.depth,
        "project": args.project,
        "date": envelope["meta"]["timestamp"],
        "status": "completed" if envelope["status"] == "OK" else "partial",
        "cache_hit": False,
        "envelope": envelope,  # NEW: sidecar copy
    }
    write_sources_json(paths["sources_json"], meta, response_for_writers)

    cat = MODE_CONFIG[args.mode]["category"]
    tel_args = f"type={MODE_CONFIG[args.mode]['type']}"
    if cat:
        tel_args += f",category={cat}"
    tel_args += f",numResults={body['numResults']}"
    telemetry_rows = [{
        "num": i + 1,
        "tool": "exa_search.py search",
        "args": tel_args,
        "http": a["http"] or 0,
        "latency_ms": a["latency_ms"],
        "cost_usd": (envelope["telemetry"]["total_cost_usd"] if a["error"] is None else 0.0),
        "results": (len(envelope["results"]) if a["error"] is None else 0),
    } for i, a in enumerate(envelope["telemetry"]["attempts"])]
    write_partial_md(paths["partial_md"], meta=meta, telemetry_rows=telemetry_rows)

    # Stdout: JSON envelope if --envelope, else markdown summary (back-compat default).
    if args.envelope:
        print(json.dumps(envelope, indent=2, ensure_ascii=False))
    else:
        render_stdout_summary(
            response_for_writers,
            query=args.query,
            mode=args.mode,
            latency_ms=envelope["telemetry"]["total_latency_ms"],
            partial_path=paths["partial_md"],
            json_path=paths["sources_json"],
        )

    # Telemetry — fire-and-forget, unchanged shape.
    post_telemetry(
        event={
            "session_id": os.environ.get("H2T_SESSION_ID", ""),
            "engine": "exa",
            "endpoint": "/search",
            "mode": args.mode,
            "exa_type": body["type"],
            "exa_category": body.get("category"),
            "query_hash": sha256(args.query.encode("utf-8")).hexdigest()[:16],
            "num_results_requested": body["numResults"],
            "num_results_returned": len(envelope["results"]),
            "cost_usd": envelope["telemetry"]["total_cost_usd"],
            "latency_ms": envelope["telemetry"]["total_latency_ms"],
            "http_status": envelope["telemetry"]["attempts"][-1]["http"] or 0,
            "exit_code": exit_code,
            "timestamp": envelope["meta"]["timestamp"],
        },
        buffer_path=out_dir / ".pending_telemetry.jsonl",
    )
    return exit_code
```

- [ ] **Step 5: Run all tests**

```bash
$PYTEST $TEST_FILE -v 2>&1 | tail -40
```

Expected: 4 new tests PASS, all earlier tests PASS. If any earlier test fails on stdout shape — investigate, but the markdown writer is unchanged, so it should be fine.

- [ ] **Step 6: Commit**

```bash
git add plugins/h2t-ops/skills/research/scripts/exa_search.py plugins/h2t-ops/skills/research/tests/test_exa_search.py
git commit -m "feat(research): wire envelope into search CLI; add --envelope/--no-retry flags

Default stdout unchanged (markdown summary). --envelope opt-in prints
JSON envelope to stdout instead. Sidecar envelope always written to
.sources.json under meta.envelope. --no-retry disables retry loop
for tests/debug.

Refs: lichtpfad/h2t-skills#100"
```

---

## Task 7: Crawl subcommand minimal envelope

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py` (`_run_crawl`)
- Test: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append:

```python
# --- crawl envelope sidecar (Task 7) ---

def test_crawl_writes_envelope_to_sources_json(monkeypatch, tmp_path):
    monkeypatch.setenv("EXA_API_KEY", "k")
    with patch.object(exa_search, "call_exa", return_value=(200, {
        "results": [{"url": "https://x", "text": "body"}],
        "costDollars": {"total": 0.001},
    }, 200)):
        rc = exa_search.main([
            "crawl", "--url", "https://x",
            "--output-dir", str(tmp_path), "--project", "p",
        ])
    assert rc == 0
    sources = list(tmp_path.glob("*.sources.json"))
    assert len(sources) == 1
    data = json.loads(sources[0].read_text(encoding="utf-8"))
    assert data["meta"]["envelope"]["status"] == "OK"
    assert data["meta"]["envelope"]["primary_engine"] == "exa"


def test_crawl_empty_is_degraded(monkeypatch, tmp_path):
    monkeypatch.setenv("EXA_API_KEY", "k")
    with patch.object(exa_search, "call_exa", return_value=(200, {
        "results": [], "costDollars": {"total": 0.0},
    }, 80)):
        rc = exa_search.main([
            "crawl", "--url", "https://x",
            "--output-dir", str(tmp_path), "--project", "p",
        ])
    assert rc == 0
    sources = list(tmp_path.glob("*.sources.json"))
    data = json.loads(sources[0].read_text(encoding="utf-8"))
    assert data["meta"]["envelope"]["status"] == "DEGRADED"
```

- [ ] **Step 2: Run to verify FAIL**

```bash
$PYTEST $TEST_FILE -v -k "crawl_writes_envelope or crawl_empty" 2>&1 | tail -10
```

Expected: 2 FAIL (no envelope in sources.json yet for crawl).

- [ ] **Step 3: Update _run_crawl to attach envelope sidecar**

Replace `_run_crawl` body (around line 536) with:

```python
def _run_crawl(args: argparse.Namespace) -> int:
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        die(4, "EXA_ERROR:ENV EXA_API_KEY missing")
    body = {"urls": [args.url], "text": {"maxCharacters": 15000}}
    try:
        status, data, latency_ms = call_exa("/contents", body, api_key)
    except ExaPermanentError as e:
        die(2, f"EXA_ERROR:API http={e.http_status} body={json.dumps(e.body)[:300]!r}")
    except ExaTransientError as e:
        if e.http_status is None:
            die(3, f"EXA_ERROR:NETWORK {e} after {e.latency_ms}ms")
        die(2, f"EXA_ERROR:API http={e.http_status}")
    except ExaMalformedResponseError as e:
        die(2, f"EXA_ERROR:MALFORMED {e}")

    out_dir = Path(args.output_dir)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    topic = f"crawl-{args.url}"
    paths = output_paths(out_dir, args.project, topic, date)

    cost = float(data.get("costDollars", {}).get("total", 0))
    n_results = len(data.get("results", []))
    status_label = "OK" if n_results > 0 else "DEGRADED"
    envelope = build_envelope(
        status=status_label,
        results=data.get("results", []),
        attempts=[{"engine": "exa", "endpoint": "/contents", "http": status,
                   "latency_ms": latency_ms,
                   "error": None if n_results > 0 else "exa_empty_results"}],
        meta={
            "query": f"crawl({args.url})", "mode": "crawl",
            "num_results_requested": 1, "num_results_returned": n_results,
            "timestamp": timestamp,
        },
        total_cost_usd=cost,
        reason_for_fallback=None if n_results > 0 else "exa_empty_results",
    )

    meta = {
        "query": f"crawl({args.url})",
        "mode": "crawl",
        "depth": "n/a",
        "project": args.project,
        "date": timestamp,
        "status": "completed" if n_results > 0 else "partial",
        "cache_hit": False,
        "envelope": envelope,
    }
    write_sources_json(paths["sources_json"], meta, data)
    render_stdout_summary(
        data,
        query=f"crawl({args.url})",
        mode="crawl",
        latency_ms=latency_ms,
        partial_path=paths["partial_md"],
        json_path=paths["sources_json"],
    )
    post_telemetry(
        event={
            "session_id": os.environ.get("H2T_SESSION_ID", ""),
            "engine": "exa",
            "endpoint": "/contents",
            "mode": "crawl",
            "cost_usd": cost,
            "latency_ms": latency_ms,
            "http_status": status,
            "exit_code": 0,
            "timestamp": timestamp,
        },
        buffer_path=out_dir / ".pending_telemetry.jsonl",
    )
    return 0
```

- [ ] **Step 4: Run to verify PASS**

```bash
$PYTEST $TEST_FILE -v -k "crawl" 2>&1 | tail -15
```

Expected: 2 new tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/scripts/exa_search.py plugins/h2t-ops/skills/research/tests/test_exa_search.py
git commit -m "feat(research): minimal envelope sidecar for crawl subcommand

Crawl writes meta.envelope to .sources.json. No retry, no --envelope flag
in this PR (deferred per spec §6).

Refs: lichtpfad/h2t-skills#100"
```

---

## Task 8: Update SKILL.md — Provider Status Envelope section

**Files:**
- Modify: `plugins/h2t-ops/skills/research/SKILL.md`

- [ ] **Step 1: Update version in frontmatter**

Edit line 7:

Old:
```yaml
  version: 0.1.0
```
New:
```yaml
  version: 0.1.1
```

- [ ] **Step 2: Insert new "Provider Status Envelope" section**

Find the "## Tool Restriction" section (around line 69). Immediately after that section (before "## Workflow"), insert:

```markdown
## Provider Status Envelope

Каждый `$EXA_CLI search` пишет envelope в `.sources.json` (поле `meta.envelope`).
При флаге `--envelope` envelope печатается в stdout вместо markdown summary.

| `envelope.status` | Что значит | Действие агента |
|---|---|---|
| `OK` | Exa вернул ≥1 результат после всех retries | Continue to Step 5 (synthesis) |
| `DEGRADED` | Exa отработал, но 0 results после retries (`exit 0`) | Report `STATUS: DEGRADED + reason=exa_empty_results`. Агент МОЖЕТ: (a) попробовать другой mode/query вариацию явным новым CLI вызовом, (b) использовать `WebSearch` с обязательной пометкой `STATUS: DEGRADED + fallback=websearch` в репорте, (c) остановиться. Silent fallback запрещён. |
| `FAILED` | HTTP 4xx/5xx/network/malformed после retries | Report `STATUS: FAILED + EXA_ERROR:*` (точное сообщение из stderr). STOP. |

`exit 0` НЕ означает `status == OK`. Всегда читать envelope (либо из stdout при `--envelope`, либо из `.sources.json:meta.envelope`).
```

- [ ] **Step 3: Update Step 4 — Fail-Loud Checks**

Find the exit-code table (around line 149) and add a row at top:

```markdown
| envelope.status | OK / DEGRADED / FAILED | См. секцию Provider Status Envelope выше |
```

- [ ] **Step 4: Update Antipatterns**

Find "## Antipatterns" (line 191). Add at end of bullet list:

```markdown
- **Treat `exit 0` as success without reading envelope** — `status == DEGRADED` пишется при exit 0 на empty results. Всегда читать `envelope.status`.
- **Silent retry того же запроса** — retry делает скрипт автоматически. Если агент видит `DEGRADED`, он либо явно меняет запрос (новый CLI вызов с другим `--mode` / query вариацией), либо переключается на fallback с пометкой. Никаких "молчаливых" повторов.
```

- [ ] **Step 5: Verify edits with grep**

```bash
grep -n "Provider Status Envelope" plugins/h2t-ops/skills/research/SKILL.md
grep -n "version: 0.1.1" plugins/h2t-ops/skills/research/SKILL.md
grep -n "Treat \`exit 0\` as success" plugins/h2t-ops/skills/research/SKILL.md
```

Expected: each command prints at least one match.

- [ ] **Step 6: Commit**

```bash
git add plugins/h2t-ops/skills/research/SKILL.md
git commit -m "docs(research): SKILL.md — Provider Status Envelope section

Add Provider Status Envelope section explaining OK/DEGRADED/FAILED
semantics and agent fallback policy. Update Step 4 exit-code table
and Antipatterns. Bump skill metadata.version to 0.1.1.

Refs: lichtpfad/h2t-skills#100"
```

---

## Task 9: Update reference.md and REPORT-SPEC.md

**Files:**
- Modify: `plugins/h2t-ops/skills/research/reference.md`
- Modify: `plugins/h2t-ops/skills/research/REPORT-SPEC.md` (line 73 version footer)

- [ ] **Step 1: Append envelope schema section to reference.md**

Append to `reference.md`:

```markdown

---

## Envelope Schema (v1)

`exa_search.py search` (and minimal-form `crawl`) emit a provider envelope.
Always present in `.sources.json` under `meta.envelope`. Optionally to stdout via `--envelope`.

```json
{
  "status": "OK | DEGRADED | FAILED",
  "primary_engine": "exa",
  "fallback_engine_used": null,
  "results": [...],
  "telemetry": {
    "attempts": [
      {"engine": "exa", "endpoint": "/search", "http": 200, "latency_ms": 1234, "error": null}
    ],
    "reason_for_fallback": null,
    "total_latency_ms": 1234,
    "total_cost_usd": 0.012
  },
  "meta": {
    "query": "...",
    "mode": "generic",
    "num_results_requested": 10,
    "num_results_returned": 7,
    "timestamp": "2026-05-07T12:34:56+00:00",
    "envelope_version": "1"
  }
}
```

### Status decision matrix

| Status | Exit | When |
|---|---|---|
| `OK` | 0 | HTTP 200 + ≥1 result after retries |
| `DEGRADED` | 0 | HTTP 200 + 0 results after retries |
| `FAILED` | 1 | Args validation error |
| `FAILED` | 2 | HTTP 4xx (no retry), HTTP 5xx after retries, malformed JSON |
| `FAILED` | 3 | Network/timeout after retries |
| `FAILED` | 4 | Env / preflight error |

### Attempt error labels

`null` (success), `exa_5xx_retryable` (5xx + 429), `exa_4xx_nonretryable`, `exa_network_timeout`, `exa_empty_results`, `exa_malformed_json`.

### Retry policy

| Class | Retryable? | Max attempts | Backoff |
|---|---|---|---|
| 200 + non-empty | — | 1 | — |
| 200 + empty | yes | 2 | 1.0s + jitter |
| 5xx / 429 | yes | 2 | 2.0s + jitter |
| 4xx (other) | no | 1 | — |
| Network/timeout | yes | 2 | 1.5s + jitter |
| Malformed JSON | no | 1 | — |

Hard cap on cumulative sleep: 10 seconds. When exceeded: `EXA_WARN:RETRY_BUDGET_EXHAUSTED` to stderr, retry skipped.
```

- [ ] **Step 2: Update REPORT-SPEC.md version footer**

Edit `REPORT-SPEC.md` line 73:

Old:
```
*Generated by `h2t-ops:research` skill v0.1.0 | Telemetry: {status}*
```
New:
```
*Generated by `h2t-ops:research` skill v0.1.1 | Telemetry: {status}*
```

- [ ] **Step 3: Verify**

```bash
grep -n "Envelope Schema" plugins/h2t-ops/skills/research/reference.md
grep -n "v0.1.1" plugins/h2t-ops/skills/research/REPORT-SPEC.md
```

Expected: both find a match.

- [ ] **Step 4: Commit**

```bash
git add plugins/h2t-ops/skills/research/reference.md plugins/h2t-ops/skills/research/REPORT-SPEC.md
git commit -m "docs(research): document envelope schema in reference.md

Add Envelope Schema section to reference.md with status matrix, error
labels, and retry policy table. Bump REPORT-SPEC version footer to 0.1.1.

Refs: lichtpfad/h2t-skills#100"
```

---

## Task 10: Bump skill internal version + plugin manifest

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py` (line 8 `__version__`)
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py` (line 27 version assertion)
- Modify (via bump_plugin.py): `plugins/h2t-ops/.claude-plugin/plugin.json`, `marketplace.json`

- [ ] **Step 1: Update __version__ in script**

Edit `scripts/exa_search.py:8`:

Old: `__version__ = "0.1.0"`
New: `__version__ = "0.1.1"`

- [ ] **Step 2: Update version assertion in test**

Edit `tests/test_exa_search.py:27`:

Old: `assert "0.1.0" in result.stdout`
New: `assert "0.1.1" in result.stdout`

- [ ] **Step 3: Run version test to verify**

```bash
$PYTEST $TEST_FILE::test_version_flag -v
```

Expected: PASS.

- [ ] **Step 4: Bump plugin manifest via helper script**

```bash
$PYTHON scripts/bump_plugin.py h2t-ops 1.1.1
```

Expected stdout: confirmation that both `marketplace.json` and `plugin.json` updated to 1.1.1.

- [ ] **Step 5: Verify manifest**

```bash
grep '"version"' plugins/h2t-ops/.claude-plugin/plugin.json
```

Expected: `"version": "1.1.1"`.

- [ ] **Step 6: Run full test suite for final clean state**

```bash
$PYTEST $TEST_FILE -v 2>&1 | tail -10
```

Expected: all tests PASS, exit 0.

- [ ] **Step 7: Commit**

```bash
git add plugins/h2t-ops/skills/research/scripts/exa_search.py plugins/h2t-ops/skills/research/tests/test_exa_search.py plugins/h2t-ops/.claude-plugin/plugin.json marketplace.json
git commit -m "chore(research): bump skill to 0.1.1, h2t-ops plugin to 1.1.1

Patch bump per spec §10. Minor (0.2.0 / 1.2.0) deferred until live
verification of envelope in real research run.

Refs: lichtpfad/h2t-skills#100"
```

---

## Task 11: Final integration check + push branch

**Files:** none (verification only).

- [ ] **Step 1: Run full test suite**

```bash
$PYTEST plugins/h2t-ops/skills/research/tests/ -v 2>&1 | tail -20
```

Expected: all PASS. Print pass count.

- [ ] **Step 2: Smoke test CLI shape — default stdout**

```bash
$PYTHON plugins/h2t-ops/skills/research/scripts/exa_search.py --version
```

Expected: `exa_search 0.1.1`, exit 0.

- [ ] **Step 3: Smoke test envelope flag against fixture (if EXA_API_KEY present)**

If `$EXA_API_KEY` is set:

```bash
$PYTHON plugins/h2t-ops/skills/research/scripts/exa_search.py search \
  --query "TouchDesigner POP" --mode fast --num-results 3 \
  --output-dir /tmp/h2t-envelope-smoke --project smoketest --envelope \
  | $PYTHON -c "import json,sys; e=json.load(sys.stdin); print('status=', e['status'], 'results=', len(e['results']))"
```

Expected: `status= OK results= 3` (or `DEGRADED results= 0` if Exa returned empty — both are valid envelope outputs).

If `$EXA_API_KEY` not set, skip with note in commit comment.

- [ ] **Step 4: Verify git log**

```bash
git -C C:/dev/h2t-skills log --oneline -12
```

Expected: 10 commits from this plan + spec commit (`9988792`) at the bottom of recent history.

- [ ] **Step 5: Push branch (if work happened on a branch)**

If on `main`, **stop and ask user** whether to push directly or create a feature branch. Per CLAUDE.md and project conventions, do not force-push or push to main without explicit instruction.

```bash
git -C C:/dev/h2t-skills branch --show-current
```

If branch is `main` — pause. If branch is feature branch — `git push -u origin <branch>` and open PR with body referencing issue #100.

---

## Self-Review Checklist (post-implementation)

After completing all tasks:

- [ ] Envelope schema in code matches §3 of spec exactly (field names, nesting, types)
- [ ] All 6 status decision rows from §3.1 covered by at least one test
- [ ] Default stdout (no `--envelope`) starts with `## Exa Search:` — back-compat preserved
- [ ] `.sources.json` always contains `meta.envelope` regardless of `--envelope` flag
- [ ] No `WebSearch` invocation anywhere in Python code
- [ ] No `time.sleep` calls outside `sleep_with_jitter` helper (greppable)
- [ ] All EXA_ERROR strings preserved verbatim where they existed before refactor
- [ ] `__version__`, SKILL.md `metadata.version`, REPORT-SPEC footer, `.claude-plugin/plugin.json` all show consistent versions

```bash
grep -rn "0\.1\.[01]" plugins/h2t-ops/skills/research/ plugins/h2t-ops/.claude-plugin/
```

Expected: only `0.1.1` references, no `0.1.0` left.
