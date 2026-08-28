---
title: "Research capability phase 1"
status: "draft"
date: "2026-07-08"
milestone: "research-exa"
issue: ""
---

# Research capability (Exa Research API) — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `research` capability to `h2t-ops research` that runs the Exa Research API (`POST /research/v1` → poll `GET /research/v1/{id}`) as an async, retrieval-first deep-research node, reusing the existing envelope / artifact / secret substrate.

**Architecture:** New `research_task` orchestrator in `exa.py` (create → poll loop → research envelope), a thin `ResearchClient.research()` wrapper that reuses `_write_provider_artifacts` / `_persist_thread_run` / `_persist_synthesis`, a `research` subparser in `commands.py`, and a new `research` provider-routing capability. Poll cadence and timeout are caller-controlled; `--wait` (blocking) is the default, `--no-wait` returns the `researchId` immediately.

**Tech Stack:** Python stdlib (`urllib`, `json`, `time`), pytest, existing `h2t_ops.connectors.research` package.

**Grounded contract (live-verified 2026-07-08):**
- `POST /research/v1` body `{"instructions": str, "model": str, "outputSchema"?: obj}` → **201** `{"researchId": "r_…", "createdAt": int, "model": str, "instructions": str, "status": "running"}`.
- `GET /research/v1/{researchId}` → **200** `{… "status": "running"|"completed"|"failed", "output"?: {"content": str} | structured, "citations"?: [{"id","url","title"?}], "finishedAt"?: int, "error"?: str}`.
- `?taskId=` query form is **invalid (400)** — path param only.
- `exa-research-fast` completes in ~20–25 s.
- Cost fields (`costDollars.total`, `numSearches`, `numPages`, `reasoningTokens`) live under `output.costDollars` and may be absent without `?events=true` — extract defensively, do not require.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `h2t_ops/connectors/research/exa.py` | Provider core: add GET support to `call_exa`; add research constants, `create_research`, `get_research`, `build_research_envelope`, `research_task` | Modify |
| `h2t_ops/connectors/research/provider_routing.py` | Add `"research"` capability | Modify |
| `h2t_ops/connectors/research/client.py` | Add `ResearchClient.research()` wrapper | Modify |
| `h2t_ops/connectors/research/commands.py` | Add `research` subparser + `run()` dispatch | Modify |
| `plugins/h2t-ops/skills/research/SKILL.md` | Document `research` mode; drop its "planned" marker | Modify |
| `tests/connectors/research/test_exa.py` | Tests for GET `call_exa` + research primitives + `research_task` | Modify |
| `tests/connectors/research/test_provider_routing.py` | Test `research` capability route | Modify |
| `tests/connectors/research/test_client.py` | Test `ResearchClient.research()` | Modify |
| `tests/connectors/research/test_commands.py` | Test `research` subparser + dispatch | Modify |

**Test-body note (learned):** tests here use `importlib.reload` / module-attr monkeypatch across sibling files. Do **not** treat verbatim test bodies as gospel — they encode *intent*. If a reload/monkeypatch desync appears, add explicit `sys.modules` cleanup (see `_remove_research_provider_modules` pattern) rather than fighting it.

Run all tests with: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/ -q`

---

## Task 1: GET support in `call_exa`

**Files:**
- Modify: `h2t_ops/connectors/research/exa.py:345-362` (`call_exa` signature + Request build)
- Test: `tests/connectors/research/test_exa.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_exa.py::test_call_exa_get_sends_no_body -v`
Expected: FAIL — `call_exa()` got an unexpected keyword argument `method`.

- [ ] **Step 3: Write minimal implementation**

Change the `call_exa` signature and Request construction:

```python
def call_exa(
    endpoint: str,
    body: dict[str, Any],
    api_key: str,
    timeout: int = 60,
    method: str = "POST",
) -> tuple[int, dict[str, Any], int]:
    """POST/GET to Exa and return (http_status, response_json, latency_ms)."""
    data = None if method == "GET" else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{_EXA_API}{endpoint}",
        data=data,
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"exa_search.py/{__version__} (h2t-ops:research)",
        },
        method=method,
    )
```

Leave the rest of `call_exa` (the `try/except` body) unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_exa.py::test_call_exa_get_sends_no_body -v`
Expected: PASS. Also run the existing POST tests to confirm no regression:
`C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_exa.py -k call_exa -q` → all PASS.

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/research/exa.py tests/connectors/research/test_exa.py
git commit -m "feat(research): add GET method support to call_exa"
```

---

## Task 2: Research constants + `create_research` / `get_research`

**Files:**
- Modify: `h2t_ops/connectors/research/exa.py` (add near `MODE_CONFIG`, and new functions before `__all__`)
- Test: `tests/connectors/research/test_exa.py`

- [ ] **Step 1: Write the failing tests**

```python
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
    monkeypatch.setattr(
        exa, "call_exa",
        lambda endpoint, body, api_key, **kw: (seen.update(body=body) or (201, {"researchId": "r_2", "status": "running"}, 20)),
    )
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_exa.py -k research -v`
Expected: FAIL — `AttributeError: module 'exa' has no attribute 'RESEARCH_MODELS'` / `create_research`.

- [ ] **Step 3: Write minimal implementation**

Add constants after `MODES = list(MODE_CONFIG.keys())` (around line 47):

```python
RESEARCH_MODELS = ("exa-research-fast", "exa-research", "exa-research-pro")
RESEARCH_DEFAULT_MODEL = "exa-research-fast"
RESEARCH_POLL_INTERVAL_SECONDS = 2.0
RESEARCH_TIMEOUT_SECONDS = 180.0
```

Add functions before `__all__`:

```python
def create_research(
    instructions: str,
    *,
    model: str,
    output_schema: dict[str, Any] | None,
    api_key: str,
) -> dict[str, Any]:
    """POST /research/v1 to create an async research task."""
    body: dict[str, Any] = {"instructions": instructions, "model": model}
    if output_schema:
        body["outputSchema"] = output_schema
    _status, data, _latency = call_exa("/research/v1", body, api_key)
    return data


def get_research(research_id: str, *, api_key: str) -> dict[str, Any]:
    """GET /research/v1/{id} to poll a research task."""
    _status, data, _latency = call_exa(
        f"/research/v1/{research_id}", {}, api_key, method="GET"
    )
    return data
```

Add `"RESEARCH_MODELS"`, `"RESEARCH_DEFAULT_MODEL"`, `"create_research"`, `"get_research"` to `__all__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_exa.py -k research -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/research/exa.py tests/connectors/research/test_exa.py
git commit -m "feat(research): add create_research/get_research primitives"
```

---

## Task 3: `build_research_envelope` + `research_task` orchestrator

**Files:**
- Modify: `h2t_ops/connectors/research/exa.py` (add before `__all__`)
- Test: `tests/connectors/research/test_exa.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_exa.py -k research_task -v`
Expected: FAIL — `module 'exa' has no attribute 'research_task'`.

- [ ] **Step 3: Write minimal implementation**

Add helper + orchestrator before `__all__`:

```python
def build_research_envelope(
    *,
    status: str,
    research_id: str,
    model: str,
    instructions: str,
    output: Any,
    citations: list[Any],
    attempts: list[dict[str, Any]],
    cost: float,
    num_searches: int | None,
    num_pages: int | None,
    reasoning_tokens: int | None,
    reason_for_fallback: str | None = None,
) -> dict[str, Any]:
    """Assemble the research provider envelope (compatible with artifact writer)."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    total_latency_ms = sum(a.get("latency_ms", 0) for a in attempts)
    return {
        "status": status,
        "primary_engine": "exa",
        "research_id": research_id,
        "model": model,
        "output": output,
        "citations": citations,
        "results": citations,  # artifact writer treats these as sources
        "telemetry": {
            "attempts": attempts,
            "reason_for_fallback": reason_for_fallback,
            "total_latency_ms": total_latency_ms,
            "total_cost_usd": cost,
            "num_searches": num_searches,
            "num_pages": num_pages,
            "reasoning_tokens": reasoning_tokens,
        },
        "meta": {
            "instructions": instructions,
            "model": model,
            "timestamp": timestamp,
            "envelope_version": ENVELOPE_VERSION,
        },
    }


def _research_cost(data: dict[str, Any]) -> tuple[float, int | None, int | None, int | None]:
    output = data.get("output")
    cost_block = output.get("costDollars", {}) if isinstance(output, dict) else {}
    if not isinstance(cost_block, dict):
        cost_block = {}
    try:
        total = float(cost_block.get("total", 0.0) or 0.0)
    except (TypeError, ValueError):
        total = 0.0
    return (
        total,
        cost_block.get("numSearches"),
        cost_block.get("numPages"),
        cost_block.get("reasoningTokens"),
    )


def research_task(
    instructions: str,
    *,
    api_key: str,
    model: str = RESEARCH_DEFAULT_MODEL,
    output_schema: dict[str, Any] | None = None,
    wait: bool = True,
    poll_interval: float = RESEARCH_POLL_INTERVAL_SECONDS,
    timeout_s: float = RESEARCH_TIMEOUT_SECONDS,
) -> tuple[dict[str, Any], int]:
    """Create an Exa research task and (optionally) poll to completion."""
    attempts: list[dict[str, Any]] = []
    try:
        created = create_research(
            instructions, model=model, output_schema=output_schema, api_key=api_key
        )
    except ExaPermanentError as exc:
        attempts.append({"engine": "exa", "endpoint": "/research/v1", "http": exc.http_status,
                         "latency_ms": exc.latency_ms, "error": "exa_auth_error" if exc.http_status in {401, 403} else "exa_4xx"})
        env = build_research_envelope(status="FAILED", research_id="", model=model, instructions=instructions,
                                      output=None, citations=[], attempts=attempts, cost=0.0,
                                      num_searches=None, num_pages=None, reasoning_tokens=None,
                                      reason_for_fallback="exa_create_failed")
        return env, (4 if exc.http_status in {401, 403} else 1)
    except (ExaTransientError, ExaMalformedResponseError) as exc:
        attempts.append({"engine": "exa", "endpoint": "/research/v1", "http": getattr(exc, "http_status", None),
                         "latency_ms": getattr(exc, "latency_ms", 0), "error": "exa_network"})
        env = build_research_envelope(status="FAILED", research_id="", model=model, instructions=instructions,
                                      output=None, citations=[], attempts=attempts, cost=0.0,
                                      num_searches=None, num_pages=None, reasoning_tokens=None,
                                      reason_for_fallback="exa_create_failed")
        return env, 6

    research_id = str(created.get("researchId", ""))
    attempts.append({"engine": "exa", "endpoint": "/research/v1", "http": 201, "latency_ms": 0, "error": None})

    if not wait:
        env = build_research_envelope(status="RUNNING", research_id=research_id, model=model,
                                      instructions=instructions, output=None, citations=[], attempts=attempts,
                                      cost=0.0, num_searches=None, num_pages=None, reasoning_tokens=None)
        return env, 0

    start = time.monotonic()
    while True:
        data = get_research(research_id, api_key=api_key)
        state = str(data.get("status", "running"))
        attempts.append({"engine": "exa", "endpoint": f"/research/v1/{research_id}", "http": 200,
                         "latency_ms": 0, "error": None})
        if state == "completed":
            cost, n_search, n_pages, r_tokens = _research_cost(data)
            env = build_research_envelope(status="OK", research_id=research_id, model=model,
                                          instructions=instructions, output=data.get("output"),
                                          citations=data.get("citations", []), attempts=attempts, cost=cost,
                                          num_searches=n_search, num_pages=n_pages, reasoning_tokens=r_tokens)
            return env, 0
        if state == "failed":
            env = build_research_envelope(status="FAILED", research_id=research_id, model=model,
                                          instructions=instructions, output=data.get("output"),
                                          citations=[], attempts=attempts, cost=0.0, num_searches=None,
                                          num_pages=None, reasoning_tokens=None,
                                          reason_for_fallback=str(data.get("error") or "research_failed"))
            return env, 1
        if time.monotonic() - start > timeout_s:
            env = build_research_envelope(status="FAILED", research_id=research_id, model=model,
                                          instructions=instructions, output=None, citations=[], attempts=attempts,
                                          cost=0.0, num_searches=None, num_pages=None, reasoning_tokens=None,
                                          reason_for_fallback="research_timeout")
            return env, 3
        sleep_with_jitter(poll_interval)
```

Add `"build_research_envelope"` and `"research_task"` to `__all__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_exa.py -k research_task -v`
Expected: PASS (all 5).

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/research/exa.py tests/connectors/research/test_exa.py
git commit -m "feat(research): add research_task orchestrator with poll loop"
```

---

## Task 4: `research` provider-routing capability

**Files:**
- Modify: `h2t_ops/connectors/research/provider_routing.py:9-18` (`CAPABILITIES`), `:31-48` (`PROVIDER_CAPABILITIES`)
- Test: `tests/connectors/research/test_provider_routing.py`

- [ ] **Step 1: Write the failing test**

```python
def test_research_capability_routes_to_exa(monkeypatch):
    from h2t_ops.connectors.research import provider_routing

    monkeypatch.setattr(provider_routing, "_secret_available", lambda name: name == "EXA_API_KEY")
    route = provider_routing.select_route("research")

    assert route["selected_provider"] == "exa"
    assert route["configured"] is True
    assert "research" in provider_routing.CAPABILITIES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_provider_routing.py::test_research_capability_routes_to_exa -v`
Expected: FAIL — `UsageError: unknown research capability: research`.

- [ ] **Step 3: Write minimal implementation**

In `CAPABILITIES` set, add `"research"`:

```python
CAPABILITIES = {
    "preflight",
    "search",
    "answer",
    "similar",
    "crawl",
    "author",
    "fetch",
    "visual_ocr",
    "research",
}
```

In `PROVIDER_CAPABILITIES` tuple, add after the `author` row:

```python
    ProviderCapability("exa", "research", required_secrets=("EXA_API_KEY",), priority=10),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_provider_routing.py::test_research_capability_routes_to_exa -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/research/provider_routing.py tests/connectors/research/test_provider_routing.py
git commit -m "feat(research): add research provider-routing capability"
```

---

## Task 5: `ResearchClient.research()` wrapper

**Files:**
- Modify: `h2t_ops/connectors/research/client.py` (add method after `answer()`, around line 1211)
- Test: `tests/connectors/research/test_client.py`

- [ ] **Step 1: Write the failing test**

```python
def test_client_research_ok(monkeypatch, tmp_path):
    from h2t_ops.connectors.research import client as client_mod
    from h2t_ops.connectors.research import exa

    monkeypatch.setattr(client_mod, "resolve_secret", lambda name: "k")
    monkeypatch.setattr(client_mod.ResearchClient, "_require_research_route", lambda self, cap, provider=None: {"selected_provider": "exa"})

    envelope = exa.build_research_envelope(
        status="OK", research_id="r_1", model="exa-research-fast", instructions="Q",
        output={"content": "Answer."}, citations=[{"url": "https://x", "title": "X"}],
        attempts=[{"engine": "exa", "endpoint": "/research/v1", "http": 201, "latency_ms": 0, "error": None}],
        cost=0.02, num_searches=3, num_pages=5, reasoning_tokens=900,
    )
    monkeypatch.setattr(exa, "research_task", lambda instructions, **kw: (envelope, 0))

    client = client_mod.ResearchClient(output_dir=tmp_path)
    result = client.research(instructions="Q", project="h2t-skills")

    assert result["kind"] == "research_provider_envelope"
    assert result["status"] == "OK"
    assert result["output"]["content"] == "Answer."
    assert "artifact" in result


def test_client_research_failed_raises(monkeypatch, tmp_path):
    from h2t_ops.connectors.research import client as client_mod
    from h2t_ops.connectors.research import exa
    from h2t_ops.core.errors import ProviderError

    monkeypatch.setattr(client_mod, "resolve_secret", lambda name: "k")
    monkeypatch.setattr(client_mod.ResearchClient, "_require_research_route", lambda self, cap, provider=None: {"selected_provider": "exa"})

    envelope = exa.build_research_envelope(
        status="FAILED", research_id="r_1", model="exa-research-fast", instructions="Q",
        output=None, citations=[],
        attempts=[{"engine": "exa", "endpoint": "/research/v1", "http": 201, "latency_ms": 0, "error": None}],
        cost=0.0, num_searches=None, num_pages=None, reasoning_tokens=None,
        reason_for_fallback="research_timeout",
    )
    monkeypatch.setattr(exa, "research_task", lambda instructions, **kw: (envelope, 3))

    client = client_mod.ResearchClient(output_dir=tmp_path)
    with pytest.raises(ProviderError):
        client.research(instructions="Q", project="h2t-skills")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_client.py -k research -v`
Expected: FAIL — `AttributeError: 'ResearchClient' object has no attribute 'research'`.

- [ ] **Step 3: Write minimal implementation**

Add this method to `ResearchClient`, immediately after `answer()` (before `resolve_author`):

```python
    def research(
        self,
        *,
        instructions: str,
        model: str | None = None,
        output_schema: dict[str, Any] | None = None,
        wait: bool = True,
        poll_interval: float | None = None,
        timeout_s: float | None = None,
        project: str = "default",
    ) -> dict[str, Any]:
        """Run an Exa Research API task and persist provider artifacts."""
        from h2t_ops.connectors.research import exa

        self._require_research_route("research", provider="exa")
        api_key = resolve_secret("EXA_API_KEY")
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "model": model or exa.RESEARCH_DEFAULT_MODEL,
            "output_schema": output_schema,
            "wait": wait,
        }
        if poll_interval is not None:
            kwargs["poll_interval"] = poll_interval
        if timeout_s is not None:
            kwargs["timeout_s"] = timeout_s
        envelope, exit_code = exa.research_task(instructions, **kwargs)

        telemetry = _artifact_telemetry(envelope)
        artifact = self._write_provider_artifacts(
            kind="research",
            slug_source=instructions,
            project=project,
            provider_envelope=envelope,
            telemetry=telemetry,
            ledger_provider="exa",
            ledger_endpoint="/research/v1",
            ledger_mode=str(envelope.get("model", "research")),
        )
        run_refs = self._persist_thread_run(
            project=project,
            query=instructions,
            provider="exa",
            topics=["research"],
            document_ids=[],
            created_at=artifact["created_at"],
        )
        output = envelope.get("output")
        summary_text = str(output.get("content")) if isinstance(output, dict) else ""
        if summary_text:
            synthesis_refs = self._persist_synthesis(
                thread_id=run_refs["thread_id"],
                run_id=run_refs["run_id"],
                summary=summary_text,
                created_at=artifact["created_at"],
                project=project,
            )
            artifact = self._attach_research_refs(artifact, {**run_refs, **synthesis_refs})
        else:
            artifact = self._attach_research_refs(artifact, run_refs)

        if envelope.get("status") == "FAILED":
            _raise_for_provider_failure("Exa research failed", envelope, exit_code)

        safe_envelope = sanitize_details(envelope)
        return {
            "kind": "research_provider_envelope",
            **safe_envelope,
            "artifact": artifact,
        }
```

Note: `_artifact_telemetry` already reads `telemetry.total_cost_usd` — the new `num_searches`/`num_pages`/`reasoning_tokens` ride along inside the envelope's `telemetry` and are persisted verbatim in the artifact. No change needed there.

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_client.py -k research -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/research/client.py tests/connectors/research/test_client.py
git commit -m "feat(research): add ResearchClient.research wrapper"
```

---

## Task 6: `research` subparser + `run()` dispatch

**Files:**
- Modify: `h2t_ops/connectors/research/commands.py` (add subparser in `register()` after `answer_p`, add dispatch in `run()` after the `answer` branch)
- Test: `tests/connectors/research/test_commands.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_research_subparser_registered():
    from h2t_ops import cli
    parser = cli.build_parser()
    ns = parser.parse_args([
        "research", "research",
        "--instructions", "Summarize AI safety",
        "--model", "exa-research",
        "--no-wait",
    ])
    assert ns.research_cmd == "research"
    assert ns.instructions == "Summarize AI safety"
    assert ns.model == "exa-research"
    assert ns.wait is False


def test_research_model_choices():
    from h2t_ops import cli
    from h2t_ops.connectors.research import commands as research_commands  # noqa: F401
    parser = cli.build_parser()
    research_parent = _subparser(parser, "research")
    research_sub = _subparser(research_parent, "research")
    assert _option_choices(research_sub, "--model") == {
        "exa-research-fast", "exa-research", "exa-research-pro",
    }


def test_research_dispatch_calls_client(monkeypatch):
    from types import SimpleNamespace
    from h2t_ops.connectors.research import commands as research_commands

    seen = {}

    class FakeClient:
        def __init__(self, **kw):
            pass
        def research(self, **kw):
            seen.update(kw)
            return {"kind": "research_provider_envelope", "status": "OK"}

    monkeypatch.setattr(
        "h2t_ops.connectors.research.client.ResearchClient", FakeClient
    )
    args = SimpleNamespace(
        research_cmd="research", instructions="Q", model="exa-research-fast",
        schema=None, wait=True, poll_interval=None, timeout_s=None,
        project="h2t-skills", output_dir=None,
    )
    result = research_commands.run(args)
    assert result["status"] == "OK"
    assert seen["instructions"] == "Q"
    assert seen["project"] == "h2t-skills"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_commands.py -k research_ -v`
Expected: FAIL — `argument research_cmd: invalid choice: 'research'` (subparser not registered).

- [ ] **Step 3: Write minimal implementation**

In `register()`, add after the `answer_p` block (after line 174) and before `resolve_author`:

```python
    research_p = cmds.add_parser("research", help="Run a deep async research task via Exa Research API")
    research_p.add_argument("--instructions", required=True)
    research_p.add_argument(
        "--model",
        default="exa-research-fast",
        choices=["exa-research-fast", "exa-research", "exa-research-pro"],
    )
    research_p.add_argument("--schema", dest="schema", help="path to a JSON schema file, or inline JSON")
    research_p.add_argument("--wait", dest="wait", action="store_true", default=True)
    research_p.add_argument("--no-wait", dest="wait", action="store_false")
    research_p.add_argument("--poll-interval", type=float, dest="poll_interval")
    research_p.add_argument("--timeout-s", type=float, dest="timeout_s")
    research_p.add_argument("--project", default="default")
    research_p.add_argument("--output-dir", dest="output_dir")
    add_fmt(research_p)
```

In `run()`, add after the `answer` branch (after line 275):

```python
    if cmd == "research":
        return client.research(
            instructions=args.instructions,
            model=args.model,
            output_schema=_load_schema(getattr(args, "schema", None)),
            wait=args.wait,
            poll_interval=getattr(args, "poll_interval", None),
            timeout_s=getattr(args, "timeout_s", None),
            project=args.project,
        )
```

Add a module-level helper near `_split_csv` (after line 188):

```python
def _load_schema(raw: str | None) -> dict[str, Any] | None:
    """Load an output schema from a file path or inline JSON string."""
    if not raw:
        return None
    import json
    from pathlib import Path

    from h2t_ops.core.errors import UsageError

    candidate = Path(raw).expanduser()
    text = candidate.read_text(encoding="utf-8") if candidate.is_file() else raw
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise UsageError(f"--schema is neither a readable file nor valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise UsageError("--schema must be a JSON object")
    return parsed
```

Note: in `test_research_dispatch_calls_client` the fake args set `schema=None`, so `_load_schema` returns `None` and no file I/O occurs.

- [ ] **Step 4: Run tests to verify they pass**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_commands.py -k research_ -v`
Expected: PASS (all 3).

- [ ] **Step 5: Commit**

```bash
git add h2t_ops/connectors/research/commands.py tests/connectors/research/test_commands.py
git commit -m "feat(research): add research subcommand to CLI"
```

---

## Task 7: Skill documentation — promote `research` from planned to live

**Files:**
- Modify: `plugins/h2t-ops/skills/research/SKILL.md`

- [ ] **Step 1: Add a `research` row to the capability decision guide table**

In the decision-guide table, add this row after the `search --mode deep` row:

```markdown
| Multi-hop deep dig, "разберись в теме X" | `research --instructions "..."` | async Exa Research API, ~20–120 s, cited report |
```

- [ ] **Step 2: Move `research` out of the "planned" block**

In the `### Planned capabilities (not yet available — do not call)` section, delete the `**research**` bullet (it is now live). Keep the `**agent**` bullet. Add a short live-usage block above `## Boundary`:

```markdown
## Research mode (async deep dig)

```bash
h2t-ops research research --instructions "..." --model exa-research-fast --project "$RESEARCH_PROJECT" --json
h2t-ops research research --instructions "..." --no-wait --json   # returns researchId, poll later
```

- Models: `exa-research-fast` (default) / `exa-research` / `exa-research-pro` (deeper, pricier).
- `--wait` (default) blocks and polls; `--no-wait` returns the `researchId` immediately.
- Retrieval-first: prefer taking the returned sources/citations and synthesizing under
  evidence-grounded discipline over shipping the black-box `output.content` verbatim for client work.
```

- [ ] **Step 3: Verify no dangling "planned" reference to research**

Run: `C:/dev/h2t-skills/.venv/Scripts/python plugins/h2t-dev/skills/docs-lint/scripts/lint.py audit --root C:/dev/h2t-skills`
Expected: no new errors introduced by the skill edit.

- [ ] **Step 4: Commit**

```bash
git add plugins/h2t-ops/skills/research/SKILL.md
git commit -m "docs(research): document live research capability in skill"
```

---

## Final verification

- [ ] **Full research test suite green**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/ -q`
Expected: all PASS.

- [ ] **Lint clean**

Run: `C:/dev/h2t-skills/.venv/Scripts/ruff check h2t_ops/connectors/research/`
Expected: no errors.

- [ ] **Live smoke (optional, costs ~1 research-fast run)**

Run: `C:/dev/h2t-skills/.venv/Scripts/python -m h2t_ops.cli research research --instructions "In one sentence, what is TouchDesigner?" --model exa-research-fast --project h2t-skills --json`
Expected: `status: OK`, non-empty `output.content`, `telemetry.total_cost_usd` present.

- [ ] **Bump plugin version + close issue**

```bash
python scripts/bump_plugin.py h2t-ops 0.2.0
gh issue close 277 --repo lichtpfad/h2t-skills --comment "Implemented in <hash> (Phase 1 research capability)"
```

---

## Self-review notes

- **Spec coverage (Phase 1):** GET support (T1), create/poll primitives (T2), `research_task` + envelope + telemetry `numSearches/numPages/reasoningTokens` (T3), routing capability (T4), client wrapper (T5), CLI subparser + `--wait/--no-wait` + `--model` + `--schema` (T6), skill docs (T7). All Phase-1 acceptance-criteria items from issue #277 map to a task.
- **`--wait` default:** resolved to blocking-by-default (`store_true default=True` + `--no-wait store_false`), per open-question 2 lean.
- **`call_exa` endpoint hardcode:** the spec's "parameterize call_exa by endpoint" is satisfied — `call_exa` already takes `endpoint`; T1 adds the missing `method` axis needed for polling. `_classify_attempt_from_call` stays search-only and is untouched.
- **Type consistency:** `research_task` returns `(envelope, exit_code)` matching `answer`/`find_similar`; envelope keys (`status`, `output`, `citations`, `results`, `telemetry`, `meta`) are used identically in T5.
- **Cost defensiveness:** `_research_cost` tolerates missing `costDollars` (confirmed absent in fast-model probe without `events=true`).

---

## Gate review fixes (applied 2026-07-08 after council + codex)

The plan-review gate (2 judges + codex) returned FAIL. These deltas are now authoritative — where they conflict with a task above, the delta wins.

**F1 (blocking) — failure→exception mapping.** Do NOT reuse `_raise_for_provider_failure` in `research()` (its exit-code semantics are search-specific: exit 3→NetworkError makes a poll timeout look like a network error, and no path yields `ProviderError`). Replace the raise block in Task 5 with explicit mapping:

```python
        if envelope.get("status") == "FAILED":
            details = sanitize_details({"provider_envelope": envelope})
            attempts = envelope.get("telemetry", {}).get("attempts", [])
            last_error = attempts[-1].get("error") if attempts else None
            if last_error == "exa_auth_error" or exit_code == 4:
                raise AuthError("Exa research failed: auth", details=details)
            if last_error == "exa_network":
                raise NetworkError("Exa research failed: network", details=details)
            reason = envelope.get("telemetry", {}).get("reason_for_fallback")
            raise ProviderError(f"Exa research failed: {reason}", details=details)
```

Now `test_client_research_failed_raises` (timeout, exit 3) correctly raises `ProviderError` — the test stands as written. (`AuthError`, `NetworkError`, `ProviderError` are already imported at top of client.py.)

**F2 (blocking) — poll backoff (AC1).** In `research_task`, replace the constant sleep with bounded exponential backoff:

```python
    start = time.monotonic()
    current_interval = poll_interval
    while True:
        ...  # (get_research, state handling, timeout check unchanged)
        sleep_with_jitter(current_interval)
        current_interval = min(current_interval * 1.5, 30.0)
```

Add this test to `test_exa.py`:

```python
def test_research_task_poll_backoff_grows(monkeypatch):
    intervals = []
    monkeypatch.setattr(exa, "sleep_with_jitter", lambda s: intervals.append(s))
    monkeypatch.setattr(exa, "create_research",
        lambda instructions, *, model, output_schema, api_key: {"researchId": "r_1", "status": "running"})
    polls = iter([
        {"researchId": "r_1", "status": "running"},
        {"researchId": "r_1", "status": "running"},
        {"researchId": "r_1", "status": "completed", "output": {"content": "ok"}, "citations": []},
    ])
    monkeypatch.setattr(exa, "get_research", lambda rid, *, api_key: next(polls))
    exa.research_task("Q", api_key="k", wait=True, poll_interval=2.0, timeout_s=1000.0)
    assert intervals == [2.0, 3.0]  # 2.0, then 2.0*1.5
```

**F3 (blocking) — poll-loop resilience (codex NEW#3).** Wrap `get_research` in the loop in try/except so provider errors during polling become a FAILED envelope instead of escaping:

```python
        try:
            data = get_research(research_id, api_key=api_key)
        except (ExaPermanentError, ExaTransientError, ExaMalformedResponseError) as exc:
            attempts.append({"engine": "exa", "endpoint": f"/research/v1/{research_id}",
                             "http": getattr(exc, "http_status", None),
                             "latency_ms": getattr(exc, "latency_ms", 0), "error": "exa_poll_failed"})
            env = build_research_envelope(status="FAILED", research_id=research_id, model=model,
                                          instructions=instructions, output=None, citations=[], attempts=attempts,
                                          cost=0.0, num_searches=None, num_pages=None, reasoning_tokens=None,
                                          reason_for_fallback="exa_poll_failed")
            return env, 1
```

Add a test asserting a poll-time `ExaPermanentError` yields `status=="FAILED"`, exit 1.

**F4 (blocking) — schema-validation test (AC7).** Add to `test_commands.py`:

```python
def test_load_schema_invalid_json_raises():
    from h2t_ops.connectors.research import commands as research_commands
    from h2t_ops.core.errors import UsageError
    with pytest.raises(UsageError):
        research_commands._load_schema("{not valid json")
```

**F5 (nit) — synthesis None guard (codex NEW#5).** In Task 5, guard against `str(None)`:

```python
        output = envelope.get("output")
        content = output.get("content") if isinstance(output, dict) else None
        summary_text = str(content) if content else ""
```

**F6 (nit) — meta.query (codex NEW#4 / judge nit).** In `build_research_envelope`, add `"query": instructions` alongside `"instructions": instructions` in `meta`, so `_render_partial_markdown` (reads `meta.query`) renders correctly.

**F7 (nit) — SKILL.md prose.** In Task 7, also fix the now-stale "planned" cross-references (the "use the **planned** `research` capability below" line and the "For **both** planned modes" line) so only `agent` remains described as planned.

**F8 (nit) — version bump.** Final-verification bump is **patch**, not minor (semver rule: minor only after live confirmation). Use the next patch of the current h2t-ops plugin version, and only bump minor after live smoke passes in a real session.

**Accepted deviations (non-blocking, no change):** AC2 literal `/search` hardcode in `_classify_attempt_from_call` stays (research builds its own attempts; intent met). Test files distributed across existing suites instead of one `test_research_task.py` (better coverage).
