# Skill Intelligence Graph — Foundation (Steps 6.0 + 6.1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap `skill-patterns` and `skill-lessons` sources in h2t-graphs, then implement `lib/skill_graph/` — a Python client + CLI that skills can call to query patterns and write lessons.

**Architecture:** `SkillGraphClient` wraps h2t-graphs HTTP API using stdlib `urllib` (no extra deps). Dual-token policy: RO for reads, RW for writes, both loaded from `~/.dor/secrets.env`. CLI wrapper (`cli.py`) exposes `query`, `add-lesson`, `add-pattern` subcommands for use in SKILL.md bash steps.

**Tech Stack:** Python 3.11, stdlib only (`urllib`, `argparse`, `json`), pytest + `unittest.mock`

**Scope:** Steps 6.0 and 6.1 only. Research pipeline (6.2), SKILL.md integration (6.3), GEPA (6.4) are separate plans.

**Spec:** `docs/superpowers/specs/2026-04-06-skill-intelligence-graph-design.md`

---

## File Map

**Create:**
- `lib/skill_graph/__init__.py` — re-exports `SkillGraphClient`
- `lib/skill_graph/client.py` — `SkillGraphClient`: `query()`, `add_lesson()`, `add_pattern()`, `_load_secrets()`, `_get()`, `_post()`
- `lib/skill_graph/cli.py` — argparse CLI: `query`, `add-lesson`, `add-pattern` subcommands
- `tests/skill_graph/__init__.py` — empty
- `tests/skill_graph/test_client.py` — unit tests for client (mocked HTTP)
- `tests/skill_graph/test_cli.py` — unit tests for CLI (mocked client)

**Modify:**
- `lib/eval/session.py` — add optional `skill_graph=None` param to `SkillEval.__init__` and `__exit__`

---

## Task 0: Verify h2t-graphs source bootstrap

This is a manual verification task — no code. Must be complete before Task 1.

- [ ] **Step 0.1: Read the API docs**

```bash
source ~/.dor/secrets.env
curl -s -H "X-H2T-Token: $H2T_GRAPHS_TOKEN_RO" \
  https://graphs.lichtpfadstudio.com/llms.txt
```

Look for: source creation endpoint, add_insight endpoint path and payload schema.

- [ ] **Step 0.2: Check existing sources**

```bash
source ~/.dor/secrets.env
curl -s -H "X-H2T-Token: $H2T_GRAPHS_TOKEN_RO" \
  "https://graphs.lichtpfadstudio.com/api/query?source=skill-patterns&search=test"
```

Expected: empty results list `[]` → source exists.
If 404 or error → source does not exist yet, proceed to Step 0.3.

- [ ] **Step 0.3: Create sources (if needed)**

If source creation is self-serve via API (check /llms.txt output from 0.1):

```bash
source ~/.dor/secrets.env
# Create skill-patterns
curl -s -X POST \
  -H "X-H2T-Token: $H2T_GRAPHS_TOKEN_RW" \
  -H "Content-Type: application/json" \
  -d '{"name": "skill-patterns", "description": "Best practices for skill authoring"}' \
  https://graphs.lichtpfadstudio.com/api/sources

# Create skill-lessons
curl -s -X POST \
  -H "X-H2T-Token: $H2T_GRAPHS_TOKEN_RW" \
  -H "Content-Type: application/json" \
  -d '{"name": "skill-lessons", "description": "Runtime lessons learned from debug sessions and evals"}' \
  https://graphs.lichtpfadstudio.com/api/sources
```

If source creation requires admin access in h2t-graphs repo — open an issue there and block until resolved.

- [ ] **Step 0.4: Smoke test both sources**

```bash
source ~/.dor/secrets.env
curl -s -H "X-H2T-Token: $H2T_GRAPHS_TOKEN_RO" \
  "https://graphs.lichtpfadstudio.com/api/query?source=skill-patterns&search=test"
curl -s -H "X-H2T-Token: $H2T_GRAPHS_TOKEN_RO" \
  "https://graphs.lichtpfadstudio.com/api/query?source=skill-lessons&search=test"
```

Expected: both return `[]` or `{"results": []}`, not 404. **Do not proceed to Task 1 until both pass.**

- [ ] **Step 0.5: Record the add_insight endpoint**

From /llms.txt output, note the exact path and payload format for writing a node.
Example (confirm actual): `POST /api/add_insight` with `{"source": "...", "content": {...}}`.

Update `lib/skill_graph/client.py` constants in Task 1 if the path differs.

---

## Task 1: Package skeleton + secrets loader

**Files:**
- Create: `lib/skill_graph/__init__.py`
- Create: `lib/skill_graph/client.py` (skeleton only)
- Create: `tests/skill_graph/__init__.py`
- Create: `tests/skill_graph/test_client.py` (skeleton)

- [ ] **Step 1.1: Write the failing test for secrets loader**

Create `tests/skill_graph/__init__.py` (empty):
```python
```

Create `tests/skill_graph/test_client.py`:
```python
"""Unit tests for SkillGraphClient — all HTTP mocked."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

import os
import json
import pytest
from unittest.mock import patch, mock_open, MagicMock


def test_load_secrets_from_env_file(tmp_path):
    secrets_file = tmp_path / "secrets.env"
    secrets_file.write_text(
        "H2T_GRAPHS_TOKEN_RO=ro-test-token\n"
        "H2T_GRAPHS_TOKEN_RW=rw-test-token\n"
        "H2T_GRAPHS_URL=https://test.example.com\n"
    )
    from skill_graph.client import _load_secrets
    secrets = _load_secrets(secrets_path=str(secrets_file))
    assert secrets["H2T_GRAPHS_TOKEN_RO"] == "ro-test-token"
    assert secrets["H2T_GRAPHS_TOKEN_RW"] == "rw-test-token"
    assert secrets["H2T_GRAPHS_URL"] == "https://test.example.com"


def test_load_secrets_falls_back_to_env(tmp_path, monkeypatch):
    monkeypatch.setenv("H2T_GRAPHS_TOKEN_RO", "env-ro")
    monkeypatch.setenv("H2T_GRAPHS_TOKEN_RW", "env-rw")
    from skill_graph.client import _load_secrets
    secrets = _load_secrets(secrets_path=str(tmp_path / "nonexistent.env"))
    assert secrets["H2T_GRAPHS_TOKEN_RO"] == "env-ro"
    assert secrets["H2T_GRAPHS_TOKEN_RW"] == "env-rw"
```

- [ ] **Step 1.2: Run test to verify it fails**

```bash
cd C:/dev/claude-agent-skills
pytest tests/skill_graph/test_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'skill_graph'`

- [ ] **Step 1.3: Create package skeleton**

Create `lib/skill_graph/__init__.py`:
```python
from .client import SkillGraphClient

__all__ = ["SkillGraphClient"]
```

Create `lib/skill_graph/client.py`:
```python
"""SkillGraphClient — thin HTTP wrapper over h2t-graphs API.

Token policy:
  query()       → H2T_GRAPHS_TOKEN_RO
  add_lesson()  → H2T_GRAPHS_TOKEN_RW
  add_pattern() → H2T_GRAPHS_TOKEN_RW

Both loaded from ~/.dor/secrets.env (falls back to env vars).
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

_ADD_INSIGHT_PATH = "/api/add_insight"  # verify from /llms.txt in Step 0.5
_QUERY_PATH = "/api/query"

VALID_PATTERN_TYPES = frozenset({
    "hook", "etl", "pipeline", "generation",
    "eval", "marketplace", "trigger", "eval-derived",
})


def _load_secrets(secrets_path: Optional[str] = None) -> dict[str, str]:
    """Load token/URL from secrets.env file, fall back to env vars."""
    path = Path(secrets_path) if secrets_path else Path.home() / ".dor" / "secrets.env"
    result: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, _, val = line.partition("=")
                result[key.strip()] = val.strip()
    # env vars override file values
    for key in ("H2T_GRAPHS_TOKEN_RO", "H2T_GRAPHS_TOKEN_RW", "H2T_GRAPHS_URL"):
        if os.environ.get(key):
            result[key] = os.environ[key]
    return result


class SkillGraphClient:
    def __init__(self, url: Optional[str] = None, secrets_path: Optional[str] = None):
        self._secrets = _load_secrets(secrets_path)
        self.url = (
            url
            or self._secrets.get("H2T_GRAPHS_URL")
            or "https://graphs.lichtpfadstudio.com"
        ).rstrip("/")

    @property
    def _ro_token(self) -> str:
        return self._secrets.get("H2T_GRAPHS_TOKEN_RO", "")

    @property
    def _rw_token(self) -> str:
        return self._secrets.get("H2T_GRAPHS_TOKEN_RW", "")

    def _get(self, path: str, params: dict, token: str) -> dict:
        query = urllib.parse.urlencode(params)
        req = urllib.request.Request(
            f"{self.url}{path}?{query}",
            headers={"X-H2T-Token": token},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def _post(self, path: str, data: dict, token: str) -> dict:
        body = json.dumps(data).encode()
        req = urllib.request.Request(
            f"{self.url}{path}",
            data=body,
            headers={"X-H2T-Token": token, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def query(self, context: str, skill_name: Optional[str] = None,
              sources: tuple = ("skill-patterns", "skill-lessons"),
              top_k: int = 5) -> list[dict]:
        raise NotImplementedError

    def add_lesson(self, skill_name: str, trigger: str, resolution: str,
                   lesson_type: str = "bug", session_id: Optional[str] = None,
                   eval_score_before: Optional[float] = None,
                   eval_score_after: Optional[float] = None,
                   crosslinks: Optional[list[dict]] = None) -> str:
        raise NotImplementedError

    def add_pattern(self, pattern_type: str, title: str, body: str, source: str,
                    applies_to: Optional[list[str]] = None, confidence: float = 0.7,
                    source_url: Optional[str] = None,
                    tags: Optional[list[str]] = None) -> str:
        raise NotImplementedError
```

- [ ] **Step 1.4: Run tests**

```bash
pytest tests/skill_graph/test_client.py -v
```

Expected: `test_load_secrets_from_env_file` PASS, `test_load_secrets_falls_back_to_env` PASS

- [ ] **Step 1.5: Commit**

```bash
git add lib/skill_graph/ tests/skill_graph/
git commit -m "feat(skill-graph): add package skeleton + secrets loader"
```

---

## Task 2: `query()` — semantic search with RO token

**Files:**
- Modify: `lib/skill_graph/client.py` — implement `query()`
- Modify: `tests/skill_graph/test_client.py` — add query tests

- [ ] **Step 2.1: Write failing tests**

Append to `tests/skill_graph/test_client.py`:
```python
def _make_client(url="https://test.example.com", ro="ro-tok", rw="rw-tok"):
    from skill_graph.client import SkillGraphClient
    client = SkillGraphClient(url=url, secrets_path="/nonexistent")
    client._secrets = {"H2T_GRAPHS_TOKEN_RO": ro, "H2T_GRAPHS_TOKEN_RW": rw}
    return client


def _mock_urlopen(response_data: dict):
    """Return a context manager mock that yields a response with json data."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(response_data).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_query_uses_ro_token():
    client = _make_client()
    fake_resp = {"results": [{"id": "p1", "score": 0.9, "title": "Hook pattern"}]}
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(fake_resp)) as mock_open:
        results = client.query("hook injection", sources=("skill-patterns",))
    call_args = mock_open.call_args[0][0]
    assert call_args.get_header("X-h2t-token") == "ro-tok"


def test_query_sends_semantic_param():
    client = _make_client()
    fake_resp = {"results": []}
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(fake_resp)):
        client.query("hook injection", sources=("skill-patterns",))
    # verified via URL in urlopen call
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(fake_resp)) as m:
        client.query("my context", sources=("skill-patterns",))
    url = m.call_args[0][0].full_url
    assert "semantic=my+context" in url or "semantic=my%20context" in url
    assert "source=skill-patterns" in url


def test_query_merges_sources_and_returns_top_k():
    client = _make_client()
    resp_patterns = {"results": [
        {"id": "p1", "score": 0.9},
        {"id": "p2", "score": 0.5},
    ]}
    resp_lessons = {"results": [
        {"id": "l1", "score": 0.8},
    ]}
    responses = [_mock_urlopen(resp_patterns), _mock_urlopen(resp_lessons)]
    with patch("urllib.request.urlopen", side_effect=responses):
        results = client.query("test", sources=("skill-patterns", "skill-lessons"), top_k=2)
    assert len(results) == 2
    assert results[0]["id"] == "p1"   # highest score first
    assert results[1]["id"] == "l1"


def test_query_silent_on_http_error():
    client = _make_client()
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
        results = client.query("test")  # must not raise
    assert results == []
```

- [ ] **Step 2.2: Run to verify failure**

```bash
pytest tests/skill_graph/test_client.py::test_query_uses_ro_token -v
```

Expected: `NotImplementedError`

- [ ] **Step 2.3: Implement `query()`**

Replace the `raise NotImplementedError` in `query()`:
```python
def query(self, context: str, skill_name: Optional[str] = None,
          sources: tuple = ("skill-patterns", "skill-lessons"),
          top_k: int = 5) -> list[dict]:
    results: list[dict] = []
    for source in sources:
        params: dict = {"source": source, "semantic": context, "limit": top_k}
        try:
            data = self._get(_QUERY_PATH, params, self._ro_token)
            results.extend(data.get("results", []))
        except Exception:
            pass  # never crash a skill for graph failure
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:top_k]
```

- [ ] **Step 2.4: Run all query tests**

```bash
pytest tests/skill_graph/test_client.py -v
```

Expected: all PASS

- [ ] **Step 2.5: Commit**

```bash
git add lib/skill_graph/client.py tests/skill_graph/test_client.py
git commit -m "feat(skill-graph): implement query() with RO token + multi-source merge"
```

---

## Task 3: `add_lesson()` — write lesson + crosslink patch

**Files:**
- Modify: `lib/skill_graph/client.py` — implement `add_lesson()`
- Modify: `tests/skill_graph/test_client.py` — add lesson tests

- [ ] **Step 3.1: Write failing tests**

Append to `tests/skill_graph/test_client.py`:
```python
def test_add_lesson_uses_rw_token():
    client = _make_client()
    with patch("urllib.request.urlopen", return_value=_mock_urlopen({"id": "l1"})) as m:
        client.add_lesson("session-start", "gate skipped", "added GATE step")
    req = m.call_args[0][0]
    assert req.get_header("X-h2t-token") == "rw-tok"


def test_add_lesson_payload_structure():
    client = _make_client()
    with patch("urllib.request.urlopen", return_value=_mock_urlopen({"id": "l1"})) as m:
        client.add_lesson(
            skill_name="gmail",
            trigger="script not found",
            resolution="added $SKILL_GRAPH env var",
            lesson_type="bug",
            session_id="dev-agent-skills-test-2026-04-07",
        )
    req = m.call_args[0][0]
    payload = json.loads(req.data.decode())
    assert payload["source"] == "skill-lessons"
    content = payload["content"]
    assert content["lesson_type"] == "bug"
    assert content["skill_name"] == "gmail"
    assert content["trigger"] == "script not found"
    assert content["resolution"] == "added $SKILL_GRAPH env var"
    assert content["session_id"] == "dev-agent-skills-test-2026-04-07"
    assert "date" in content


def test_add_lesson_returns_node_id():
    client = _make_client()
    with patch("urllib.request.urlopen", return_value=_mock_urlopen({"id": "lesson-42"})):
        node_id = client.add_lesson("session-start", "broke", "fixed")
    assert node_id == "lesson-42"


def test_add_lesson_patches_crosslinks():
    client = _make_client()
    responses = [
        _mock_urlopen({"id": "lesson-1"}),   # add lesson
        _mock_urlopen({"id": "pattern-99"}),  # patch pattern reverse edge
    ]
    with patch("urllib.request.urlopen", side_effect=responses) as m:
        client.add_lesson(
            "session-start", "broke", "fixed",
            crosslinks=[{"to": "pattern-99", "relation": "caused_by"}]
        )
    assert m.call_count == 2
    patch_req = m.call_args_list[1][0][0]
    patch_payload = json.loads(patch_req.data.decode())
    assert patch_payload["source"] == "skill-patterns"
    assert patch_payload["node_id"] == "pattern-99"


def test_add_lesson_crosslink_patch_failure_is_silent():
    client = _make_client()
    import urllib.error
    responses = [
        _mock_urlopen({"id": "lesson-1"}),
        urllib.error.URLError("patch failed"),
    ]
    with patch("urllib.request.urlopen", side_effect=responses):
        # must not raise even if crosslink patch fails
        node_id = client.add_lesson(
            "session-start", "broke", "fixed",
            crosslinks=[{"to": "pattern-99", "relation": "caused_by"}]
        )
    assert node_id == "lesson-1"
```

- [ ] **Step 3.2: Run to verify failure**

```bash
pytest tests/skill_graph/test_client.py::test_add_lesson_uses_rw_token -v
```

Expected: `NotImplementedError`

- [ ] **Step 3.3: Implement `add_lesson()`**

Replace `raise NotImplementedError` in `add_lesson()`:
```python
def add_lesson(self, skill_name: str, trigger: str, resolution: str,
               lesson_type: str = "bug", session_id: Optional[str] = None,
               eval_score_before: Optional[float] = None,
               eval_score_after: Optional[float] = None,
               crosslinks: Optional[list[dict]] = None) -> str:
    from datetime import datetime, timezone
    content: dict = {
        "lesson_type": lesson_type,
        "skill_name": skill_name,
        "trigger": trigger,
        "resolution": resolution,
        "session_id": session_id or "",
        "date": datetime.now(timezone.utc).isoformat(),
    }
    if eval_score_before is not None:
        content["eval_score_before"] = eval_score_before
    if eval_score_after is not None:
        content["eval_score_after"] = eval_score_after
    if crosslinks:
        content["crosslinks"] = crosslinks

    result = self._post(_ADD_INSIGHT_PATH, {"source": "skill-lessons", "content": content},
                        self._rw_token)
    node_id: str = result.get("id", "")

    # patch reverse edges — eventual consistency, never raises
    if crosslinks and node_id:
        for link in crosslinks:
            try:
                self._post(
                    _ADD_INSIGHT_PATH,
                    {"source": "skill-patterns", "node_id": link["to"],
                     "patch": {"crosslinks": [{"to": node_id, "relation": link["relation"]}]}},
                    self._rw_token,
                )
            except Exception:
                pass

    return node_id
```

- [ ] **Step 3.4: Run all tests**

```bash
pytest tests/skill_graph/test_client.py -v
```

Expected: all PASS

- [ ] **Step 3.5: Commit**

```bash
git add lib/skill_graph/client.py tests/skill_graph/test_client.py
git commit -m "feat(skill-graph): implement add_lesson() with crosslink patch (eventual consistency)"
```

---

## Task 4: `add_pattern()` — write pattern with enum validation

**Files:**
- Modify: `lib/skill_graph/client.py` — implement `add_pattern()`
- Modify: `tests/skill_graph/test_client.py` — add pattern tests

- [ ] **Step 4.1: Write failing tests**

Append to `tests/skill_graph/test_client.py`:
```python
def test_add_pattern_uses_rw_token():
    client = _make_client()
    with patch("urllib.request.urlopen", return_value=_mock_urlopen({"id": "p1"})) as m:
        client.add_pattern("hook", "Inject via PreToolUse", "Always use hooks for data...", "gstack")
    req = m.call_args[0][0]
    assert req.get_header("X-h2t-token") == "rw-tok"


def test_add_pattern_payload_structure():
    client = _make_client()
    with patch("urllib.request.urlopen", return_value=_mock_urlopen({"id": "p1"})) as m:
        client.add_pattern(
            pattern_type="hook",
            title="Inject via PreToolUse",
            body="Always use PreToolUse hooks to inject external data.",
            source="gstack",
            applies_to=["etl-skills", "session-start"],
            confidence=0.9,
            source_url="https://github.com/anthropics/gstack/example",
            tags=["hook", "injection"],
        )
    payload = json.loads(m.call_args[0][0].data.decode())
    assert payload["source"] == "skill-patterns"
    content = payload["content"]
    assert content["pattern_type"] == "hook"
    assert content["confidence"] == 0.9
    assert "etl-skills" in content["applies_to"]
    assert content["source_url"] == "https://github.com/anthropics/gstack/example"


def test_add_pattern_rejects_invalid_type():
    client = _make_client()
    with pytest.raises(ValueError, match="Invalid pattern_type"):
        client.add_pattern("unknown-type", "title", "body", "gstack")


def test_add_pattern_accepts_eval_derived():
    client = _make_client()
    with patch("urllib.request.urlopen", return_value=_mock_urlopen({"id": "p-eval"})):
        node_id = client.add_pattern("eval-derived", "Lesson from GEPA", "body", "gepa-batch")
    assert node_id == "p-eval"


def test_add_pattern_defaults():
    client = _make_client()
    with patch("urllib.request.urlopen", return_value=_mock_urlopen({"id": "p1"})) as m:
        client.add_pattern("etl", "title", "body", "plugin-dev")
    content = json.loads(m.call_args[0][0].data.decode())["content"]
    assert content["confidence"] == 0.7
    assert content["applies_to"] == []
    assert content["tags"] == []
    assert "source_url" not in content
```

- [ ] **Step 4.2: Run to verify failure**

```bash
pytest tests/skill_graph/test_client.py::test_add_pattern_rejects_invalid_type -v
```

Expected: `NotImplementedError`

- [ ] **Step 4.3: Implement `add_pattern()`**

Replace `raise NotImplementedError` in `add_pattern()`:
```python
def add_pattern(self, pattern_type: str, title: str, body: str, source: str,
                applies_to: Optional[list[str]] = None, confidence: float = 0.7,
                source_url: Optional[str] = None,
                tags: Optional[list[str]] = None) -> str:
    if pattern_type not in VALID_PATTERN_TYPES:
        raise ValueError(
            f"Invalid pattern_type: {pattern_type!r}. Must be one of {sorted(VALID_PATTERN_TYPES)}"
        )
    content: dict = {
        "pattern_type": pattern_type,
        "title": title,
        "body": body,
        "source": source,
        "confidence": confidence,
        "applies_to": applies_to or [],
        "tags": tags or [],
    }
    if source_url is not None:
        content["source_url"] = source_url

    result = self._post(_ADD_INSIGHT_PATH, {"source": "skill-patterns", "content": content},
                        self._rw_token)
    return result.get("id", "")
```

- [ ] **Step 4.4: Run all tests**

```bash
pytest tests/skill_graph/test_client.py -v
```

Expected: all PASS

- [ ] **Step 4.5: Commit**

```bash
git add lib/skill_graph/client.py tests/skill_graph/test_client.py
git commit -m "feat(skill-graph): implement add_pattern() with enum validation"
```

---

## Task 5: CLI wrapper

**Files:**
- Create: `lib/skill_graph/cli.py`
- Create: `tests/skill_graph/test_cli.py`

- [ ] **Step 5.1: Write failing tests**

Create `tests/skill_graph/test_cli.py`:
```python
"""Unit tests for skill_graph CLI — mocks SkillGraphClient."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib"))

import json
import pytest
from unittest.mock import patch, MagicMock


def _run_cli(*args):
    """Run CLI with given args, return (stdout, exit_code)."""
    from io import StringIO
    from skill_graph.cli import main
    import contextlib
    out = StringIO()
    code = 0
    try:
        with contextlib.redirect_stdout(out):
            main(list(args))
    except SystemExit as e:
        code = e.code or 0
    return out.getvalue(), code


def test_query_subcommand_prints_results():
    fake_results = [{"id": "p1", "score": 0.9, "title": "Hook pattern", "body": "Use hooks."}]
    with patch("skill_graph.cli.SkillGraphClient") as MockClient:
        MockClient.return_value.query.return_value = fake_results
        out, code = _run_cli("query", "--context", "hook injection")
    assert "Hook pattern" in out
    assert code == 0


def test_query_no_results_says_nothing_found():
    with patch("skill_graph.cli.SkillGraphClient") as MockClient:
        MockClient.return_value.query.return_value = []
        out, code = _run_cli("query", "--context", "unknown topic")
    assert "No results" in out
    assert code == 0


def test_add_lesson_subcommand():
    with patch("skill_graph.cli.SkillGraphClient") as MockClient:
        MockClient.return_value.add_lesson.return_value = "lesson-42"
        out, code = _run_cli(
            "add-lesson",
            "--skill", "session-start",
            "--trigger", "gate was skipped",
            "--resolution", "added GATE block to step 4",
        )
    assert "lesson-42" in out
    assert code == 0
    MockClient.return_value.add_lesson.assert_called_once_with(
        skill_name="session-start",
        trigger="gate was skipped",
        resolution="added GATE block to step 4",
        lesson_type="bug",
        session_id=None,
    )


def test_add_pattern_subcommand():
    with patch("skill_graph.cli.SkillGraphClient") as MockClient:
        MockClient.return_value.add_pattern.return_value = "pat-7"
        out, code = _run_cli(
            "add-pattern",
            "--type", "hook",
            "--title", "PreToolUse injection",
            "--body", "Use PreToolUse to inject data before SKILL.md runs.",
            "--source", "gstack",
        )
    assert "pat-7" in out
    assert code == 0
```

- [ ] **Step 5.2: Run to verify failure**

```bash
pytest tests/skill_graph/test_cli.py -v
```

Expected: `ModuleNotFoundError: No module named 'skill_graph.cli'`

- [ ] **Step 5.3: Implement CLI**

Create `lib/skill_graph/cli.py`:
```python
"""CLI for skill_graph — called from SKILL.md bash steps.

Usage:
    $H2T_PYTHON -m skill_graph.cli query --context "hook injection"
    $H2T_PYTHON -m skill_graph.cli add-lesson --skill session-start --trigger "..." --resolution "..."
    $H2T_PYTHON -m skill_graph.cli add-pattern --type hook --title "..." --body "..." --source gstack
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional

from .client import SkillGraphClient


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skill_graph")
    sub = parser.add_subparsers(dest="command", required=True)

    # query
    q = sub.add_parser("query", help="Semantic search across skill-patterns and skill-lessons")
    q.add_argument("--context", required=True, help="Natural language query")
    q.add_argument("--skill", default=None, help="Skill name (optional filter)")
    q.add_argument("--top-k", type=int, default=5)

    # add-lesson
    al = sub.add_parser("add-lesson", help="Write a lesson learned to skill-lessons")
    al.add_argument("--skill", dest="skill_name", required=True)
    al.add_argument("--trigger", required=True, help="What caused the issue")
    al.add_argument("--resolution", required=True, help="How it was fixed")
    al.add_argument("--type", dest="lesson_type", default="bug",
                    choices=["bug", "anti-pattern", "eval-finding", "regression"])
    al.add_argument("--session-id", default=None)

    # add-pattern
    ap = sub.add_parser("add-pattern", help="Write a best-practice pattern to skill-patterns")
    ap.add_argument("--type", dest="pattern_type", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--confidence", type=float, default=0.7)
    ap.add_argument("--source-url", default=None)

    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    client = SkillGraphClient()

    if args.command == "query":
        results = client.query(args.context, skill_name=args.skill, top_k=args.top_k)
        if not results:
            print("No results found.")
            return
        for r in results:
            title = r.get("title") or r.get("id", "?")
            body = r.get("body", "")
            score = r.get("score", 0.0)
            print(f"[{score:.2f}] {title}")
            if body:
                print(f"  {body[:200]}")
            print()

    elif args.command == "add-lesson":
        node_id = client.add_lesson(
            skill_name=args.skill_name,
            trigger=args.trigger,
            resolution=args.resolution,
            lesson_type=args.lesson_type,
            session_id=args.session_id,
        )
        print(f"Lesson written: {node_id}")

    elif args.command == "add-pattern":
        node_id = client.add_pattern(
            pattern_type=args.pattern_type,
            title=args.title,
            body=args.body,
            source=args.source,
            confidence=args.confidence,
            source_url=args.source_url,
        )
        print(f"Pattern written: {node_id}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5.4: Run all tests**

```bash
pytest tests/skill_graph/ -v
```

Expected: all PASS

- [ ] **Step 5.5: Integration smoke test (requires real tokens)**

```bash
source ~/.dor/secrets.env
H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
$H2T_PYTHON -m skill_graph.cli query --context "hook injection patterns" --top-k 3
```

Expected: prints results or "No results found." — no crash, no auth error.

- [ ] **Step 5.6: Commit**

```bash
git add lib/skill_graph/cli.py tests/skill_graph/test_cli.py
git commit -m "feat(skill-graph): add CLI wrapper for query/add-lesson/add-pattern"
```

---

## Task 6: Patch `SkillEval` — optional skill_graph on failure

**Files:**
- Modify: `lib/eval/session.py` — add `skill_graph` param, call `add_lesson` on failure
- Modify: `lib/eval/test_session.py` — add tests for new behaviour

- [ ] **Step 6.1: Read existing test to understand pattern**

```bash
cat lib/eval/test_session.py
```

Note the existing test conventions before writing new ones.

- [ ] **Step 6.2: Write failing tests**

Append to `lib/eval/test_session.py`:
```python
def test_skill_eval_calls_add_lesson_on_exception():
    from unittest.mock import MagicMock
    from eval.session import SkillEval
    mock_graph = MagicMock()
    mock_graph.add_lesson.return_value = "lesson-1"

    try:
        with SkillEval("session-start", domain="dev", project="test",
                       skill_graph=mock_graph) as ev:
            raise RuntimeError("deliberate failure")
    except RuntimeError:
        pass

    mock_graph.add_lesson.assert_called_once()
    call_kwargs = mock_graph.add_lesson.call_args[1]
    assert call_kwargs["skill_name"] == "session-start"
    assert "deliberate failure" in call_kwargs["trigger"]
    assert call_kwargs["lesson_type"] == "eval-finding"
    assert call_kwargs["resolution"] == ""  # empty — filled later via SKILL.md


def test_skill_eval_does_not_call_add_lesson_on_success():
    from unittest.mock import MagicMock
    from eval.session import SkillEval
    mock_graph = MagicMock()

    with SkillEval("session-start", domain="dev", project="test",
                   skill_graph=mock_graph) as ev:
        ev.metric("test.metric", value_num=1.0)

    mock_graph.add_lesson.assert_not_called()


def test_skill_eval_works_without_skill_graph():
    from eval.session import SkillEval
    # no skill_graph — existing behaviour unchanged
    with SkillEval("session-start", domain="dev", project="test") as ev:
        ev.metric("test.metric", value_num=1.0)
    # passes with no exception
```

- [ ] **Step 6.3: Run to verify failure**

```bash
pytest lib/eval/test_session.py::test_skill_eval_calls_add_lesson_on_exception -v
```

Expected: `TypeError: __init__() got an unexpected keyword argument 'skill_graph'`

- [ ] **Step 6.4: Patch `SkillEval`**

In `lib/eval/session.py`, modify `__init__` and `__exit__`:

```python
# __init__ signature — add skill_graph param:
def __init__(
    self,
    skill: str,
    domain: str,
    project: str,
    plugin_version: str = "",
    evals_root: Optional[str] = None,
    skill_graph=None,   # ← add this; type hint omitted to avoid circular import
) -> None:
    ...
    self._skill_graph = skill_graph
```

```python
# __exit__ — add lesson write on failure:
def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
    status = "failure" if exc_type else "success"
    ended_at = datetime.now(timezone.utc).isoformat()
    self._write_local(status, ended_at)
    if os.environ.get("H2T_EVALS_ENABLED") == "1":
        self._send_central(status)
    if exc_type is not None and self._skill_graph is not None:
        try:
            self._skill_graph.add_lesson(
                skill_name=self.skill,
                trigger=str(exc_val) if exc_val else "skill execution failure",
                resolution="",
                lesson_type="eval-finding",
            )
        except Exception:
            pass  # never crash a skill for graph failure
    return False
```

- [ ] **Step 6.5: Run all eval tests**

```bash
pytest lib/eval/test_session.py -v
```

Expected: all PASS (including pre-existing tests)

- [ ] **Step 6.6: Run full test suite**

```bash
pytest tests/ lib/ -v --tb=short
```

Expected: all PASS

- [ ] **Step 6.7: Commit**

```bash
git add lib/eval/session.py lib/eval/test_session.py
git commit -m "feat(skill-graph): patch SkillEval to write lesson on failure via optional skill_graph param"
```

---

## Self-Review

**Spec coverage:**
- [x] Step 6.0: source bootstrap — Task 0
- [x] lib/skill_graph/client.py — Tasks 1–4
- [x] CLI wrapper — Task 5
- [x] SkillEval patch — Task 6
- [x] Dual-token policy — Task 1 (client init), Tests 2.1, 4.1
- [x] Crosslink typed edges + eventual consistency — Task 3
- [x] `eval-derived` in VALID_PATTERN_TYPES — Task 4 test
- [x] `skill_graph=None` doesn't break existing SkillEval callers — Task 6 test

**Placeholder scan:** None found.

**Type consistency:**
- `SkillGraphClient` → imported in `cli.py` as `from .client import SkillGraphClient` ✓
- `crosslinks: list[dict]` — used consistently in client.py and test ✓
- `_ADD_INSIGHT_PATH`, `_QUERY_PATH` — defined once in client.py, used in all methods ✓
- `VALID_PATTERN_TYPES` — frozenset defined once, used in `add_pattern()` and test ✓

---

## References

- Spec: `docs/superpowers/specs/2026-04-06-skill-intelligence-graph-design.md`
- h2t-graphs API rules: `C:/Users/stani/.h2t/config/rules/graphs-api.md`
- SkillEval: `lib/eval/session.py`
- Existing test pattern: `tests/clients/test_gmail.py`
