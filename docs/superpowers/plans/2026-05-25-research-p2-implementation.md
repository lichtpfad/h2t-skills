# Research P2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add YouTube transcript provider, Exa findSimilar/answer endpoints, author resolution cascade, and visual-ocr auto-capture to the h2t-ops research connector.

**Architecture:** Layered build — h2t-tools packaging (Layer 0) enables visual-ocr auto-capture (Layer 3); Exa extensions and YouTube provider (Layer 1) are independent and enable author resolution (Layer 2). All new providers return envelopes compatible with the existing fetch envelope contract so POS needs no changes.

**Tech Stack:** Python 3.11, `youtube-transcript-api`, `rapidocr-onnxruntime` (already in deps), `playwright` (h2t-tools venv), `urllib` (stdlib), `pytest` + `unittest.mock`.

---

## File Map

| Action | Path |
|--------|------|
| Create | `C:/dev/h2t-tools/pyproject.toml` |
| Create | `C:/dev/h2t-tools/h2t_tools/__init__.py` |
| Move   | `C:/dev/h2t-tools/scripts/screenshot/screenshot.py` → `C:/dev/h2t-tools/h2t_tools/screenshot.py` |
| Modify | `C:/dev/h2t-skills/pyproject.toml` — add `youtube-transcript-api` |
| Modify | `C:/dev/h2t-skills/h2t_ops/connectors/research/exa.py` — add `find_similar()`, `answer()` |
| Create | `C:/dev/h2t-skills/h2t_ops/connectors/research/youtube.py` |
| Modify | `C:/dev/h2t-skills/h2t_ops/connectors/research/fetch.py` — add `_is_youtube_url()` + dispatch |
| Create | `C:/dev/h2t-skills/h2t_ops/connectors/research/author_resolve.py` |
| Modify | `C:/dev/h2t-skills/h2t_ops/connectors/research/visual_ocr.py` — add `capture_and_ocr()` |
| Modify | `C:/dev/h2t-skills/h2t_ops/connectors/research/commands.py` — add `similar`, `answer`, `resolve-author`; extend `visual-ocr` |
| Modify | `C:/dev/h2t-skills/tests/connectors/research/test_exa.py` |
| Create | `C:/dev/h2t-skills/tests/connectors/research/test_youtube.py` |
| Create | `C:/dev/h2t-skills/tests/connectors/research/test_author_resolve.py` |
| Modify | `C:/dev/h2t-skills/tests/connectors/research/test_visual_ocr.py` |

---

## Task 0: h2t-tools — package screenshot as CLI entry point

**Files:**
- Create: `C:/dev/h2t-tools/pyproject.toml`
- Create: `C:/dev/h2t-tools/h2t_tools/__init__.py`
- Move: `C:/dev/h2t-tools/scripts/screenshot/screenshot.py` → `C:/dev/h2t-tools/h2t_tools/screenshot.py`

- [ ] **Step 1: Create the package directory and empty `__init__.py`**

```
C:/dev/h2t-tools/h2t_tools/__init__.py  ← empty file
```

Create it as an empty file.

- [ ] **Step 2: Move the script into the package**

```bash
git -C C:/dev/h2t-tools mv scripts/screenshot/screenshot.py h2t_tools/screenshot.py
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "h2t-tools"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["playwright>=1.44"]

[project.scripts]
h2t-screenshot = "h2t_tools.screenshot:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.setuptools.packages.find]
where = ["."]
include = ["h2t_tools*"]
```

- [ ] **Step 4: Install as editable CLI tool**

```bash
uv tool install --editable C:/dev/h2t-tools
```

Expected: no errors. `h2t-screenshot` should now be on PATH.

- [ ] **Step 5: Verify entry point works**

```bash
h2t-screenshot --help
```

Expected: prints argparse help with `url`, `--format`, `--out` args.

- [ ] **Step 6: Commit in h2t-tools repo**

```bash
git -C C:/dev/h2t-tools add pyproject.toml h2t_tools/
git -C C:/dev/h2t-tools commit -m "feat: package as h2t-screenshot CLI entry point"
```

---

## Task 1: Add `youtube-transcript-api` dependency

**Files:**
- Modify: `C:/dev/h2t-skills/pyproject.toml`

- [ ] **Step 1: Add dependency**

In `C:/dev/h2t-skills/pyproject.toml`, add to the `dependencies` list:

```toml
dependencies = [
  "notion-client>=2.0",
  "httpx>=0.27",
  "python-dotenv>=1.0",
  "google-api-python-client>=2.0",
  "google-auth>=2.0",
  "google-auth-oauthlib>=1.0",
  "tzdata>=2024.1",
  "telethon>=1.36,<1.43",
  "rapidocr-onnxruntime>=1.3.24",
  "youtube-transcript-api>=0.6",
]
```

- [ ] **Step 2: Sync venv**

```bash
uv pip install --python C:/dev/h2t-skills/.venv/Scripts/python.exe youtube-transcript-api
```

Expected: package installs successfully.

- [ ] **Step 3: Verify import**

```bash
C:/dev/h2t-skills/.venv/Scripts/python.exe -c "from youtube_transcript_api import YouTubeTranscriptApi; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git -C C:/dev/h2t-skills add pyproject.toml
git -C C:/dev/h2t-skills commit -m "feat(research): add youtube-transcript-api dependency"
```

---

## Task 2: Exa `find_similar()` + `answer()`

**Files:**
- Modify: `C:/dev/h2t-skills/h2t_ops/connectors/research/exa.py`
- Modify: `C:/dev/h2t-skills/tests/connectors/research/test_exa.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/connectors/research/test_exa.py`:

```python
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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_exa.py::test_find_similar_ok tests/connectors/research/test_exa.py::test_answer_ok -v
```

Expected: `AttributeError: module 'h2t_ops.connectors.research.exa' has no attribute 'find_similar'`

- [ ] **Step 3: Implement `find_similar()` and `answer()` in `exa.py`**

Append to `h2t_ops/connectors/research/exa.py` (before `__all__`):

```python
def find_similar(
    url: str,
    *,
    api_key: str,
    num_results: int = 10,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> tuple[dict[str, Any], int]:
    """Call Exa /findSimilar. Returns (envelope, exit_code)."""
    import time as _time
    body: dict[str, Any] = {
        "url": url,
        "numResults": num_results,
        "contents": {"highlights": {"maxCharacters": 4000}},
    }
    if include_domains:
        body["includeDomains"] = include_domains
    if exclude_domains:
        body["excludeDomains"] = exclude_domains

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        http_status, data, latency = call_exa("/findSimilar", body, api_key)
    except ExaPermanentError as exc:
        exit_code = 4 if exc.http_status in {401, 403} else 1
        return {
            "status": "FAILED",
            "primary_engine": "exa",
            "results": [],
            "telemetry": {
                "attempts": [{"engine": "exa", "endpoint": "/findSimilar", "http": exc.http_status, "latency_ms": exc.latency_ms, "error": "exa_auth_error" if exc.http_status in {401, 403} else "exa_4xx"}],
                "total_latency_ms": exc.latency_ms,
                "total_cost_usd": 0.0,
            },
            "meta": {"source_url": url, "envelope_version": ENVELOPE_VERSION, "timestamp": timestamp},
        }, exit_code
    except (ExaTransientError, ExaMalformedResponseError) as exc:
        latency_ms = getattr(exc, "latency_ms", 0)
        return {
            "status": "FAILED",
            "primary_engine": "exa",
            "results": [],
            "telemetry": {
                "attempts": [{"engine": "exa", "endpoint": "/findSimilar", "http": getattr(exc, "http_status", None), "latency_ms": latency_ms, "error": "exa_network"}],
                "total_latency_ms": latency_ms,
                "total_cost_usd": 0.0,
            },
            "meta": {"source_url": url, "envelope_version": ENVELOPE_VERSION, "timestamp": timestamp},
        }, 6

    results = data.get("results", [])
    cost = float((data.get("costDollars") or {}).get("total", 0.0))
    status = "OK" if results else "DEGRADED"
    return {
        "status": status,
        "primary_engine": "exa",
        "results": results,
        "telemetry": {
            "attempts": [{"engine": "exa", "endpoint": "/findSimilar", "http": http_status, "latency_ms": latency, "error": None}],
            "total_latency_ms": latency,
            "total_cost_usd": cost,
        },
        "meta": {
            "source_url": url,
            "num_results_requested": num_results,
            "num_results_returned": len(results),
            "envelope_version": ENVELOPE_VERSION,
            "timestamp": timestamp,
        },
    }, 0


def answer(
    query: str,
    *,
    api_key: str,
) -> tuple[dict[str, Any], int]:
    """Call Exa /answer. Returns (envelope, exit_code)."""
    body: dict[str, Any] = {"query": query, "text": True}
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        http_status, data, latency = call_exa("/answer", body, api_key)
    except ExaPermanentError as exc:
        exit_code = 4 if exc.http_status in {401, 403} else 1
        return {
            "status": "FAILED",
            "primary_engine": "exa",
            "answer_text": "",
            "citations": [],
            "telemetry": {"attempts": [{"engine": "exa", "endpoint": "/answer", "http": exc.http_status, "latency_ms": exc.latency_ms, "error": "exa_auth_error" if exc.http_status in {401, 403} else "exa_4xx"}], "total_latency_ms": exc.latency_ms, "total_cost_usd": 0.0},
            "meta": {"query": query, "envelope_version": ENVELOPE_VERSION, "timestamp": timestamp},
        }, exit_code
    except (ExaTransientError, ExaMalformedResponseError) as exc:
        latency_ms = getattr(exc, "latency_ms", 0)
        return {
            "status": "FAILED",
            "primary_engine": "exa",
            "answer_text": "",
            "citations": [],
            "telemetry": {"attempts": [{"engine": "exa", "endpoint": "/answer", "http": getattr(exc, "http_status", None), "latency_ms": latency_ms, "error": "exa_network"}], "total_latency_ms": latency_ms, "total_cost_usd": 0.0},
            "meta": {"query": query, "envelope_version": ENVELOPE_VERSION, "timestamp": timestamp},
        }, 6

    answer_text = data.get("answer", "")
    citations = data.get("citations", [])
    return {
        "status": "OK",
        "primary_engine": "exa",
        "answer_text": answer_text,
        "citations": citations,
        "telemetry": {
            "attempts": [{"engine": "exa", "endpoint": "/answer", "http": http_status, "latency_ms": latency, "error": None}],
            "total_latency_ms": latency,
            "total_cost_usd": 0.0,
        },
        "meta": {
            "query": query,
            "envelope_version": ENVELOPE_VERSION,
            "timestamp": timestamp,
        },
    }, 0
```

Also add `find_similar` and `answer` to `__all__` at the bottom of `exa.py`.

- [ ] **Step 4: Run tests — verify they pass**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_exa.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add h2t_ops/connectors/research/exa.py tests/connectors/research/test_exa.py
git -C C:/dev/h2t-skills commit -m "feat(research): add Exa findSimilar and answer endpoints (#182)"
```

---

## Task 3: `similar` and `answer` CLI subcommands

**Files:**
- Modify: `C:/dev/h2t-skills/h2t_ops/connectors/research/commands.py`
- Modify: `C:/dev/h2t-skills/h2t_ops/connectors/research/client.py`

- [ ] **Step 1: Add subparsers in `commands.py`**

In the `register()` function of `commands.py`, after the `visual_ocr` parser block and before `p.set_defaults(_handler=run)`, add:

```python
    similar = cmds.add_parser("similar", help="Find pages similar to a URL using Exa")
    similar.add_argument("--url", required=True, dest="url")
    similar.add_argument("--num-results", type=int, dest="num_results")
    similar.add_argument("--include-domains", dest="include_domains")
    similar.add_argument("--exclude-domains", dest="exclude_domains")
    add_fmt(similar)

    answer_p = cmds.add_parser("answer", help="Get a direct LLM-grounded answer from Exa")
    answer_p.add_argument("--query", required=True)
    add_fmt(answer_p)

    resolve_author = cmds.add_parser("resolve-author", help="Resolve an author name to a channel URL")
    resolve_author.add_argument("--name", required=True)
    resolve_author.add_argument("--keywords", dest="keywords")
    resolve_author.add_argument("--hint", dest="hint")
    add_fmt(resolve_author)
```

- [ ] **Step 2: Add `similar()` and `answer()` to `ResearchClient` in `client.py`**

Find the `ResearchClient` class. Add these methods (follow the same pattern as `search()`):

```python
    def similar(
        self,
        url: str,
        *,
        num_results: int | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> Any:
        from h2t_ops.connectors.research.exa import find_similar
        api_key = resolve_secret("EXA_API_KEY")
        envelope, exit_code = find_similar(
            url,
            api_key=api_key,
            num_results=num_results or 10,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
        )
        return self._emit(envelope, exit_code)

    def answer(self, query: str) -> Any:
        from h2t_ops.connectors.research.exa import answer as _answer
        api_key = resolve_secret("EXA_API_KEY")
        envelope, exit_code = _answer(query, api_key=api_key)
        return self._emit(envelope, exit_code)
```

Note: `_emit` or equivalent output method — use the same method the `search()` method uses to emit results. If none exists, use `return envelope` and set exit code via `sys.exit(exit_code)` following the pattern in other connectors.

- [ ] **Step 3: Wire commands in `run()` function of `commands.py`**

In the `run()` function, add after the `visual-ocr` handler:

```python
    if cmd == "similar":
        return client.similar(
            args.url,
            num_results=args.num_results,
            include_domains=_split_csv(args.include_domains),
            exclude_domains=_split_csv(args.exclude_domains),
        )
    if cmd == "answer":
        return client.answer(args.query)
    if cmd == "resolve-author":
        return client.resolve_author(
            args.name,
            keywords=_split_csv(args.keywords),
            hint=args.hint,
        )
```

- [ ] **Step 4: Smoke test CLI**

```bash
C:/dev/h2t-skills/.venv/Scripts/python.exe -m h2t_ops.cli research similar --help
C:/dev/h2t-skills/.venv/Scripts/python.exe -m h2t_ops.cli research answer --help
```

Expected: both print argparse help without errors.

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add h2t_ops/connectors/research/commands.py h2t_ops/connectors/research/client.py
git -C C:/dev/h2t-skills commit -m "feat(research): add similar and answer CLI subcommands (#182)"
```

---

## Task 4: `youtube.py` — YouTube transcript provider

**Files:**
- Create: `C:/dev/h2t-skills/h2t_ops/connectors/research/youtube.py`
- Create: `C:/dev/h2t-skills/tests/connectors/research/test_youtube.py`

- [ ] **Step 1: Write failing tests**

Create `tests/connectors/research/test_youtube.py`:

```python
"""Tests for the YouTube transcript provider."""
from __future__ import annotations

import json
import urllib.error
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from h2t_ops.connectors.research import youtube


def test_is_youtube_url_watch():
    assert youtube.is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")


def test_is_youtube_url_short():
    assert youtube.is_youtube_url("https://youtu.be/dQw4w9WgXcQ")


def test_is_youtube_url_shorts():
    assert youtube.is_youtube_url("https://youtube.com/shorts/abc123")


def test_is_youtube_url_non_youtube():
    assert not youtube.is_youtube_url("https://derivative.ca/something")
    assert not youtube.is_youtube_url("https://alltd.org/pop-starter-pack/")


def test_extract_video_id_watch():
    vid = youtube._extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert vid == "dQw4w9WgXcQ"


def test_extract_video_id_short():
    vid = youtube._extract_video_id("https://youtu.be/dQw4w9WgXcQ")
    assert vid == "dQw4w9WgXcQ"


def _fake_segment(text: str, start: float = 0.0):
    seg = MagicMock()
    seg.text = text
    seg.start = start
    return seg


def test_fetch_youtube_ok(monkeypatch):
    segments = [_fake_segment("Hello world."), _fake_segment("Second line.", 1.0)]

    mock_api = MagicMock()
    mock_api.fetch.return_value = segments

    def mock_yt_api():
        return mock_api

    # Mock YouTubeTranscriptApi constructor
    monkeypatch.setattr(youtube, "YouTubeTranscriptApi", mock_yt_api)

    # Mock oEmbed
    def mock_oembed(video_id: str) -> dict:
        return {"title": "Test Video", "author_name": "Test Channel"}

    monkeypatch.setattr(youtube, "_get_oembed", mock_oembed)

    envelope, exit_code = youtube.fetch_youtube(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        output_dir=None,
        project="test",
    )

    assert exit_code == 0
    assert envelope["status"] == "OK"
    assert envelope["provider_used"] == "youtube_transcript"
    assert "Hello world." in envelope["body_text"]
    assert "Second line." in envelope["body_text"]
    assert envelope["provenance"]["video_id"] == "dQw4w9WgXcQ"
    assert envelope["provenance"]["title"] == "Test Video"
    assert envelope["provenance"]["author_name"] == "Test Channel"
    assert envelope["provenance"]["transcript_segments"] == 2


def test_fetch_youtube_no_transcript(monkeypatch):
    mock_api = MagicMock()
    mock_api.fetch.side_effect = Exception("No transcripts available")

    monkeypatch.setattr(youtube, "YouTubeTranscriptApi", lambda: mock_api)
    monkeypatch.setattr(youtube, "_get_oembed", lambda vid: {})

    envelope, exit_code = youtube.fetch_youtube(
        "https://www.youtube.com/watch?v=NOFOUND123",
        output_dir=None,
        project="test",
    )

    assert exit_code == 1
    assert envelope["status"] == "FAILED"
    assert envelope["provider_used"] == "youtube_transcript"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_youtube.py -v
```

Expected: `ModuleNotFoundError: No module named 'h2t_ops.connectors.research.youtube'`

- [ ] **Step 3: Create `youtube.py`**

Create `h2t_ops/connectors/research/youtube.py`:

```python
"""YouTube transcript provider for the h2t-ops research fetch ladder."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi

ENVELOPE_VERSION = "1"


def is_youtube_url(url: str) -> bool:
    """Return True if url points to a YouTube video."""
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().lstrip("www.")
    return hostname in ("youtube.com", "youtu.be")


def _extract_video_id(url: str) -> str:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().lstrip("www.")
    if hostname == "youtu.be":
        return parsed.path.lstrip("/").split("?")[0]
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "shorts":
        return parts[1]
    raise ValueError(f"Cannot extract video_id from URL: {url}")


def _get_oembed(video_id: str) -> dict[str, Any]:
    oembed_url = (
        f"https://www.youtube.com/oembed"
        f"?url=https://www.youtube.com/watch?v={video_id}&format=json"
    )
    req = urllib.request.Request(
        oembed_url,
        headers={"User-Agent": "h2t-ops/research (youtube provider)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}


def _get_transcript(api: Any, video_id: str) -> tuple[list[Any], str]:
    """Return (segments, language_code). Priority: ru → en → any."""
    for lang in ("ru", "en"):
        try:
            segs = list(api.fetch(video_id, languages=[lang]))
            return segs, lang
        except Exception:
            continue
    # Fallback: any available
    segs = list(api.fetch(video_id))
    return segs, "unknown"


def fetch_youtube(
    url: str,
    *,
    output_dir: Path | None = None,
    project: str = "default",
) -> tuple[dict[str, Any], int]:
    """Fetch YouTube transcript and return a fetch-ladder-compatible envelope."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    t0 = time.monotonic()

    try:
        video_id = _extract_video_id(url)
    except ValueError as exc:
        return {
            "status": "FAILED",
            "provider_used": "youtube_transcript",
            "body_text": "",
            "body_chars": 0,
            "provenance": {"text_source": "youtube_transcript", "error": str(exc)},
            "telemetry": {"error": str(exc), "total_latency_ms": 0},
            "meta": {"envelope_version": ENVELOPE_VERSION, "timestamp": timestamp},
        }, 2

    meta = _get_oembed(video_id)

    try:
        api = YouTubeTranscriptApi()
        segments, language = _get_transcript(api, video_id)
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {
            "status": "FAILED",
            "provider_used": "youtube_transcript",
            "body_text": "",
            "body_chars": 0,
            "provenance": {
                "text_source": "youtube_transcript",
                "video_id": video_id,
                "author_name": meta.get("author_name", ""),
                "title": meta.get("title", ""),
                "error": str(exc),
            },
            "telemetry": {"error": str(exc), "total_latency_ms": latency_ms},
            "meta": {"envelope_version": ENVELOPE_VERSION, "timestamp": timestamp},
        }, 1

    body_text = " ".join(seg.text for seg in segments).strip()
    latency_ms = int((time.monotonic() - t0) * 1000)

    return {
        "status": "OK",
        "url": url,
        "final_url": url,
        "provider_used": "youtube_transcript",
        "content_type": "transcript",
        "content_gate": "none",
        "title": meta.get("title", ""),
        "body_markdown": body_text,
        "body_text": body_text,
        "body_chars": len(body_text),
        "links": [],
        "provenance": {
            "text_source": "youtube_transcript",
            "video_id": video_id,
            "author_name": meta.get("author_name", ""),
            "title": meta.get("title", ""),
            "language": language,
            "transcript_segments": len(segments),
        },
        "telemetry": {
            "attempts": [{"engine": "youtube_transcript", "latency_ms": latency_ms, "error": None}],
            "total_latency_ms": latency_ms,
        },
        "meta": {
            "primary_engine": "youtube_transcript",
            "envelope_version": ENVELOPE_VERSION,
            "timestamp": timestamp,
        },
    }, 0
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_youtube.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add h2t_ops/connectors/research/youtube.py tests/connectors/research/test_youtube.py
git -C C:/dev/h2t-skills commit -m "feat(research): add YouTube transcript provider"
```

---

## Task 5: URL dispatch table in `fetch.py`

**Files:**
- Modify: `C:/dev/h2t-skills/h2t_ops/connectors/research/fetch.py`
- Modify: `C:/dev/h2t-skills/tests/connectors/research/test_fetch.py`

- [ ] **Step 1: Write failing test**

Append to `tests/connectors/research/test_fetch.py`:

```python
def test_fetch_via_ladder_routes_youtube(monkeypatch):
    """YouTube URLs must bypass the HTTP ladder and use the YouTube provider."""
    called_with = {}

    def fake_fetch_youtube(url, *, output_dir, project, **kw):
        called_with["url"] = url
        called_with["project"] = project
        return {"status": "OK", "provider_used": "youtube_transcript", "body_text": "transcript"}, 0

    monkeypatch.setattr(fetch, "_fetch_youtube_provider", fake_fetch_youtube)

    cfg = fetch.load_config(None)
    envelope = fetch.fetch_via_ladder(
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        provider_choice="auto",
        config=cfg,
        user_agent="test",
        keep_raw=False,
        output_paths=None,
    )

    assert envelope["provider_used"] == "youtube_transcript"
    assert called_with["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

- [ ] **Step 2: Run test — verify it fails**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_fetch.py::test_fetch_via_ladder_routes_youtube -v
```

Expected: `AttributeError: module ... has no attribute '_fetch_youtube_provider'`

- [ ] **Step 3: Add dispatch to `fetch.py`**

Near the top of `fetch.py` (after imports), add a helper:

```python
def _is_youtube_url(url: str) -> bool:
    """Return True if url is a YouTube video URL."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().lstrip("www.")
    return hostname in ("youtube.com", "youtu.be")


def _fetch_youtube_provider(url: str, *, output_dir: Any, project: str, **_kw: Any) -> tuple[dict[str, Any], int]:
    """Lazy import wrapper — avoids circular imports."""
    from h2t_ops.connectors.research.youtube import fetch_youtube
    return fetch_youtube(url, output_dir=output_dir, project=project)
```

At the top of `fetch_via_ladder()` (right after the `min_body_chars` resolution block, before `order` is built), insert:

```python
    # URL-type dispatch: route to specialized providers before the HTTP ladder
    if _is_youtube_url(url):
        envelope_dict, _exit = _fetch_youtube_provider(
            url,
            output_dir=output_paths and output_paths.get("artifact_json", Path(".")).parent,
            project="default",
        )
        return envelope_dict
```

Note: `fetch_via_ladder` returns `dict[str, Any]` (not a tuple), so return `envelope_dict` directly.

- [ ] **Step 4: Run tests — verify they pass**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_fetch.py -v
```

Expected: all tests PASS including the new YouTube dispatch test.

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills add h2t_ops/connectors/research/fetch.py tests/connectors/research/test_fetch.py
git -C C:/dev/h2t-skills commit -m "feat(research): add URL dispatch table with YouTube provider routing"
```

---

## Task 6: `author_resolve.py`

**Files:**
- Create: `C:/dev/h2t-skills/h2t_ops/connectors/research/author_resolve.py`
- Create: `C:/dev/h2t-skills/tests/connectors/research/test_author_resolve.py`

- [ ] **Step 1: Write failing tests**

Create `tests/connectors/research/test_author_resolve.py`:

```python
"""Tests for author_resolve — no network."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from h2t_ops.connectors.research import author_resolve


def test_resolve_via_handle_guess(monkeypatch):
    """If oEmbed confirms a handle guess, return confidence=confirmed."""
    def fake_oembed(video_id: str) -> dict:
        if "Acidbourbon" in video_id or "acidbourbon" in video_id:
            return {"author_name": "Acidbourbon", "title": "TD Tutorial"}
        return {}

    monkeypatch.setattr(author_resolve, "_oembed_channel_validate", fake_oembed)
    monkeypatch.setattr(
        author_resolve,
        "_exa_people_search",
        lambda name, keywords, api_key: None,
    )
    monkeypatch.setattr(
        author_resolve,
        "_alltd_uploader_check",
        lambda name: None,
    )

    result = author_resolve.resolve_author(
        "Acidbourbon",
        api_key="test-key",
        keywords=["TouchDesigner", "POP"],
    )

    assert result["confidence"] == "confirmed"
    assert result["channel_url"] is not None
    assert "Acidbourbon" in result["channel_url"] or "acidbourbon" in result["channel_url"]
    assert any("handle_guess" in step for step in result["resolution_path"])


def test_resolve_via_exa(monkeypatch):
    """If Exa people search returns a channel URL, use it."""
    monkeypatch.setattr(
        author_resolve,
        "_exa_people_search",
        lambda name, keywords, api_key: "https://youtube.com/@testchannel",
    )
    monkeypatch.setattr(author_resolve, "_oembed_channel_validate", lambda vid: {})
    monkeypatch.setattr(author_resolve, "_alltd_uploader_check", lambda name: None)

    result = author_resolve.resolve_author(
        "TestChannel",
        api_key="test-key",
    )

    assert result["confidence"] == "confirmed"
    assert result["channel_url"] == "https://youtube.com/@testchannel"
    assert any("exa_people" in step for step in result["resolution_path"])


def test_resolve_not_found(monkeypatch):
    """Not found is exit 0 with confidence=not_found, not an error."""
    monkeypatch.setattr(author_resolve, "_exa_people_search", lambda *a, **kw: None)
    monkeypatch.setattr(author_resolve, "_oembed_channel_validate", lambda vid: {})
    monkeypatch.setattr(author_resolve, "_alltd_uploader_check", lambda name: None)

    result = author_resolve.resolve_author("GhostAuthor99", api_key="k")

    assert result["confidence"] == "not_found"
    assert result["channel_url"] is None
    assert result["name"] == "GhostAuthor99"


def test_resolve_result_schema(monkeypatch):
    """Result always contains required keys."""
    monkeypatch.setattr(author_resolve, "_exa_people_search", lambda *a, **kw: None)
    monkeypatch.setattr(author_resolve, "_oembed_channel_validate", lambda vid: {})
    monkeypatch.setattr(author_resolve, "_alltd_uploader_check", lambda name: None)

    result = author_resolve.resolve_author("X", api_key="k")

    for key in ("name", "channel_url", "author_confirmed", "resolution_path", "confidence"):
        assert key in result, f"missing key: {key}"


def test_resolve_exa_provider_error_returns_error_confidence(monkeypatch):
    """ProviderError/AuthError from Exa returns confidence=error, not not_found."""
    from h2t_ops.core.errors import ProviderError

    def raise_provider_error(name, keywords, api_key):
        raise ProviderError("Exa API unavailable", details={})

    monkeypatch.setattr(author_resolve, "_exa_people_search", raise_provider_error)

    result = author_resolve.resolve_author("AnyAuthor", api_key="k")

    assert result["confidence"] == "error"
    assert "provider error" in result["resolution_path"][0]
    assert result["channel_url"] is None
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_author_resolve.py -v
```

Expected: `ModuleNotFoundError: No module named 'h2t_ops.connectors.research.author_resolve'`

- [ ] **Step 3: Create `author_resolve.py`**

Create `h2t_ops/connectors/research/author_resolve.py`:

```python
"""Author/channel resolution cascade for research workflows.

Resolution order:
  1. Exa people search — extract YouTube URLs from results
  2. Handle guesses + YouTube oEmbed validation
  3. AllTD uploader page check
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any


_YOUTUBE_URL_RE = re.compile(
    r"https?://(?:www\.)?youtube\.com/@?[\w.-]+|https?://youtu\.be/[\w.-]+"
)


def _exa_people_search(
    name: str,
    keywords: list[str] | None,
    api_key: str,
) -> str | None:
    """Search Exa people mode. Return first YouTube URL found, or None."""
    from h2t_ops.connectors.research.exa import call_exa

    kw_str = " ".join(keywords) if keywords else ""
    query = f"{name} {kw_str} YouTube".strip()
    body = {
        "query": query,
        "type": "auto",
        "category": "people",
        "numResults": 5,
        "contents": {"highlights": {"maxCharacters": 2000}},
    }
    from h2t_ops.core.errors import AuthError, NetworkError, ProviderError as _ProviderError
    try:
        _status, data, _latency = call_exa("/search", body, api_key)
    except (AuthError, NetworkError, _ProviderError):
        raise  # Propagate typed errors — callers must distinguish from not_found
    except Exception:
        return None

    for result in data.get("results", []):
        url = result.get("url", "")
        if "youtube.com" in url or "youtu.be" in url:
            return url
        for hl in (result.get("highlights") or []):
            m = _YOUTUBE_URL_RE.search(hl)
            if m:
                return m.group(0)
    return None


def _oembed_channel_validate(handle: str) -> dict[str, Any]:
    """Try YouTube oEmbed for a channel handle. Returns {} on failure."""
    # oEmbed works with video URLs; use channel URL as a search hint via direct probe
    probe_url = f"https://www.youtube.com/@{handle}"
    req = urllib.request.Request(
        f"https://www.youtube.com/oembed?url={probe_url}&format=json",
        headers={"User-Agent": "h2t-ops/research"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}


def _alltd_uploader_check(name: str) -> str | None:
    """Check if alltd.org/uploader/<handle>/ exists. Returns URL if found, else None."""
    handle = name.lower().replace(" ", "")
    url = f"https://alltd.org/uploader/{handle}/"
    req = urllib.request.Request(url, headers={"User-Agent": "h2t-ops/research"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return url
    except Exception:
        pass
    return None


def resolve_author(
    name: str,
    *,
    api_key: str,
    hint: str | None = None,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Resolve an author name to a channel URL using a cascade strategy.

    Returns a dict with keys: name, channel_url, author_confirmed,
    resolution_path, confidence.

    confidence: "confirmed" | "likely" | "not_found"
    Exit 0 in all cases — not_found is an honest result, not an error.
    """
    resolution_path: list[str] = []

    from h2t_ops.core.errors import AuthError, NetworkError, ProviderError as _ProviderError
    # Step 1: Exa people search
    try:
        exa_url = _exa_people_search(name, keywords, api_key)
    except (AuthError, NetworkError, _ProviderError) as exc:
        return {
            "name": name,
            "channel_url": None,
            "author_confirmed": None,
            "resolution_path": [f"exa_people: provider error — {type(exc).__name__}: {exc}"],
            "confidence": "error",
        }
    if exa_url:
        resolution_path.append(f"exa_people: found {exa_url}")
        return {
            "name": name,
            "channel_url": exa_url,
            "author_confirmed": name,
            "resolution_path": resolution_path,
            "confidence": "confirmed",
        }
    resolution_path.append("exa_people: no YouTube URL in results")

    # Step 2: Handle guesses + oEmbed
    handle_candidates = [name, name.lower(), name.replace(" ", ""), name.replace(" ", "").lower()]
    for handle in dict.fromkeys(handle_candidates):  # deduplicate preserving order
        meta = _oembed_channel_validate(handle)
        if meta.get("author_name"):
            channel_url = f"https://youtube.com/@{handle}"
            resolution_path.append(f"handle_guess @{handle}: oembed confirmed ({meta['author_name']})")
            return {
                "name": name,
                "channel_url": channel_url,
                "author_confirmed": meta["author_name"],
                "resolution_path": resolution_path,
                "confidence": "confirmed",
            }
        resolution_path.append(f"handle_guess @{handle}: oembed not confirmed")

    # Step 3: AllTD uploader page
    alltd_url = _alltd_uploader_check(name)
    if alltd_url:
        resolution_path.append(f"alltd_uploader: found {alltd_url}")
        return {
            "name": name,
            "channel_url": alltd_url,
            "author_confirmed": None,
            "resolution_path": resolution_path,
            "confidence": "likely",
        }
    resolution_path.append("alltd_uploader: not found")

    resolution_path.append("all_strategies: not_found")
    return {
        "name": name,
        "channel_url": None,
        "author_confirmed": None,
        "resolution_path": resolution_path,
        "confidence": "not_found",
    }
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_author_resolve.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Add `resolve_author` to `ResearchClient` in `client.py`**

Add method to `ResearchClient`:

```python
    def resolve_author(
        self,
        name: str,
        *,
        keywords: list[str] | None = None,
        hint: str | None = None,
    ) -> Any:
        from h2t_ops.connectors.research.author_resolve import resolve_author as _resolve
        api_key = resolve_secret("EXA_API_KEY")
        result = _resolve(name, api_key=api_key, keywords=keywords, hint=hint)
        exit_code = 1 if result.get("confidence") == "error" else 0
        return self._emit(result, exit_code)
```

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills add h2t_ops/connectors/research/author_resolve.py tests/connectors/research/test_author_resolve.py h2t_ops/connectors/research/client.py
git -C C:/dev/h2t-skills commit -m "feat(research): add author resolution cascade (#99)"
```

---

## Task 7: `capture_and_ocr()` + `visual-ocr --url` mode

**Files:**
- Modify: `C:/dev/h2t-skills/h2t_ops/connectors/research/visual_ocr.py`
- Modify: `C:/dev/h2t-skills/tests/connectors/research/test_visual_ocr.py`
- Modify: `C:/dev/h2t-skills/h2t_ops/connectors/research/commands.py`

- [ ] **Step 1: Write failing test for `capture_and_ocr`**

Append to `tests/connectors/research/test_visual_ocr.py`:

```python
def test_capture_and_ocr_ok(monkeypatch, tmp_path):
    """capture_and_ocr calls h2t-screenshot, copies screenshot to stable path, runs OCR."""
    import shutil as _shutil
    import subprocess
    from unittest.mock import patch as _patch

    monkeypatch.setattr(_shutil, "which", lambda cmd: "/usr/bin/h2t-screenshot")

    fake_image = tmp_path / "tmp_screenshot" / "test.png"
    fake_image.parent.mkdir()
    fake_image.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    fake_stdout = f"→ https://example.com\n  ✓ desktop: {fake_image}\n"

    fake_run_result = MagicMock()
    fake_run_result.returncode = 0
    fake_run_result.stdout = fake_stdout
    fake_run_result.stderr = ""

    output_dir = tmp_path / "artifacts"
    with _patch("subprocess.run", return_value=fake_run_result):
        with _patch.object(
            visual_ocr,
            "extract_text_from_image",
            return_value=("Recovered text from page", ["Heading One"], "medium"),
        ):
            envelope, exit_code = visual_ocr.capture_and_ocr(
                "https://example.com",
                output_dir=output_dir,
                project="test",
            )

    assert exit_code == 0
    assert envelope["status"] == "OK"
    assert envelope["provider_used"] == "visual_ocr"
    assert "Recovered text" in envelope["body_text_visual_ocr"]
    assert envelope["needs_review"] is True
    assert envelope["quote_safe"] is False
    # Stable image must exist in output_dir (not in a deleted temp dir)
    stable_image = Path(envelope["provenance"]["image_path"])
    assert stable_image.is_file(), "screenshot must be copied to output_dir, not left in tmp"
    assert str(output_dir) in str(stable_image)


def test_capture_and_ocr_rejects_file_url(tmp_path):
    """UsageError for file:// URLs — SSRF guard."""
    from h2t_ops.core.errors import UsageError
    with pytest.raises(UsageError):
        visual_ocr.capture_and_ocr(
            "file:///etc/passwd", output_dir=tmp_path, project="test"
        )


def test_capture_and_ocr_rejects_localhost(tmp_path):
    """UsageError for localhost URLs — SSRF guard."""
    from h2t_ops.core.errors import UsageError
    with pytest.raises(UsageError):
        visual_ocr.capture_and_ocr(
            "http://localhost:8080/admin", output_dir=tmp_path, project="test"
        )


def test_capture_and_ocr_rejects_private_ip(tmp_path):
    """UsageError for private IP ranges — SSRF guard."""
    from h2t_ops.core.errors import UsageError
    with pytest.raises(UsageError):
        visual_ocr.capture_and_ocr(
            "http://192.168.1.1/", output_dir=tmp_path, project="test"
        )


def test_capture_and_ocr_screenshot_not_on_path(monkeypatch, tmp_path):
    """ConfigError when h2t-screenshot is not installed."""
    import shutil as _shutil
    monkeypatch.setattr(_shutil, "which", lambda cmd: None)

    from h2t_ops.core.errors import ConfigError
    with pytest.raises(ConfigError) as ei:
        visual_ocr.capture_and_ocr(
            "https://example.com", output_dir=tmp_path, project="test"
        )

    assert "h2t-screenshot" in str(ei.value)


def test_capture_and_ocr_screenshot_fails(monkeypatch, tmp_path):
    """ProviderError when h2t-screenshot returns non-zero."""
    import shutil as _shutil
    import subprocess
    from unittest.mock import patch as _patch

    monkeypatch.setattr(_shutil, "which", lambda cmd: "/usr/bin/h2t-screenshot")

    fake_result = MagicMock()
    fake_result.returncode = 1
    fake_result.stdout = ""
    fake_result.stderr = "browser launch failed"

    with _patch("subprocess.run", return_value=fake_result):
        from h2t_ops.core.errors import ProviderError
        with pytest.raises(ProviderError):
            visual_ocr.capture_and_ocr(
                "https://example.com", output_dir=tmp_path, project="test"
            )
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_visual_ocr.py::test_capture_and_ocr_ok -v
```

Expected: `AttributeError: module ... has no attribute 'capture_and_ocr'`

- [ ] **Step 3: Add `capture_and_ocr()` and `_parse_screenshot_path()` to `visual_ocr.py`**

Append to `h2t_ops/connectors/research/visual_ocr.py`:

```python
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone


def _parse_screenshot_path(stdout: str) -> str | None:
    """Extract the desktop image path from h2t-screenshot stdout."""
    for line in stdout.splitlines():
        stripped = line.strip()
        if "✓ desktop:" in stripped:
            return stripped.split("✓ desktop:", 1)[1].strip()
    return None


def capture_and_ocr(
    url: str,
    *,
    output_dir: Path,
    project: str,
) -> tuple[dict, int]:
    """Auto-capture a screenshot of url and run OCR. No sidecar required."""
    from h2t_ops.connectors.research.client import validate_public_http_url
    validate_public_http_url(url)  # SSRF guard: reject file://, localhost, private IPs, credentials

    if not shutil.which("h2t-screenshot"):
        raise ConfigError(
            "h2t-screenshot not found on PATH",
            hint="Install with: uv tool install --editable C:/dev/h2t-tools",
        )

    # Build stable artifact paths before temp dir — screenshot persists here
    artifact_paths = build_visual_ocr_artifact_paths(
        output_dir=Path(output_dir),
        project=project,
        slug_source=url,
    )
    artifact_paths["sources_json"].parent.mkdir(parents=True, exist_ok=True)
    stable_image = artifact_paths["sources_json"].with_suffix(".capture.png")

    with tempfile.TemporaryDirectory() as tmp_dir:
        result = subprocess.run(
            ["h2t-screenshot", url, "--format", "desktop", "--out", tmp_dir],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise ProviderError(
                f"h2t-screenshot failed for {url}",
                details={"returncode": result.returncode, "stderr": result.stderr[:300]},
            )

        image_path_str = _parse_screenshot_path(result.stdout)
        if not image_path_str or not Path(image_path_str).is_file():
            raise ProviderError(
                "h2t-screenshot did not produce a desktop image file",
                details={"stdout": result.stdout[:300]},
            )

        # Copy to stable location before TemporaryDirectory is deleted
        shutil.copy2(image_path_str, stable_image)

    # Temp dir deleted — use stable_image for OCR and provenance
    extracted_text, visible_headings, confidence = extract_text_from_image(stable_image)
    captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    envelope = build_visual_ocr_envelope(
        url=url,
        source_fetch_status="unknown",
        source_fetch_reason=None,
        captured_at=captured_at,
        image_path=str(stable_image),
        extracted_text=extracted_text,
        visible_headings=visible_headings,
        ocr_confidence=confidence,
    )
    envelope["provenance"]["capture_method"] = "auto_screenshot"
    envelope["provenance"]["capture_tool"] = "h2t-screenshot"

    import json as _json
    sidecar = {"envelope": envelope, "meta": {"status": envelope["status"]}}
    artifact_paths["sources_json"].write_text(
        _json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    exit_code = 0 if envelope["status"] in ("OK", "DEGRADED") else 1
    return envelope, exit_code
```

Note: `ConfigError` and `ProviderError` are already imported at the top of `visual_ocr.py`.

- [ ] **Step 4: Run tests — verify they pass**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/test_visual_ocr.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Add `--url` mode to `visual-ocr` in `commands.py`**

In `commands.py`, find the `visual_ocr` subparser block and update it:

```python
    visual_ocr = cmds.add_parser(
        "visual-ocr",
        help="Create a review-required OCR rescue artifact",
    )
    # Manual mode (existing)
    visual_ocr.add_argument("--fetch-sidecar", dest="fetch_sidecar")
    visual_ocr.add_argument("--image-path", dest="image_path")
    # Auto-capture mode (new)
    visual_ocr.add_argument("--url", dest="visual_ocr_url")
    visual_ocr.add_argument("--project", default="default")
    visual_ocr.add_argument("--output-dir", dest="output_dir")
    add_fmt(visual_ocr)
```

In `run()`, update the `visual-ocr` handler:

```python
    if cmd == "visual-ocr":
        if getattr(args, "visual_ocr_url", None):
            return client.visual_ocr_auto(
                args.visual_ocr_url,
                project=args.project,
            )
        return client.visual_ocr(
            fetch_sidecar=args.fetch_sidecar,
            image_path=args.image_path,
            project=args.project,
        )
```

Add `visual_ocr_auto()` to `ResearchClient` in `client.py`:

```python
    def visual_ocr_auto(self, url: str, *, project: str = "default") -> Any:
        from h2t_ops.connectors.research.visual_ocr import capture_and_ocr
        output_dir = self.output_dir or (Path.home() / ".h2t" / "research")
        envelope, exit_code = capture_and_ocr(url, output_dir=output_dir, project=project)
        return self._emit(envelope, exit_code)
```

- [ ] **Step 6: Smoke test CLI**

```bash
C:/dev/h2t-skills/.venv/Scripts/python.exe -m h2t_ops.cli research visual-ocr --help
```

Expected: shows both `--url` and `--fetch-sidecar` options.

- [ ] **Step 7: Commit**

```bash
git -C C:/dev/h2t-skills add h2t_ops/connectors/research/visual_ocr.py tests/connectors/research/test_visual_ocr.py h2t_ops/connectors/research/commands.py h2t_ops/connectors/research/client.py
git -C C:/dev/h2t-skills commit -m "feat(research): add visual-ocr --url auto-capture mode (#105)"
```

---

## Task 8: Full test suite + smoke verification

- [ ] **Step 1: Run full research test suite**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/connectors/research/ -v
```

Expected: all tests PASS, no regressions.

- [ ] **Step 2: Run full suite**

```bash
C:/dev/h2t-skills/.venv/Scripts/pytest tests/ -v --tb=short
```

Expected: all tests PASS.

- [ ] **Step 3: Smoke — Exa similar** (requires `EXA_API_KEY` in env)

```bash
uv run --directory C:/dev/h2t-skills h2t-ops research similar --url https://derivative.ca --json
```

Expected: JSON envelope with `status: OK` and `results` array.

- [ ] **Step 4: Smoke — Exa answer** (requires `EXA_API_KEY`)

```bash
uv run --directory C:/dev/h2t-skills h2t-ops research answer --query "TouchDesigner POP particle basics" --json
```

Expected: JSON envelope with `status: OK` and `answer_text` field.

- [ ] **Step 5: Smoke — YouTube fetch** (requires network)

```bash
uv run --directory C:/dev/h2t-skills h2t-ops research fetch --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --json
```

Expected: `provider_used: youtube_transcript`, `body_text` contains transcript.

- [ ] **Step 6: Smoke — visual-ocr --url** (requires h2t-screenshot)

```bash
uv run --directory C:/dev/h2t-skills h2t-ops research visual-ocr --url "https://alltd.org/pop-starter-pack-touchdesigner/" --json
```

Expected: JSON envelope with `needs_review: true` and `body_text_visual_ocr` containing recovered text.

- [ ] **Step 7: Smoke — resolve-author** (requires `EXA_API_KEY`)

```bash
uv run --directory C:/dev/h2t-skills h2t-ops research resolve-author --name "Accentfold" --keywords "TouchDesigner" --json
```

Expected: JSON with `confidence` field (`confirmed`, `likely`, or `not_found`) and `resolution_path` array.

- [ ] **Step 8: Final commit — close issues**

```bash
git -C C:/dev/h2t-skills commit --allow-empty -m "chore(research): Research P2 complete — closes #182, #99, #105"
```

---

## Self-Review Checklist

- [x] Task 0 covers h2t-tools packaging (Layer 0 prereq)
- [x] Task 1 covers youtube-transcript-api dep
- [x] Tasks 2–3 cover Exa findSimilar + answer (#182)
- [x] Tasks 4–5 cover YouTube provider + dispatch (#Layer 1B)
- [x] Task 6 covers author_resolve + resolve-author command (#99)
- [x] Task 7 covers capture_and_ocr + visual-ocr --url (#105)
- [x] Task 8 covers smoke tests for all five new commands
- [x] All test steps include complete test function code
- [x] All implementation steps include complete function code
- [x] No TBDs or placeholders
- [x] Method names are consistent across tasks (`capture_and_ocr`, `visual_ocr_auto`, `resolve_author`)
- [x] `resolve-author` subparser is added in Task 3 (commands.py) and wired in run()
