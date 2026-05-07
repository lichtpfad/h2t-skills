# Research Fetch URL Provider Ladder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать `fetch_url.py` — provider ladder CLI (direct + jina active, остальные stubs), envelope-compatible с merged #100, zero new pip deps, baseline tests зелёные на чистом `~/.h2t/venv`.

**Architecture:** Single-file CLI под `plugins/h2t-ops/skills/research/scripts/fetch_url.py`. Класс-провайдеры (`DirectProvider`, `JinaProvider`, four stubs) с общим интерфейсом. `ProviderLadder` координирует попытки, собирает telemetry, применяет cumulative timeout. `_inline_extract` (stdlib `html.parser`) — обязательный baseline; `trafilatura` — опциональный uplift через lazy import. Sidecar writers `.partial.md` / `.sources.json` / `.raw.html`. Public API экспортируется для адаптеров #105/#104.

**Tech Stack:** Python 3.11 stdlib (`urllib`, `html.parser`, `json`, `argparse`, `pathlib`, `dataclasses`, `time`, `random`), pytest, `unittest.mock`. Нет новых pip deps. `trafilatura` — opt-in, не required.

**Spec:** `docs/superpowers/specs/2026-05-07-research-fetch-url-ladder.md`
**Issue:** lichtpfad/h2t-skills#103
**Parent ladder:** lichtpfad/h2t-skills#98
**Related merged PR:** lichtpfad/h2t-skills#106 (envelope core)

---

## File Structure

| Path | Type | Responsibility |
|---|---|---|
| `plugins/h2t-ops/skills/research/scripts/fetch_url.py` | create | Single-file CLI: providers, ladder, classifier, envelope, CLI |
| `plugins/h2t-ops/skills/research/tests/test_fetch_url.py` | create | pytest module — 33 baseline + 1 optional |
| `plugins/h2t-ops/skills/research/tests/fixtures/fetch/public_article.html` | create | OK fixture |
| `plugins/h2t-ops/skills/research/tests/fixtures/fetch/public_article_jina.md` | create | Jina mock response |
| `plugins/h2t-ops/skills/research/tests/fixtures/fetch/js_shell.html` | create | js_shell fixture |
| `plugins/h2t-ops/skills/research/tests/fixtures/fetch/short_body.html` | create | short_body fixture |
| `plugins/h2t-ops/skills/research/tests/fixtures/fetch/login_wall.html` | create | login_required fixture |
| `plugins/h2t-ops/skills/research/tests/fixtures/fetch/paywall.html` | create | paid fixture |
| `plugins/h2t-ops/skills/research/tests/fixtures/fetch/alltd_403_body.html` | create | Cloudflare-style 403 fixture (NOT gated) |
| `plugins/h2t-ops/skills/research/tests/fixtures/fetch/redirect_to_login.html` | create | meta-refresh login fixture |
| `plugins/h2t-ops/skills/research/tests/fixtures/fetch/non_ascii_article.html` | create | UTF-8 fixture |
| `plugins/h2t-ops/skills/research/SKILL.md` | modify | Add "Fetching Specific URLs" section, antipatterns, version bump 0.1.1→0.1.2 |
| `plugins/h2t-ops/skills/research/reference.md` | modify | Append fetch envelope schema |
| `plugins/h2t-ops/.claude-plugin/plugin.json` | modify | 1.1.1 → 1.1.2 |

**Worktree:** `C:/dev/h2t-skills-fetch-ladder`. Branch `feature/research-fetch-url-ladder`. **Never** touch `C:/dev/h2t-skills` main worktree (it has unrelated dirty files).

**Shell environment:** Windows. PowerShell default; Bash tool available. CLAUDE.md prohibits venv activation — use direct paths:

- Python: `C:/Users/stani/.h2t/venv/Scripts/python.exe`
- Pytest: `C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest`
- Test file: `plugins/h2t-ops/skills/research/tests/test_fetch_url.py`

For pattern matching prefer the **Grep tool** over `grep`/`Select-String` in shell.

**Frequent commits:** один логический task = один commit. Conventional Commits scope `(research)`. Stage only listed files explicitly — **never** `git add .` / `git add -A`.

**Trafilatura policy:** PR#1 baseline — без trafilatura. Тесты, помеченные `@pytest.mark.optional`, проверяют uplift и могут пропускаться.

**Stub providers:** Playwright/Crawl4AI/Firecrawl/Browserless — все идентичные stubs, raise `ProviderNotConfigured`. Нет реальных HTTP-клиентов в PR#1.

---

## Pre-flight

Before Task 1, verify environment:

- [ ] **Pre-0: Mark worktree as a safe directory for git**

Worktree paths created from another shell are flagged by Git as `dubious ownership` until added to `safe.directory`, which makes ALL `git -C C:/dev/h2t-skills-fetch-ladder ...` commands fail with `fatal: detected dubious ownership in repository at ...`. Run **once** per machine:

```bash
git config --global --add safe.directory C:/dev/h2t-skills-fetch-ladder
```

Idempotent: `--add` does not create a duplicate if the entry already exists. After this, every other `git -C` command in the plan works.

- [ ] **Pre-1: Verify worktree**

```bash
git -C C:/dev/h2t-skills-fetch-ladder status -sb
```

Expected:
```
## feature/research-fetch-url-ladder...origin/main [ahead 2]
```

(Allowed ahead commits: `85f86d6` spec + `6c72717` plan = 2.)

- [ ] **Pre-2: Verify Python**

Run: `C:/Users/stani/.h2t/venv/Scripts/python.exe --version`
Expected: `Python 3.11.9` (или 3.11.x)

- [ ] **Pre-3: Verify pytest installed**

Run: `C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest --version`
Expected: `pytest 7.x` или `8.x`

- [ ] **Pre-4: Verify trafilatura is NOT installed (baseline policy)**

Run: `C:/Users/stani/.h2t/venv/Scripts/python.exe -c "import trafilatura"`
Expected: `ModuleNotFoundError: No module named 'trafilatura'`

If installed — skip; baseline tests должны пройти и с ним. Просто проверьте отдельно task 28 (uplift) после.

- [ ] **Pre-5: Confirm no `fetch_url.py` exists yet**

Run: `ls plugins/h2t-ops/skills/research/scripts/fetch_url.py 2>&1`
Expected: file not found.

---

## Task 1: Bootstrap module + first failing test

**Files:**
- Create: `plugins/h2t-ops/skills/research/scripts/fetch_url.py`
- Create: `plugins/h2t-ops/skills/research/tests/test_fetch_url.py`

- [ ] **Step 1: Write failing import test**

Create `plugins/h2t-ops/skills/research/tests/test_fetch_url.py`:

```python
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
```

- [ ] **Step 2: Run test, expect FAIL (no module)**

Run: `C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t-ops/skills/research/tests/test_fetch_url.py -v`
Expected: `ModuleNotFoundError: No module named 'fetch_url'`

- [ ] **Step 3: Create skeleton module**

Create `plugins/h2t-ops/skills/research/scripts/fetch_url.py`:

```python
#!/usr/bin/env python3
"""fetch_url.py — provider ladder CLI for h2t-ops:research skill.

Spec: docs/superpowers/specs/2026-05-07-research-fetch-url-ladder.md
Issue: lichtpfad/h2t-skills#103
"""
from __future__ import annotations

__version__ = "0.0.1"
```

- [ ] **Step 4: Run test, expect PASS**

Run: `C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t-ops/skills/research/tests/test_fetch_url.py -v`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): bootstrap fetch_url.py module"
```

---

## Task 2: ENVELOPE_VERSION + build_fetch_envelope

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/fetch_url.py` (append)
- Modify: `plugins/h2t-ops/skills/research/tests/test_fetch_url.py` (append)

- [ ] **Step 1: Write failing test**

Append to `tests/test_fetch_url.py`:

```python
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
```

- [ ] **Step 2: Run, expect FAIL** (`AttributeError: module 'fetch_url' has no attribute 'build_fetch_envelope'`)

- [ ] **Step 3: Implement**

Append to `fetch_url.py`:

```python
from datetime import datetime, timezone
from typing import Any

ENVELOPE_VERSION = "1"
FETCH_ENVELOPE_VERSION = "1"
PRIMARY_ENGINE = "fetch_ladder"


def build_fetch_envelope(
    *,
    status: str,
    url: str,
    final_url: str | None,
    provider_used: str,
    content_type: str,
    content_gate: str,
    title: str | None,
    body_markdown: str,
    body_text: str,
    body_chars: int,
    links: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    providers_skipped: dict[str, str],
    reason_for_failed: str | None,
    reason_for_degraded: str | None,
    raw_html_path: str | None,
    site: str | None,
    canonical_url: str | None,
    lang: str | None,
    detected_reason: str | None,
    user_agent: str,
) -> dict[str, Any]:
    """Assemble the fetch envelope per spec §4.1."""
    total_latency_ms = sum(a.get("latency_ms", 0) for a in attempts)
    return {
        "status": status,
        "url": url,
        "final_url": final_url,
        "provider_used": provider_used,
        "content_type": content_type,
        "content_gate": content_gate,
        "title": title,
        "body_markdown": body_markdown,
        "body_text": body_text,
        "body_chars": body_chars,
        "links": links,
        "metadata": {
            "canonical_url": canonical_url,
            "site": site,
            "lang": lang,
            "detected_reason": detected_reason,
            "site_adapter": None,
            "raw_html_path": raw_html_path,
        },
        "telemetry": {
            "attempts": attempts,
            "reason_for_degraded": reason_for_degraded,
            "reason_for_failed": reason_for_failed,
            "total_latency_ms": total_latency_ms,
            "providers_skipped": sorted(providers_skipped.keys()),
            "providers_skipped_reason": dict(providers_skipped),
        },
        "meta": {
            "primary_engine": PRIMARY_ENGINE,
            "envelope_version": ENVELOPE_VERSION,
            "fetch_envelope_version": FETCH_ENVELOPE_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "user_agent": user_agent,
        },
    }
```

- [ ] **Step 4: Run, expect PASS** (3 tests total)

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): build_fetch_envelope + version constants"
```

---

## Task 3: Provider exception classes + ProviderResult dataclass

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Failing test**

```python
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
```

- [ ] **Step 2: Run, FAIL** (`AttributeError`)

- [ ] **Step 3: Implement**

Append to `fetch_url.py`:

```python
from dataclasses import dataclass, field


class ProviderTransientError(Exception):
    """Retryable across providers: 5xx, 429, network timeout, URLError."""

    def __init__(self, message: str, *, provider: str, http_status: int | None,
                 latency_ms: int):
        super().__init__(message)
        self.provider = provider
        self.http_status = http_status
        self.latency_ms = latency_ms


class ProviderPermanentError(Exception):
    """Non-retryable for THIS provider; ladder may try next: 4xx, malformed."""

    def __init__(self, message: str, *, provider: str, http_status: int | None,
                 latency_ms: int):
        super().__init__(message)
        self.provider = provider
        self.http_status = http_status
        self.latency_ms = latency_ms


class ProviderHardGate(Exception):
    """Bypass forbidden — ladder STOPS, does not try further providers."""

    def __init__(self, message: str, *, provider: str, gate: str, latency_ms: int,
                 http_status: int | None = None):
        super().__init__(message)
        self.provider = provider
        self.gate = gate  # login_required | paid
        self.http_status = http_status
        self.latency_ms = latency_ms


class ProviderNotConfigured(Exception):
    """Provider exists but not enabled. Ladder skips silently."""

    def __init__(self, message: str, *, provider: str):
        super().__init__(message)
        self.provider = provider


@dataclass
class ProviderResult:
    provider: str
    http_status: int | None
    latency_ms: int
    final_url: str | None
    title: str | None
    body_markdown: str
    body_text: str
    body_chars: int
    links: list[dict[str, Any]]
    canonical_url: str | None
    lang: str | None
    raw_html: str | None
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): provider exception classes and ProviderResult"
```

---

## Task 4: Inline HTML extraction (baseline, no trafilatura)

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`
- Create: `tests/fixtures/fetch/public_article.html`

- [ ] **Step 1: Create fixture**

Create `plugins/h2t-ops/skills/research/tests/fixtures/fetch/public_article.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <title>POPs in TouchDesigner — Introduction</title>
  <link rel="canonical" href="https://example.com/pops-intro">
  <meta charset="utf-8">
</head>
<body>
  <header><nav><a href="/">Home</a></nav></header>
  <article>
    <h1>POPs in TouchDesigner — Introduction</h1>
    <p>POPs are the new particle context in TouchDesigner. They replace the
    legacy SOP-based particle workflow with a GPU-driven pipeline.</p>
    <p>This article covers the fundamentals: attributes, cooking, and feedback.
    POPs introduce attribute-lifecycle as a first-class concept, similar to
    Houdini's geometry context but adapted for real-time GPU evaluation.</p>
    <h2>Attribute lifecycle</h2>
    <p>Every attribute has a creation, modification, and consumption phase.
    Understanding this order is critical for predictable network behaviour.</p>
    <p><a href="/glsl-pops">Continue to GLSL POPs</a> for the next lesson.</p>
  </article>
  <footer><script src="/static/app.js"></script></footer>
</body>
</html>
```

- [ ] **Step 2: Failing test**

Add to `tests/test_fetch_url.py`:

```python
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
```

- [ ] **Step 3: Run, FAIL** (`AttributeError: '_inline_extract'`)

- [ ] **Step 4: Implement inline extractor**

Append to `fetch_url.py`:

```python
from html.parser import HTMLParser
from urllib.parse import urljoin


class _InlineExtractor(HTMLParser):
    """Minimal stdlib HTML extractor.

    Strategy:
    - Drop content inside <script>, <style>, <noscript>, <head>, <nav>,
      <header>, <footer>, <aside>, <form>.
    - Prefer body inside <article> if present; else <main>; else everything.
    - Emit a stream of (kind, text) tokens that the caller turns into
      markdown + plain text.
    """

    SKIP_TAGS = {"script", "style", "noscript", "nav", "header", "footer",
                 "aside", "form", "iframe"}
    BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br",
                  "div", "tr", "blockquote", "pre"}
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_article = False
        self._has_article = False
        self.title: str | None = None
        self._in_title = False
        self._capture_outside_article = True
        self._tokens: list[tuple[str, str]] = []
        self._current_text: list[str] = []
        self._current_link: dict[str, Any] | None = None
        self.links: list[dict[str, Any]] = []
        self.canonical_url: str | None = None
        self.lang: str | None = None
        self._in_head = False

    # ---- helpers ----

    def _emit_block(self, tag: str) -> None:
        if not self._current_text:
            return
        text = "".join(self._current_text).strip()
        self._current_text = []
        if not text:
            return
        kind = "h" + tag[1] if tag in self.HEADING_TAGS else "p"
        self._tokens.append((kind, text))

    def _capturing(self) -> bool:
        if self._skip_depth > 0:
            return False
        if self._has_article:
            return self._in_article
        return self._capture_outside_article

    # ---- parser hooks ----

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang") or self.lang
            return
        if tag == "head":
            self._in_head = True
            return
        if tag == "title" and self._in_head:
            self._in_title = True
            return
        if tag == "link" and self._in_head and a.get("rel") == "canonical":
            self.canonical_url = a.get("href")
            return
        if tag == "article":
            self._has_article = True
            self._in_article = True
            return
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if not self._capturing():
            return
        if tag in self.BLOCK_TAGS or tag in self.HEADING_TAGS:
            self._emit_block(tag)
            self._pending_block = tag
        if tag == "a":
            href = a.get("href") or ""
            self._current_link = {"href": href, "text": ""}

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self._in_head = False
            return
        if tag == "title":
            self._in_title = False
            return
        if tag == "article":
            self._in_article = False
            self._emit_block("p")
            return
        if tag in self.SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if not self._capturing():
            return
        if tag == "a" and self._current_link is not None:
            text = self._current_link["text"].strip()
            href = self._current_link["href"]
            if href:
                self.links.append({"href": href, "text": text, "rel": ""})
            self._current_link = None
        if tag in self.BLOCK_TAGS or tag in self.HEADING_TAGS:
            block_kind = getattr(self, "_pending_block", "p")
            self._emit_block(block_kind)

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title = (self.title or "") + data
            return
        if not self._capturing():
            return
        if self._current_link is not None:
            self._current_link["text"] += data
        self._current_text.append(data)

    def finish(self) -> None:
        self._emit_block("p")
        if self.title is not None:
            self.title = self.title.strip()


def _tokens_to_markdown_and_text(tokens: list[tuple[str, str]]) -> tuple[str, str]:
    md_lines: list[str] = []
    text_lines: list[str] = []
    for kind, text in tokens:
        if kind.startswith("h"):
            level = int(kind[1])
            md_lines.append(f"{'#' * level} {text}")
        else:
            md_lines.append(text)
        text_lines.append(text)
        md_lines.append("")
        text_lines.append("")
    md = "\n".join(md_lines).strip()
    txt = "\n".join(text_lines).strip()
    return md, txt


def _inline_extract(
    html: str, *, base_url: str,
) -> tuple[str | None, str, str, list[dict[str, Any]], str | None, str | None]:
    """Return (title, body_markdown, body_text, links, canonical_url, lang)."""
    p = _InlineExtractor()
    p.feed(html)
    p.finish()
    md, txt = _tokens_to_markdown_and_text(p._tokens)
    # Resolve relative hrefs.
    for link in p.links:
        if link["href"]:
            link["href"] = urljoin(base_url, link["href"])
    return p.title, md, txt, p.links, p.canonical_url, p.lang
```

- [ ] **Step 5: Run, expect PASS**

If your implementation is missing edge cases revealed by the assertions, fix iteratively until green. The fixture is the spec.

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py plugins/h2t-ops/skills/research/tests/fixtures/fetch/public_article.html
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): inline HTML extractor (stdlib baseline)"
```

---

## Task 5: DirectProvider — happy path

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Failing test**

```python
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
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

Append to `fetch_url.py`:

```python
import time

DEFAULT_USER_AGENT = (
    "h2t-research-fetch/0.0.1 (+https://github.com/lichtpfad/h2t-skills)"
)


def _site_from_url(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).hostname or ""


class DirectProvider:
    """stdlib urllib.request fetcher with inline extraction."""

    name = "direct"

    def is_configured(self, env: dict[str, str], config: dict[str, Any]) -> bool:
        # Direct is always available.
        return True

    def fetch(self, url: str, *, timeout_ms: int, user_agent: str) -> ProviderResult:
        req = urllib.request.Request(url, headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en,*;q=0.5",
        })
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout_ms / 1000) as resp:
                raw_bytes = resp.read()
                final_url = resp.geturl() or url
                resp_headers = dict(resp.headers.items()) if hasattr(resp.headers, "items") else dict(resp.headers)
                http_status = getattr(resp, "status", 200)
        except urllib.error.HTTPError as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            self._raise_http_error(e, url=url, latency_ms=latency_ms)
            raise  # unreachable
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            raise ProviderTransientError(
                f"network: {e}", provider=self.name,
                http_status=None, latency_ms=latency_ms,
            )
        latency_ms = int((time.monotonic() - t0) * 1000)
        # 2xx path:
        encoding = _detect_encoding(resp_headers, raw_bytes)
        html_text = raw_bytes.decode(encoding, errors="replace")
        title, md, txt, links, canonical, lang = _inline_extract(
            html_text, base_url=final_url,
        )
        return ProviderResult(
            provider=self.name,
            http_status=http_status,
            latency_ms=latency_ms,
            final_url=final_url,
            title=title,
            body_markdown=md,
            body_text=txt,
            body_chars=len(txt),
            links=links,
            canonical_url=canonical,
            lang=lang,
            raw_html=html_text,
        )

    def _raise_http_error(self, e: urllib.error.HTTPError, *, url: str,
                          latency_ms: int) -> None:
        # Filled in next tasks. For now: any HTTP error → permanent.
        raise ProviderPermanentError(
            f"http {e.code}", provider=self.name,
            http_status=e.code, latency_ms=latency_ms,
        )


def _detect_encoding(headers: dict[str, str], body: bytes) -> str:
    ct = headers.get("Content-Type", "") or headers.get("content-type", "")
    if "charset=" in ct.lower():
        return ct.lower().split("charset=", 1)[1].split(";")[0].strip() or "utf-8"
    return "utf-8"
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): DirectProvider happy path"
```

---

## Task 6: DirectProvider — HTTP 4xx/5xx classification

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Failing tests**

```python
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
```

- [ ] **Step 2: FAIL** (tests for 5xx and 429 fail — current `_raise_http_error` always raises Permanent)

- [ ] **Step 3: Update `_raise_http_error` in DirectProvider**

```python
    def _raise_http_error(self, e: urllib.error.HTTPError, *, url: str,
                          latency_ms: int) -> None:
        code = e.code
        if code == 429 or 500 <= code <= 599:
            raise ProviderTransientError(
                f"http {code}", provider=self.name,
                http_status=code, latency_ms=latency_ms,
            )
        # 4xx — caller (Task 8) refines for auth-gated cases.
        raise ProviderPermanentError(
            f"http {code}", provider=self.name,
            http_status=code, latency_ms=latency_ms,
        )
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): DirectProvider 4xx/5xx/429 classification"
```

---

## Task 7: DirectProvider — URLError → Transient (already covered, add explicit test)

**Files:**
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Add test (no impl change expected)**

```python
def test_direct_provider_urlerror_raises_transient():
    p = fetch_url.DirectProvider()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        with pytest.raises(fetch_url.ProviderTransientError) as ei:
            p.fetch("https://example.com/x", timeout_ms=15000, user_agent="ua/test")
    assert ei.value.http_status is None
    assert ei.value.latency_ms >= 0
```

- [ ] **Step 2: Run — should already PASS thanks to existing URLError catch in Task 5**

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "test(research): assert DirectProvider URLError is transient"
```

---

## Task 8: DirectProvider — 401 with WWW-Authenticate → HardGate

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Failing tests**

```python
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
```

- [ ] **Step 2: First test FAILs (currently 401 raises Permanent)**

- [ ] **Step 3: Update `_raise_http_error`**

```python
    def _raise_http_error(self, e: urllib.error.HTTPError, *, url: str,
                          latency_ms: int) -> None:
        code = e.code
        # Auth-gated: 401 with WWW-Authenticate, OR 403 with explicit auth signal.
        hdrs = {}
        try:
            if hasattr(e, "headers") and e.headers is not None:
                hdrs = {k.lower(): v for k, v in e.headers.items()}
        except Exception:
            hdrs = {}
        if code == 401 and "www-authenticate" in hdrs:
            raise ProviderHardGate(
                "auth required", provider=self.name,
                gate="login_required", http_status=code, latency_ms=latency_ms,
            )
        if code == 429 or 500 <= code <= 599:
            raise ProviderTransientError(
                f"http {code}", provider=self.name,
                http_status=code, latency_ms=latency_ms,
            )
        raise ProviderPermanentError(
            f"http {code}", provider=self.name,
            http_status=code, latency_ms=latency_ms,
        )
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): DirectProvider 401 with WWW-Authenticate → HardGate"
```

---

## Task 9: DirectProvider — final_url from redirects

**Files:**
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Test redirect tracking**

```python
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
```

- [ ] **Step 2: Run — should PASS** (`final_url` already populated from `resp.geturl()` in Task 5)

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "test(research): DirectProvider tracks final_url through redirects"
```

---

## Task 10: Content classifier — js_shell detection

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`
- Create: `tests/fixtures/fetch/js_shell.html`

- [ ] **Step 1: Create fixture**

`tests/fixtures/fetch/js_shell.html`:

```html
<!DOCTYPE html>
<html><head><title>App</title></head>
<body>
  <div id="root"></div>
  <script src="/static/runtime.js"></script>
  <script src="/static/vendor.js"></script>
  <script src="/static/main.js"></script>
  <script src="/static/polyfill.js"></script>
  <script src="/static/analytics.js"></script>
  <script src="/static/auth.js"></script>
</body></html>
```

- [ ] **Step 2: Failing test**

```python
def test_detect_js_shell_true_for_spa_skeleton():
    html = _load_fixture("js_shell.html")
    body_text = ""  # inline_extract would yield empty
    assert fetch_url._detect_js_shell(html=html, body_text=body_text) is True


def test_detect_js_shell_false_for_real_article():
    html = _load_fixture("public_article.html")
    _, _, body_text, _, _, _ = fetch_url._inline_extract(html, base_url="x")
    assert fetch_url._detect_js_shell(html=html, body_text=body_text) is False
```

- [ ] **Step 3: FAIL**

- [ ] **Step 4: Implement**

Append:

```python
import re

_SCRIPT_TAG_RE = re.compile(r"<script\b[^>]*>", re.IGNORECASE)


def _detect_js_shell(*, html: str, body_text: str) -> bool:
    """Heuristic: SPA skeleton — short body + many script tags."""
    if len(body_text) >= 200:
        return False
    return len(_SCRIPT_TAG_RE.findall(html)) >= 5
```

- [ ] **Step 5: PASS**

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py plugins/h2t-ops/skills/research/tests/fixtures/fetch/js_shell.html
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): JS-shell heuristic"
```

---

## Task 11: Content classifier — login wall detection

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`
- Create: `tests/fixtures/fetch/login_wall.html`
- Create: `tests/fixtures/fetch/redirect_to_login.html`

- [ ] **Step 1: Create fixtures**

`login_wall.html`:

```html
<!DOCTYPE html>
<html><head><title>Sign in</title></head>
<body>
  <h1>Sign in</h1>
  <form action="/login" method="post" id="login-form">
    <input name="username" type="text" required>
    <input name="password" type="password" required>
    <button type="submit">Log in</button>
  </form>
</body></html>
```

`redirect_to_login.html`:

```html
<!DOCTYPE html>
<html><head>
  <meta http-equiv="refresh" content="0; URL=/login?next=/article/x">
  <title>Redirecting</title>
</head><body>Redirecting…</body></html>
```

- [ ] **Step 2: Failing tests**

```python
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
```

- [ ] **Step 3: FAIL**

- [ ] **Step 4: Implement**

```python
LOGIN_DOM_TOKENS = (
    'class="login-required"',
    'data-auth="required"',
    'id="login-form"',
)

_LOGIN_FORM_ACTION_RE = re.compile(
    r'<form\b[^>]*action=["\'](/(?:login|signin|auth)[^"\']*)["\']',
    re.IGNORECASE,
)
_META_REFRESH_LOGIN_RE = re.compile(
    r'<meta\b[^>]*http-equiv=["\']refresh["\'][^>]*url=([^"\'>\s]+)',
    re.IGNORECASE,
)


def _detect_login_wall(*, html: str, final_url: str) -> bool:
    if any(tok in html for tok in LOGIN_DOM_TOKENS):
        return True
    if _LOGIN_FORM_ACTION_RE.search(html):
        return True
    m = _META_REFRESH_LOGIN_RE.search(html)
    if m:
        target = m.group(1).lower()
        if "/login" in target or "/signin" in target or "/auth" in target:
            return True
    if final_url:
        path = final_url.lower()
        if "/login" in path or "/signin" in path:
            return True
    return False
```

- [ ] **Step 5: PASS**

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py plugins/h2t-ops/skills/research/tests/fixtures/fetch/login_wall.html plugins/h2t-ops/skills/research/tests/fixtures/fetch/redirect_to_login.html
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): login-wall detection"
```

---

## Task 12: Content classifier — paywall + classify_content_type

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`
- Create: `tests/fixtures/fetch/paywall.html`
- Create: `tests/fixtures/fetch/short_body.html`
- Create: `tests/fixtures/fetch/alltd_403_body.html`

- [ ] **Step 1: Create fixtures**

`paywall.html`:

```html
<!DOCTYPE html>
<html><head><title>Premium article</title></head>
<body>
  <article class="paywall-active" data-paid="true">
    <h1>Premium article</h1>
    <p>This story is for subscribers only.</p>
    <div itemtype="https://schema.org/Paywall"></div>
  </article>
</body></html>
```

`short_body.html`:

```html
<!DOCTYPE html>
<html lang="en"><head><title>Short</title></head>
<body><article><h1>Short</h1><p>Hi.</p></article></body></html>
```

`alltd_403_body.html`:

```html
<!DOCTYPE html>
<html><head><title>403 Forbidden</title></head>
<body>
  <h1>Cloudflare 403</h1>
  <p>Access denied. Please contact the site owner.</p>
</body></html>
```

- [ ] **Step 2: Failing tests**

```python
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
```

- [ ] **Step 3: FAIL**

- [ ] **Step 4: Implement**

```python
PAYWALL_DOM_TOKENS = (
    'data-paid="true"',
    'class="paywall-active"',
    'class="article-paywall"',
    'itemtype="https://schema.org/Paywall"',
)

KNOWN_PAYWALLED_DOMAINS: set[str] = set()  # populated in follow-up


def _detect_paywall(*, html: str, site: str) -> bool:
    if site and site.lower() in KNOWN_PAYWALLED_DOMAINS:
        return True
    return any(tok in html for tok in PAYWALL_DOM_TOKENS)


def _classify_content(
    *, html: str, body_text: str, final_url: str, site: str,
    min_body_chars: int,
) -> tuple[str, str]:
    """Return (content_type, content_gate)."""
    if _detect_login_wall(html=html, final_url=final_url):
        return "gated", "login_required"
    if _detect_paywall(html=html, site=site):
        return "gated", "paid"
    if _detect_js_shell(html=html, body_text=body_text):
        return "js_shell", "none"
    if len(body_text) < min_body_chars:
        return "short_body", "none"
    # Listing heuristic: many <li><a> relative to text — punt for PR#1.
    return "article", "none"
```

- [ ] **Step 5: PASS**

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py plugins/h2t-ops/skills/research/tests/fixtures/fetch/paywall.html plugins/h2t-ops/skills/research/tests/fixtures/fetch/short_body.html plugins/h2t-ops/skills/research/tests/fixtures/fetch/alltd_403_body.html
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): paywall detection + classify_content"
```

---

## Task 13: DirectProvider — convert HardGate via classifier

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

After Task 8, DirectProvider raises HardGate only on HTTP 401+WWW-Authenticate. We also need to convert HTTP 200 + login-form-content into HardGate (otherwise login_wall.html would be returned as OK ProviderResult).

- [ ] **Step 1: Failing test**

```python
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
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement — extend DirectProvider.fetch after extraction**

Replace the body of the 2xx path in `DirectProvider.fetch` (after extraction) with:

```python
        latency_ms = int((time.monotonic() - t0) * 1000)
        encoding = _detect_encoding(resp_headers, raw_bytes)
        html_text = raw_bytes.decode(encoding, errors="replace")
        title, md, txt, links, canonical, lang = _inline_extract(
            html_text, base_url=final_url,
        )
        site = _site_from_url(final_url)
        # Hard-gate short-circuit on the basis of body content (200 + gated DOM):
        if _detect_login_wall(html=html_text, final_url=final_url):
            raise ProviderHardGate(
                "login wall in body", provider=self.name,
                gate="login_required", http_status=http_status, latency_ms=latency_ms,
            )
        if _detect_paywall(html=html_text, site=site):
            raise ProviderHardGate(
                "paywall in body", provider=self.name,
                gate="paid", http_status=http_status, latency_ms=latency_ms,
            )
        return ProviderResult(
            provider=self.name,
            http_status=http_status,
            latency_ms=latency_ms,
            final_url=final_url,
            title=title,
            body_markdown=md,
            body_text=txt,
            body_chars=len(txt),
            links=links,
            canonical_url=canonical,
            lang=lang,
            raw_html=html_text,
        )
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): DirectProvider classifier-driven HardGate on 200 body"
```

---

## Task 14: JinaProvider — happy path

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`
- Create: `tests/fixtures/fetch/public_article_jina.md`

- [ ] **Step 1: Create fixture**

`public_article_jina.md`:

```markdown
Title: POPs in TouchDesigner — Introduction

URL Source: https://example.com/pops-intro

Markdown Content:
# POPs in TouchDesigner — Introduction

POPs are the new particle context in TouchDesigner. They replace the legacy
SOP-based particle workflow with a GPU-driven pipeline.

## Attribute lifecycle

Every attribute has a creation, modification, and consumption phase.
```

- [ ] **Step 2: Failing tests**

```python
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
```

- [ ] **Step 3: FAIL** (`JinaProvider` undefined)

- [ ] **Step 4: Implement**

```python
JINA_ENDPOINT_DEFAULT = "https://r.jina.ai/"


class JinaProvider:
    """Fetch via Jina Reader URL-to-markdown relay."""

    name = "jina"

    def is_configured(self, env: dict[str, str], config: dict[str, Any]) -> bool:
        cfg = (config.get("providers") or {}).get(self.name) or {}
        return bool(cfg.get("enabled", True))

    def fetch(self, url: str, *, timeout_ms: int, user_agent: str) -> ProviderResult:
        endpoint = JINA_ENDPOINT_DEFAULT.rstrip("/") + "/"
        target = endpoint + url
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/markdown",
            "X-Return-Format": "markdown",
        }
        api_key = os.environ.get("JINA_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = urllib.request.Request(target, headers=headers)
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout_ms / 1000) as resp:
                raw = resp.read()
                final_url = resp.geturl() or target
                http_status = getattr(resp, "status", 200)
        except urllib.error.HTTPError as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            self._raise_http_error(e, latency_ms=latency_ms)
            raise  # unreachable
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            raise ProviderTransientError(
                f"network: {e}", provider=self.name,
                http_status=None, latency_ms=latency_ms,
            )
        latency_ms = int((time.monotonic() - t0) * 1000)
        markdown_text = raw.decode("utf-8", errors="replace")
        title = _jina_extract_title(markdown_text)
        body_md = _jina_extract_body(markdown_text)
        body_text = body_md  # markdown ≈ text for Jina output
        return ProviderResult(
            provider=self.name,
            http_status=http_status,
            latency_ms=latency_ms,
            final_url=url,  # logical URL, not the relay
            title=title,
            body_markdown=body_md,
            body_text=body_text,
            body_chars=len(body_text),
            links=[],
            canonical_url=None,
            lang=None,
            raw_html=markdown_text,  # Jina returns markdown; keep for --keep-raw
        )

    def _raise_http_error(self, e: urllib.error.HTTPError, *,
                          latency_ms: int) -> None:
        code = e.code
        if code == 429 or 500 <= code <= 599:
            raise ProviderTransientError(
                f"http {code}", provider=self.name,
                http_status=code, latency_ms=latency_ms,
            )
        raise ProviderPermanentError(
            f"http {code}", provider=self.name,
            http_status=code, latency_ms=latency_ms,
        )


def _jina_extract_title(md: str) -> str | None:
    for line in md.splitlines():
        s = line.strip()
        if s.lower().startswith("title:"):
            return s.split(":", 1)[1].strip()
        if s.startswith("# "):
            return s[2:].strip()
    return None


def _jina_extract_body(md: str) -> str:
    """Drop the Jina header block ('Title:', 'URL Source:', empty lines) and
    return the actual content after 'Markdown Content:' marker."""
    lines = md.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("markdown content:"):
            return "\n".join(lines[i + 1:]).strip()
    # No marker — return the whole thing.
    return md.strip()
```

- [ ] **Step 5: PASS**

- [ ] **Step 6: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py plugins/h2t-ops/skills/research/tests/fixtures/fetch/public_article_jina.md
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): JinaProvider with optional bearer auth"
```

---

## Task 15: JinaProvider — error classification

**Files:**
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Add tests**

```python
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
```

- [ ] **Step 2: Run — should PASS** (impl from Task 14 already covers these)

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "test(research): JinaProvider error classification"
```

---

## Task 16: Stub providers (Playwright/Crawl4AI/Firecrawl/Browserless)

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Failing test**

```python
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
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

```python
class _StubProvider:
    name = "stub"

    def is_configured(self, env: dict[str, str], config: dict[str, Any]) -> bool:
        return False

    def fetch(self, url: str, *, timeout_ms: int, user_agent: str) -> ProviderResult:
        raise ProviderNotConfigured(
            f"{self.name} stub: implementation deferred to follow-up PR.",
            provider=self.name,
        )


class PlaywrightProvider(_StubProvider):
    name = "playwright"


class Crawl4AIProvider(_StubProvider):
    name = "crawl4ai"


class FirecrawlProvider(_StubProvider):
    name = "firecrawl"


class BrowserlessProvider(_StubProvider):
    name = "browserless"
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): stub providers (playwright/crawl4ai/firecrawl/browserless)"
```

---

## Task 17: Config loader (JSON only in PR#1)

Spec §7.1 illustrates YAML; PR#1 uses JSON to keep zero new pip deps. Spec amendment is folded into Task 47 documentation update.

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Failing test**

```python
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
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

```python
DEFAULT_CONFIG: dict[str, Any] = {
    "providers": {
        "direct": {"enabled": True, "user_agent": DEFAULT_USER_AGENT,
                   "timeout_ms": 15000},
        "jina": {"enabled": True, "endpoint": JINA_ENDPOINT_DEFAULT,
                 "timeout_ms": 20000},
        "playwright": {"enabled": False, "timeout_ms": 30000},
        "crawl4ai": {"enabled": False},
        "firecrawl": {"enabled": False},
        "browserless": {"enabled": False},
    },
    "ladder": {
        "default_order": ["direct", "jina", "playwright", "crawl4ai",
                          "firecrawl", "browserless"],
        "cumulative_timeout_ms": 60000,
        "per_provider_timeout_ms": 15000,
        "min_body_chars": 200,
    },
    "gating": {
        "abort_on_login_required": True,
        "abort_on_paid": True,
    },
}


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: Path | str | None) -> dict[str, Any]:
    """Load JSON config from path; return defaults if path missing or None."""
    if path is None:
        return _deep_merge(DEFAULT_CONFIG, {})
    p = Path(path)
    if not p.is_file():
        return _deep_merge(DEFAULT_CONFIG, {})
    user = json.loads(p.read_text(encoding="utf-8"))
    return _deep_merge(DEFAULT_CONFIG, user)
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): JSON config loader with default fallback"
```

---

## Task 18: ProviderLadder — single provider OK

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Failing test**

```python
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
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement skeleton ladder**

```python
LADDER_CLASSES: dict[str, type] = {
    "direct": DirectProvider,
    "jina": JinaProvider,
    "playwright": PlaywrightProvider,
    "crawl4ai": Crawl4AIProvider,
    "firecrawl": FirecrawlProvider,
    "browserless": BrowserlessProvider,
}

CUMULATIVE_TIMEOUT_WARN = "FETCH_WARN:CUMULATIVE_TIMEOUT_EXHAUSTED"


def _attempt_record(provider: str, http: int | None, latency_ms: int,
                    error: str | None) -> dict[str, Any]:
    return {"provider": provider, "http": http,
            "latency_ms": latency_ms, "error": error}


def fetch_via_ladder(
    *,
    url: str,
    provider_choice: str,
    config: dict[str, Any],
    user_agent: str,
    keep_raw: bool,
    min_body_chars: int | None = None,
    output_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    """Run the provider ladder for `url`. Returns envelope dict."""
    if min_body_chars is None:
        min_body_chars = int(config["ladder"]["min_body_chars"])
    per_timeout = int(config["ladder"]["per_provider_timeout_ms"])
    cum_timeout = int(config["ladder"]["cumulative_timeout_ms"])

    order: list[str]
    if provider_choice == "auto":
        order = list(config["ladder"]["default_order"])
    else:
        order = [provider_choice]

    attempts: list[dict[str, Any]] = []
    skipped: dict[str, str] = {}
    candidates: list[ProviderResult] = []
    chosen: ProviderResult | None = None
    final_status: str = "FAILED"
    content_type = "unknown"
    content_gate = "none"
    reason_for_failed: str | None = None
    reason_for_degraded: str | None = None
    cumulative_ms = 0

    for name in order:
        if name not in LADDER_CLASSES:
            skipped[name] = "unknown_provider"
            continue
        provider = LADDER_CLASSES[name]()
        if provider_choice == "auto" and not provider.is_configured(
            env=dict(os.environ), config=config,
        ):
            # Distinguish stub vs disabled-in-config.
            if isinstance(provider, _StubProvider):
                skipped[name] = "not_configured_stub"
            else:
                skipped[name] = "disabled_in_config"
            continue
        if cumulative_ms >= cum_timeout:
            skipped[name] = "cumulative_timeout_exhausted"
            print(f"{CUMULATIVE_TIMEOUT_WARN} skipped={name}", file=sys.stderr)
            continue
        try:
            r = provider.fetch(url, timeout_ms=per_timeout, user_agent=user_agent)
        except ProviderHardGate as e:
            attempts.append(_attempt_record(
                name, e.http_status, e.latency_ms, "fetch_gated_" + e.gate,
            ))
            cumulative_ms += e.latency_ms
            content_type = "gated"
            content_gate = e.gate
            reason_for_failed = "content_gate_" + e.gate
            final_status = "FAILED"
            break
        except ProviderPermanentError as e:
            attempts.append(_attempt_record(
                name, e.http_status, e.latency_ms, "fetch_http_4xx_nonretryable",
            ))
            cumulative_ms += e.latency_ms
            continue
        except ProviderTransientError as e:
            attempts.append(_attempt_record(
                name, e.http_status, e.latency_ms,
                "fetch_network_timeout" if e.http_status is None
                else "fetch_http_5xx_retryable",
            ))
            cumulative_ms += e.latency_ms
            continue
        except ProviderNotConfigured:
            skipped[name] = "not_configured_stub"
            continue

        cumulative_ms += r.latency_ms
        # Classify result on the basis of body content.
        ct, gate = _classify_content(
            html=r.raw_html or "",
            body_text=r.body_text,
            final_url=r.final_url or url,
            site=_site_from_url(r.final_url or url),
            min_body_chars=min_body_chars,
        )
        if gate != "none":
            attempts.append(_attempt_record(
                name, r.http_status, r.latency_ms, "fetch_gated_" + gate,
            ))
            content_type = "gated"
            content_gate = gate
            reason_for_failed = "content_gate_" + gate
            final_status = "FAILED"
            break
        if ct == "article":
            attempts.append(_attempt_record(
                name, r.http_status, r.latency_ms, None,
            ))
            chosen = r
            content_type = ct
            final_status = "OK"
            break
        # DEGRADED-class result — record and continue.
        err_label = "fetch_js_shell" if ct == "js_shell" else "fetch_short_body"
        attempts.append(_attempt_record(
            name, r.http_status, r.latency_ms, err_label,
        ))
        candidates.append(r)
        content_type = ct  # last-seen DEGRADED type as fallback

    if chosen is None and final_status != "FAILED":
        # All ran but none returned article. Pick best candidate or FAILED.
        if candidates:
            chosen = max(candidates, key=lambda c: c.body_chars)
            final_status = "DEGRADED"
            reason_for_degraded = (
                "all_providers_degraded_short_body"
                if all(c.body_chars < min_body_chars for c in candidates)
                else "all_providers_degraded_js_shell"
            )
        else:
            final_status = "FAILED"
            reason_for_failed = (
                reason_for_failed or "all_providers_failed"
            )

    # Build envelope.
    if chosen is not None:
        title = chosen.title
        md = chosen.body_markdown
        txt = chosen.body_text
        body_chars = chosen.body_chars
        links = chosen.links
        canonical = chosen.canonical_url
        lang = chosen.lang
        final_url = chosen.final_url
        provider_used = chosen.provider
        site = _site_from_url(chosen.final_url or url)
    else:
        title = None
        md = ""
        txt = ""
        body_chars = 0
        links = []
        canonical = None
        lang = None
        final_url = None
        provider_used = "none"
        site = _site_from_url(url)

    raw_html_path = None  # populated by Task 26

    return build_fetch_envelope(
        status=final_status,
        url=url,
        final_url=final_url,
        provider_used=provider_used,
        content_type=content_type,
        content_gate=content_gate,
        title=title,
        body_markdown=md,
        body_text=txt,
        body_chars=body_chars,
        links=links,
        attempts=attempts,
        providers_skipped=skipped,
        reason_for_failed=reason_for_failed,
        reason_for_degraded=reason_for_degraded,
        raw_html_path=raw_html_path,
        site=site,
        canonical_url=canonical,
        lang=lang,
        detected_reason=None,
        user_agent=user_agent,
    )
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): ProviderLadder with classify-aware single-OK path"
```

---

## Task 19: Ladder — Direct→Jina fallthrough on 403

**Files:**
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Add test**

```python
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
```

- [ ] **Step 2: PASS** (Task 18 logic already covers this)

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "test(research): ladder direct 403 falls through to jina"
```

---

## Task 20: Ladder — HardGate short-circuits

**Files:**
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Add tests**

```python
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
```

- [ ] **Step 2: PASS**

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "test(research): ladder hard-gate short-circuit"
```

---

## Task 21: Ladder — all active providers fail → FAILED

**Files:**
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Add test**

```python
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
```

- [ ] **Step 2: PASS**

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "test(research): ladder all-fail → FAILED envelope"
```

---

## Task 22: Ladder — DEGRADED best-candidate pick

**Files:**
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Add test**

```python
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
```

- [ ] **Step 2: PASS**

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "test(research): ladder picks best DEGRADED candidate"
```

---

## Task 23: Ladder — explicit provider skips ladder

**Files:**
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Add tests**

```python
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
```

- [ ] **Step 2: PASS**

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "test(research): explicit --provider skips ladder fall-through"
```

---

## Task 24: Ladder — providers_skipped tracks stubs and disabled

**Files:**
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Add tests**

```python
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
```

- [ ] **Step 2: PASS**

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "test(research): providers_skipped tracks stubs and config-disabled"
```

---

## Task 25: Ladder — cumulative timeout warning

**Files:**
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Add test**

```python
def test_ladder_cumulative_timeout_skips_remaining(capsys):
    config = fetch_url.load_config(None)
    config["ladder"]["cumulative_timeout_ms"] = 1  # immediate cap

    html = _load_fixture("short_body.html").encode("utf-8")

    def fake_urlopen(req, timeout):
        # Direct returns short_body → DEGRADED candidate, latency_ms > 1.
        time.sleep(0.005)
        return _make_http_response(html, url="https://example.com/x")

    import time
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
```

- [ ] **Step 2: PASS** (Task 18 already emits the warning when cumulative ≥ cap)

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "test(research): cumulative timeout warning"
```

---

## Task 26: Optional trafilatura uplift

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Failing tests**

```python
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

    NOTE: `@pytest.mark.optional` here is a *label*, not a skip condition.
    This test does NOT require real trafilatura installed — it monkeypatches
    a fake module shape. So the test runs in the baseline pytest invocation
    and must pass. If you ever need a true opt-in skip (real trafilatura
    integration smoke), use `@pytest.mark.skipif(not _has_real_trafilatura(),
    reason="...")` in a separate test.
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
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

```python
try:
    import trafilatura as _trafilatura_module  # type: ignore
    _TRAFILATURA_AVAILABLE = True
except Exception:  # pragma: no cover
    _trafilatura_module = None  # type: ignore
    _TRAFILATURA_AVAILABLE = False

_trafilatura_warned = False


def _reset_trafilatura_warned_for_tests() -> None:
    global _trafilatura_warned
    _trafilatura_warned = False


def _extract_with_optional_uplift(
    html: str, *, base_url: str,
) -> tuple[str | None, str, str, list[dict[str, Any]], str | None, str | None]:
    title, md, txt, links, canonical, lang = _inline_extract(
        html, base_url=base_url,
    )
    global _trafilatura_warned
    if not _TRAFILATURA_AVAILABLE:
        if not _trafilatura_warned:
            print("FETCH_WARN:NO_TRAFILATURA inline parser only", file=sys.stderr)
            _trafilatura_warned = True
        return title, md, txt, links, canonical, lang
    try:
        uplift_text = _trafilatura_module.extract(html) or ""
    except Exception:
        uplift_text = ""
    if uplift_text and len(uplift_text) > len(txt):
        return title, uplift_text, uplift_text, links, canonical, lang
    return title, md, txt, links, canonical, lang
```

Update `DirectProvider.fetch` to call `_extract_with_optional_uplift` instead of `_inline_extract`. Keep `_inline_extract` callable directly for the dedicated test.

```python
        title, md, txt, links, canonical, lang = _extract_with_optional_uplift(
            html_text, base_url=final_url,
        )
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): optional trafilatura uplift over inline baseline"
```

---

## Task 27: CLI argparse + fetch subcommand skeleton

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Failing test**

```python
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
```

- [ ] **Step 2: FAIL** (`main` undefined)

- [ ] **Step 3: Implement**

Append:

```python
import argparse


EXIT_OK = 0
EXIT_ARGS = 1
EXIT_HTTP = 2
EXIT_NETWORK = 3
EXIT_ENV = 4
EXIT_GATED = 5


STUB_PROVIDERS = {"playwright", "crawl4ai", "firecrawl", "browserless"}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fetch_url.py")
    sub = p.add_subparsers(dest="cmd")
    f = sub.add_parser("fetch")
    f.add_argument("--url", required=False)
    f.add_argument("--provider", default="auto",
                   choices=["auto", "direct", "jina", "playwright",
                            "crawl4ai", "firecrawl", "browserless"])
    f.add_argument("--format", default="markdown",
                   choices=["markdown", "text", "html"])
    f.add_argument("--json", action="store_true",
                   help="Print envelope JSON to stdout instead of summary.")
    f.add_argument("--keep-raw", action="store_true",
                   help="Save raw HTML sidecar.")
    f.add_argument("--timeout-ms", type=int, default=15000)
    f.add_argument("--min-body-chars", type=int, default=200)
    f.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    f.add_argument("--output-dir", default="~/.h2t/research")
    f.add_argument("--project", default="default")
    f.add_argument("--config", default=None)
    sub.add_parser("preflight")
    return p


def _die_args(msg: str) -> None:
    print(f"FETCH_ERROR:ARGS {msg}", file=sys.stderr)
    sys.exit(EXIT_ARGS)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd is None:
        _die_args("subcommand required (fetch | preflight)")
    if args.cmd == "fetch":
        return _run_fetch(args)
    if args.cmd == "preflight":
        return _run_preflight(args)
    _die_args(f"unknown subcommand {args.cmd}")
    return EXIT_ARGS  # unreachable


def _run_fetch(args: argparse.Namespace) -> int:
    if not args.url:
        _die_args("--url is required for `fetch`")
    if args.provider in STUB_PROVIDERS:
        _die_args(
            f"provider={args.provider} not configured (stub in this version)"
        )
    # Continued in Task 28+.
    return EXIT_OK


def _run_preflight(args: argparse.Namespace) -> int:
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): CLI argparse + args validation"
```

---

## Task 28: CLI — wire fetch_via_ladder + sidecar paths

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Failing test**

Sidecar schema follows spec §10.4: `{meta, envelope, body}`. `meta` is sidecar-level metadata (tool, project, url, status); `envelope` is the full fetch envelope verbatim; `body` carries the markdown plus a text excerpt. Don't conflate sidecar `meta` with `envelope.meta`.

```python
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
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement sidecar writer + wire into _run_fetch**

```python
import re as _re

def _slug_from_url(url: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(url)
    host = p.hostname or "url"
    path = (p.path or "").strip("/").replace("/", "-")
    raw = f"{host}-{path}" if path else host
    raw = _re.sub(r"[^a-zA-Z0-9._-]+", "-", raw).strip("-")
    return raw[:80] or "url"


def _output_paths(output_dir: Path, project: str, url: str,
                  ) -> dict[str, Path]:
    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = _slug_from_url(url)
    base = output_dir / f"{project}-fetch-{slug}-{date}"
    return {
        "partial_md": Path(str(base) + ".partial.md"),
        "sources_json": Path(str(base) + ".sources.json"),
        "raw_html": Path(str(base) + ".raw.html"),
    }


def _write_sources_json(path: Path, envelope: dict[str, Any],
                        *, project: str) -> None:
    """Write sidecar per spec §10.4: {meta, envelope, body}."""
    payload = {
        "meta": {
            "tool": "fetch_url.py",
            "tool_version": __version__,
            "project": project,
            "url": envelope["url"],
            "final_url": envelope.get("final_url"),
            "status": envelope["status"],
            "provider_used": envelope.get("provider_used"),
            "timestamp": envelope["meta"]["timestamp"],
        },
        "envelope": envelope,
        "body": {
            "markdown": envelope.get("body_markdown", ""),
            "text_excerpt": (envelope.get("body_text", "") or "")[:5000],
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def _run_fetch(args: argparse.Namespace) -> int:
    if not args.url:
        _die_args("--url is required for `fetch`")
    if args.provider in STUB_PROVIDERS:
        _die_args(
            f"provider={args.provider} not configured (stub in this version)"
        )
    cfg_path = Path(args.config).expanduser() if args.config else None
    config = load_config(cfg_path)
    paths = _output_paths(Path(args.output_dir), args.project, args.url)

    envelope = fetch_via_ladder(
        url=args.url,
        provider_choice=args.provider,
        config=config,
        user_agent=args.user_agent,
        keep_raw=args.keep_raw,
        min_body_chars=args.min_body_chars,
        output_paths=paths,
    )

    _write_sources_json(paths["sources_json"], envelope, project=args.project)

    return _emit_stdout_and_exit(envelope, args)
```

(`_emit_stdout_and_exit` is defined in Task 29.)

Stub it for now to keep the test green:

```python
def _emit_stdout_and_exit(envelope: dict[str, Any],
                          args: argparse.Namespace) -> int:
    return EXIT_OK
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): CLI wires ladder and writes sources.json sidecar"
```

---

## Task 29: CLI — stdout/stderr/exit emission

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Failing tests**

```python
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
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Replace stub `_emit_stdout_and_exit` with full implementation**

```python
def _emit_stdout_and_exit(envelope: dict[str, Any],
                          args: argparse.Namespace) -> int:
    status = envelope["status"]
    if args.json:
        print(json.dumps(envelope, ensure_ascii=False, indent=2))
    elif status != "FAILED":
        print(_render_markdown_summary(envelope, args))

    if status == "FAILED":
        _emit_stderr_for_failed(envelope)

    if status == "OK" or status == "DEGRADED":
        return EXIT_OK
    # FAILED:
    gate = envelope.get("content_gate", "none")
    if gate in ("login_required", "paid"):
        return EXIT_GATED
    last = envelope["telemetry"]["attempts"][-1] if envelope["telemetry"]["attempts"] else None
    if last and last.get("error") == "fetch_network_timeout":
        return EXIT_NETWORK
    return EXIT_HTTP


def _render_markdown_summary(envelope: dict[str, Any],
                             args: argparse.Namespace) -> str:
    lines = []
    lines.append(f"## Fetch: {envelope['url']}")
    lines.append("")
    lines.append(f"status: {envelope['status']}")
    lines.append(f"provider_used: {envelope['provider_used']}")
    lines.append(f"content_type: {envelope['content_type']}")
    if envelope["title"]:
        lines.append(f"title: {envelope['title']}")
    lines.append(f"body_chars: {envelope['body_chars']}")
    lines.append("")
    body = envelope["body_markdown"] or envelope["body_text"]
    excerpt = body[:500]
    if excerpt:
        lines.append("### Excerpt")
        lines.append("")
        lines.append(excerpt)
    return "\n".join(lines)


def _emit_stderr_for_failed(envelope: dict[str, Any]) -> None:
    gate = envelope.get("content_gate", "none")
    url = envelope["url"]
    if gate in ("login_required", "paid"):
        print(f"FETCH_ERROR:GATED url={url} gate={gate}", file=sys.stderr)
        return
    attempts = envelope["telemetry"]["attempts"]
    if not attempts:
        print(f"FETCH_ERROR:HTTP url={url} attempts=0", file=sys.stderr)
        return
    last = attempts[-1]
    err = last.get("error") or ""
    if err == "fetch_network_timeout":
        print(f"FETCH_ERROR:NETWORK url={url} attempts={len(attempts)}",
              file=sys.stderr)
    else:
        print(f"FETCH_ERROR:HTTP url={url} http={last.get('http')}",
              file=sys.stderr)
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): CLI stdout/stderr emission and exit codes"
```

---

## Task 30: --keep-raw flag — raw HTML sidecar

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Failing tests**

```python
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
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Wire keep-raw into ladder**

The chosen `ProviderResult` carries `raw_html`. When `keep_raw=True` AND a chosen result exists, write `paths["raw_html"]` and stash its path on the envelope.

In `fetch_via_ladder`, after the chosen-or-best decision and before `build_fetch_envelope`, replace the `raw_html_path = None` line:

```python
    raw_html_path = None
    if keep_raw and chosen is not None and chosen.raw_html and output_paths:
        raw_path = output_paths["raw_html"]
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(chosen.raw_html, encoding="utf-8")
        raw_html_path = str(raw_path)
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): --keep-raw writes raw HTML sidecar"
```

---

## Task 31: Partial markdown sidecar

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Failing test**

```python
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
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

In `_run_fetch`, after `_write_sources_json`:

```python
    if envelope["status"] != "FAILED":
        _write_partial_md(paths["partial_md"], envelope)
```

Add helper:

```python
def _write_partial_md(path: Path, envelope: dict[str, Any]) -> None:
    lines = []
    lines.append(f"# Fetch: {envelope['url']}")
    lines.append("")
    lines.append(f"status: {envelope['status']}")
    lines.append(f"provider_used: {envelope['provider_used']}")
    lines.append(f"content_type: {envelope['content_type']}")
    if envelope["title"]:
        lines.append(f"title: {envelope['title']}")
    lines.append("")
    lines.append("## Body")
    lines.append("")
    lines.append(envelope["body_markdown"] or envelope["body_text"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): partial.md sidecar for OK/DEGRADED"
```

---

## Task 32: Preflight subcommand

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Failing tests**

```python
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
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

```python
def _run_preflight(args: argparse.Namespace) -> int:
    # Ping Jina endpoint root.
    try:
        req = urllib.request.Request(JINA_ENDPOINT_DEFAULT, headers={
            "User-Agent": DEFAULT_USER_AGENT,
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
    except urllib.error.URLError as e:
        print(f"FETCH_ERROR:ENV jina endpoint unreachable: {e}",
              file=sys.stderr)
        return EXIT_ENV
    except Exception as e:
        print(f"FETCH_ERROR:ENV preflight failure: {e}", file=sys.stderr)
        return EXIT_ENV
    return EXIT_OK
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): preflight subcommand pings Jina root"
```

---

## Task 33: Cloudflare 403 not gated regression test

**Files:**
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Add test**

```python
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
```

- [ ] **Step 2: PASS**

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "test(research): plain 403 is not gated, ladder falls through"
```

---

## Task 34: Unicode and redirect tests

**Files:**
- Create: `tests/fixtures/fetch/non_ascii_article.html`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Create fixture**

`non_ascii_article.html`:

```html
<!DOCTYPE html>
<html lang="ru"><head>
  <meta charset="utf-8">
  <title>Атрибуты POP — основы</title>
</head><body>
  <article>
    <h1>Атрибуты POP — основы</h1>
    <p>Жизненный цикл атрибута: создание, модификация, потребление.</p>
    <p>Это критично для предсказуемого поведения сети POP.</p>
  </article>
</body></html>
```

- [ ] **Step 2: Add tests**

```python
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
```

- [ ] **Step 3: PASS**

- [ ] **Step 4: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/tests/test_fetch_url.py plugins/h2t-ops/skills/research/tests/fixtures/fetch/non_ascii_article.html
git -C C:/dev/h2t-skills-fetch-ladder commit -m "test(research): unicode safety and envelope version fields"
```

---

## Task 35: KNOWN_PAYWALLED_DOMAINS injection test

**Files:**
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Add test**

```python
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
```

- [ ] **Step 2: PASS**

- [ ] **Step 3: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "test(research): KNOWN_PAYWALLED_DOMAINS gating works when populated"
```

---

## Task 36: Public API + `__all__`

**Files:**
- Modify: `fetch_url.py`
- Modify: `tests/test_fetch_url.py`

- [ ] **Step 1: Failing test**

```python
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
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Add to module top after imports**

```python
__all__ = [
    "fetch_via_ladder",
    "build_fetch_envelope",
    "load_config",
    "ProviderResult",
    "ProviderTransientError",
    "ProviderPermanentError",
    "ProviderHardGate",
    "ProviderNotConfigured",
    "DirectProvider",
    "JinaProvider",
    "PlaywrightProvider",
    "Crawl4AIProvider",
    "FirecrawlProvider",
    "BrowserlessProvider",
    "ENVELOPE_VERSION",
    "FETCH_ENVELOPE_VERSION",
    "PRIMARY_ENGINE",
    "DEFAULT_USER_AGENT",
    "KNOWN_PAYWALLED_DOMAINS",
]
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/scripts/fetch_url.py plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "feat(research): public __all__ for #105/#104 adapter reuse"
```

---

## Task 37: Smoke — full pytest run, fix flakes

- [ ] **Step 1: Run entire test module**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t-ops/skills/research/tests/test_fetch_url.py -v
```

Expected: **all** tests pass — including `@pytest.mark.optional`, since that decorator is a label here, not a skip. The `optional` test monkeypatches a fake trafilatura module and does not require real install.

- [ ] **Step 2: Register the marker label (avoid pytest warnings)**

Pytest emits `PytestUnknownMarkWarning` for unrecognised marker names. Register `optional` so the test output stays clean. Prepend in `tests/test_fetch_url.py`:

```python
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "optional: label for opt-in scenarios (e.g. real-trafilatura uplift). "
        "Currently still runs in baseline; reserve for future @skipif gating.",
    )
```

…or, if the project already has a `conftest.py`, add the marker there instead. Run:

```bash
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t-ops/skills/research/tests/test_fetch_url.py -v 2>&1 | tail -10
```

Expected: clean run, no `PytestUnknownMarkWarning`. Again — **no tests should be reported as skipped** under this configuration; the marker is purely informational.

- [ ] **Step 3: Run sister test file too (no regressions)**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t-ops/skills/research/tests/ -v
```

Expected: existing `test_exa_search.py` still green.

- [ ] **Step 4: Commit any small fixes**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add -- plugins/h2t-ops/skills/research/tests/test_fetch_url.py
git -C C:/dev/h2t-skills-fetch-ladder commit -m "test(research): register optional pytest marker"
```

(Skip if no edits were needed.)

---

## Task 38: SKILL.md — add "Fetching Specific URLs" section + version bump

**Files:**
- Modify: `plugins/h2t-ops/skills/research/SKILL.md`

- [ ] **Step 1: Bump skill version in frontmatter**

Change `version: 0.1.1` → `version: 0.1.2`.

Update `compatibility:` line to:

```yaml
compatibility: "Requires $EXA_API_KEY env var. Get key at https://dashboard.exa.ai/api-keys. Requires ~/.h2t/venv (run /h2t-core:setup if missing). Optional: pip install trafilatura inside ~/.h2t/venv for richer article extraction (script falls back to stdlib inline parser if absent)."
```

- [ ] **Step 2: Add `$FETCH_CLI` runtime variable after `EXA_CLI`**

Insert in the "Runtime variables" code block (after the `EXA_CLI=...` line):

```bash
FETCH_CLI="$H2T_PYTHON ${CLAUDE_PLUGIN_ROOT}/skills/research/scripts/fetch_url.py"
```

- [ ] **Step 3: Append "Fetching Specific URLs" section after "Provider Status Envelope"**

```markdown
## Fetching Specific URLs (`fetch_url.py`)

`exa_search.py` находит URL'ы; `fetch_url.py` доставляет их содержимое через provider ladder (`direct → jina → stubs`).

Когда использовать:
- ✅ Известный URL, нужен полный текст статьи (а не только Exa highlight).
- ✅ Plain WebFetch вернул shell / 403 / пустоту.
- ✅ JS-rendered страницы (Jina Reader сам рендерит JS на их side).

Когда НЕ использовать:
- ❌ Поиск по теме → используй `$EXA_CLI search`.
- ❌ Bulk crawl сайта → используй адаптеры (`alltd.py`, `iihq.py`) после их реализации.
- ❌ Auth/paid контент → скрипт вернёт `FAILED + content_gate`; не пытайся обойти через `WebFetch`.

CLI:

$FETCH_CLI fetch --url "https://..." [--provider auto] [--json] [--keep-raw] [--project NAME]

Envelope status — тот же контракт, что у `exa_search.py`:

| `envelope.status` | exit | Действие агента |
|---|---|---|
| OK | 0 | Continue: synthesize from `body_markdown`. |
| DEGRADED | 0 | Report `STATUS: DEGRADED + reason=...`. Можно: (a) попробовать `--provider jina` явно, (b) пометить источник `failed-harvest` и идти дальше. Никакого silent fallback. |
| FAILED + `content_gate=login_required\|paid` | 5 | STOP. Не fetch'и через WebFetch. Источник legitimately gated. |
| FAILED + http | 2 | STOP. Report exact `FETCH_ERROR:HTTP`. |
| FAILED + network | 3 | STOP. Report exact `FETCH_ERROR:NETWORK`. |

Privacy note: Jina Reader — third-party URL relay; URL и часть содержимого видны Jina'у. Для public web research это допустимо; для anything sensitive — `--provider direct` или disable Jina через `~/.h2t/config/research/fetch_providers.json` (`providers.jina.enabled: false`).
```

- [ ] **Step 4: Append two antipatterns to existing list**

```markdown
- **Bypass auth/paywall via WebFetch fallback** — `content_gate=login_required\|paid` означает legitimately gated. Substitute via WebFetch — нарушение интегритета.
- **Synthesize article from short_body / js_shell** — `status=DEGRADED` означает body не пригоден для wiki ingest. Помечай `failed-harvest`.
```

- [ ] **Step 5: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/SKILL.md
git -C C:/dev/h2t-skills-fetch-ladder commit -m "docs(research): SKILL.md — Fetching Specific URLs section + 0.1.2"
```

---

## Task 39: reference.md — fetch envelope schema appendix

**Files:**
- Modify: `plugins/h2t-ops/skills/research/reference.md`

- [ ] **Step 1: Append section**

```markdown
---

## Fetch Envelope Schema (fetch_url.py)

Same `envelope_version: "1"` as Exa search envelope (status semantics OK / DEGRADED / FAILED), but flat single-URL shape:

```json
{
  "status": "OK | DEGRADED | FAILED",
  "url": "https://...",
  "final_url": "https://... (after redirects)",
  "provider_used": "direct | jina | none",
  "content_type": "article | listing | js_shell | gated | short_body | unknown",
  "content_gate": "none | login_required | paid | unknown",
  "title": "...",
  "body_markdown": "...",
  "body_text": "...",
  "body_chars": 1234,
  "links": [{"href": "...", "text": "...", "rel": ""}],
  "metadata": {
    "canonical_url": "...",
    "site": "alltd.org",
    "lang": "en",
    "detected_reason": null,
    "site_adapter": null,
    "raw_html_path": null
  },
  "telemetry": {
    "attempts": [{"provider": "direct", "http": 403, "latency_ms": 100, "error": "fetch_http_4xx_nonretryable"}],
    "reason_for_degraded": null,
    "reason_for_failed": null,
    "total_latency_ms": 100,
    "providers_skipped": ["playwright", "crawl4ai", "firecrawl", "browserless"],
    "providers_skipped_reason": {"playwright": "not_configured_stub"}
  },
  "meta": {
    "primary_engine": "fetch_ladder",
    "envelope_version": "1",
    "fetch_envelope_version": "1",
    "timestamp": "2026-05-07T12:34:56+00:00",
    "user_agent": "h2t-research-fetch/0.0.1 ..."
  }
}
```

Adapters (#104/#105) extend by setting `metadata.site_adapter` and adding adapter-specific fields under `metadata`. The `list-by-tag` subcommand introduces a separate envelope variant with `items[]` instead of body fields — see adapter docs when those land.
```

- [ ] **Step 2: Commit**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/skills/research/reference.md
git -C C:/dev/h2t-skills-fetch-ladder commit -m "docs(research): reference.md — fetch envelope schema"
```

---

## Task 40: Plugin version bump (atomic across plugin.json + marketplace.json)

**Files:**
- Modify: `plugins/h2t-ops/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

The repo ships a helper that bumps **both** files atomically — `scripts/bump_plugin.py`. Editing only `plugin.json` causes version drift between marketplace and plugin manifest (incident: lichtpfad/h2t-skills#74). Use the helper.

- [ ] **Step 1: Run bump helper**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe scripts/bump_plugin.py h2t-ops 1.1.2
```

Expected: prints recommended commit command, exits 0. Both files now contain `"version": "1.1.2"`.

- [ ] **Step 2: Verify both files updated**

Use Grep tool, pattern `"version"` in `plugins/h2t-ops/.claude-plugin/plugin.json` AND `.claude-plugin/marketplace.json`. Each must show `"version": "1.1.2"` for the `h2t-ops` entry.

- [ ] **Step 3: Commit (stage both files explicitly)**

```bash
git -C C:/dev/h2t-skills-fetch-ladder add plugins/h2t-ops/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git -C C:/dev/h2t-skills-fetch-ladder commit -m "chore(h2t-ops): bump plugin to 1.1.2 (fetch_url.py)"
```

---

## Task 41: Final acceptance verification

- [ ] **Step 1: Full test run**

```
C:/Users/stani/.h2t/venv/Scripts/python.exe -m pytest plugins/h2t-ops/skills/research/tests/ -v 2>&1 | tail -20
```

Expected: all green. `@pytest.mark.optional` tests pass when triggered (use `-m optional` to opt in if you'd like to verify trafilatura uplift; otherwise they should be marked-but-not-run as configured).

- [ ] **Step 2: Spec acceptance walk-through**

Open `docs/superpowers/specs/2026-05-07-research-fetch-url-ladder.md` §12. For each checkbox confirm a passing test or wired-up code path:

- [ ] Spec written before code → done in PR predecessor commit `85f86d6`.
- [ ] CLI `fetch_url.py` callable → run: `C:/Users/stani/.h2t/venv/Scripts/python.exe plugins/h2t-ops/skills/research/scripts/fetch_url.py preflight` and capture exit.
- [ ] Envelope shape — covered by Task 2, 18, 34.
- [ ] Baseline tests don't require paid keys / browser / network / pip installs sverh stdlib — confirm by running tests on a venv where only pytest is installed.
- [ ] No hard dep on Firecrawl/Browserless/Crawl4AI/Playwright — Task 16 + Task 24.
- [ ] SKILL.md updated — Task 38.
- [ ] envelope_version compat — Task 34.
- [ ] Auth/paywall not bypassed — Tasks 13, 20, 35.
- [ ] Provider attempts visible in telemetry — Tasks 19, 21, 22, 24.
- [ ] Stubs don't issue HTTP — Task 24 (asserts on attempts list).
- [ ] Inline baseline without trafilatura — Task 26.
- [ ] Trafilatura uplift correct when present — Task 26 (optional).
- [ ] `--keep-raw` semantics — Tasks 30, 31.
- [ ] `--json + FAILED gated` — Task 29 (`test_cli_gated_with_json_flag`).
- [ ] 403 без auth header не gated — Task 33.

If any acceptance criterion is unclear or untested, write the gap test before claiming done.

- [ ] **Step 3: Look at `git log` summary**

```
git -C C:/dev/h2t-skills-fetch-ladder log --oneline origin/main..HEAD
```

Expected: ~40 commits, each conventional-commit-prefixed `feat(research):` / `test(research):` / `docs(research):` / `chore(h2t-ops):`.

- [ ] **Step 4: Push branch**

(Only after explicit user OK — pushing is a shared-state action.)

```
git -C C:/dev/h2t-skills-fetch-ladder push -u origin feature/research-fetch-url-ladder
```

- [ ] **Step 5: Open PR via gh**

(Only after explicit user OK.)

```bash
gh pr create --repo lichtpfad/h2t-skills \
  --base main \
  --head feature/research-fetch-url-ladder \
  --title "feat(research): fetch_url.py provider ladder (#103)" \
  --body-file - <<'EOF'
Implements #103 per spec
docs/superpowers/specs/2026-05-07-research-fetch-url-ladder.md.

## Summary

- Active providers: `direct` (stdlib urllib + inline HTML extractor) + `jina` (Reader relay, optional bearer auth).
- Stubs: `playwright`, `crawl4ai`, `firecrawl`, `browserless` — `ProviderNotConfigured`, never call out.
- Envelope `envelope_version: "1"` compatible with #100 status semantics, flat single-URL shape with `content_type` / `content_gate` / `provider_used` / per-attempt telemetry.
- `--keep-raw` flag (default off) writes `.raw.html` for adapter (#104/#105) consumption.
- Auth/paywall gating: 401 + WWW-Authenticate, login-form/paywall DOM tokens, `KNOWN_PAYWALLED_DOMAINS`, redirect-to-login → `FAILED` exit 5; never bypass.
- Plain Cloudflare 403 (no auth header) → ladder fall-through, not gated.

## Tests

- 33 baseline tests, all stdlib, no network, no paid keys.
- 1 `@pytest.mark.optional` test for trafilatura uplift.

## Out of scope (follow-ups)

- Real Playwright client (deferred — see spec §13).
- AllTouchDesigner adapter — issue #105.
- IIHQ adapter — issue #104.
- Robots.txt enforcement.
- KNOWN_PAYWALLED_DOMAINS seed.

## Refs

- Spec: docs/superpowers/specs/2026-05-07-research-fetch-url-ladder.md
- Issue: lichtpfad/h2t-skills#103
- Parent ladder: lichtpfad/h2t-skills#98
- Phase-2 umbrella: lichtpfad/h2t-skills#97
EOF
```

- [ ] **Step 6: Comment on issue #98 with chosen ladder design**

(Only after PR is open and you have an URL to reference.)

```bash
gh issue comment 98 --repo lichtpfad/h2t-skills --body "Chosen ladder design landed in #<PR_NUMBER>: direct → jina → stubs. Real Playwright/Crawl4AI/Firecrawl/Browserless deferred to follow-ups based on post-merge smoke. Spec: docs/superpowers/specs/2026-05-07-research-fetch-url-ladder.md."
```

---

## Self-Review Notes (already applied)

- Spec sections §3.1, §3.2, §4.1, §4.3, §5.1, §5.3, §5.4, §5.5, §5.6, §5.7, §6.x, §7.x, §8.x, §10.x, §11.x → mapped to Tasks 1–40.
- Ladder skipped reason vocabulary consistent: `not_configured_stub` (stubs), `disabled_in_config` (active provider turned off), `cumulative_timeout_exhausted` (cap reached). Same strings in code and tests.
- Provider attempt error labels consistent: `fetch_http_4xx_nonretryable`, `fetch_http_5xx_retryable`, `fetch_network_timeout`, `fetch_js_shell`, `fetch_short_body`, `fetch_gated_login_required`, `fetch_gated_paid`, or `null`.
- ProviderResult is the contract: every provider returns one OR raises a typed exception; ladder is the single place that builds attempt records and envelope.
- No task references functions defined in another task without that earlier task creating them. Forward references: only `_emit_stdout_and_exit` (stubbed in Task 28, replaced in Task 29) — explicitly called out.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-07-research-fetch-url-ladder.md`.

**Execution mode: 3 worker-blocks with reviews between them.** 41 fresh subagents = too much context-reload overhead for tasks this dense. Worker-blocks are sized so each one produces a coherent, reviewable diff and ends at a natural boundary.

| Block | Tasks | What lands | Review focus |
|---|---|---|---|
| **Worker A** | 1–17 | Bootstrap, envelope, exceptions, ProviderResult, inline extractor, DirectProvider full error matrix, content classifier, JinaProvider, stubs, JSON config loader | Provider contracts, exception taxonomy, classifier signals, no leaked HTTP from stubs |
| **Worker B** | 18–32 | ProviderLadder (single-OK / fall-through / hard-gate / all-fail / DEGRADED-best / explicit-skip / providers_skipped / cumulative timeout), trafilatura uplift, CLI argparse + sidecars + `--keep-raw` + `--json` + preflight | Ladder decision logic, sidecar shape `{meta, envelope, body}`, exit code matrix, gating short-circuit invariants |
| **Worker C** | 33–41 | Cloudflare 403 regression, unicode, KNOWN_PAYWALLED_DOMAINS, public `__all__`, smoke run, SKILL.md, reference.md, plugin version bump (via `scripts/bump_plugin.py`), acceptance walk-through | Public API surface for adapters, docs accuracy, version-sync (plugin.json + marketplace.json), spec §12 acceptance coverage |

**Push and `gh pr create` (Task 41 Step 4–6) are gated by an additional explicit user OK.** Do not push until reviewer signs off on Worker C.

**Review checkpoints:**

- After **A**: cherry-check provider tests + diff size; Confirm no stub provider issues outbound HTTP; verify `__all__` not yet exported (Worker C job).
- After **B**: run full pytest; eyeball ladder code for skipped-reason consistency (`not_configured_stub` / `disabled_in_config` / `cumulative_timeout_exhausted`); confirm `--json + gated` test passes with exit 5.
- After **C**: run `git log --oneline origin/main..HEAD` — should be ~41 conventional-commit-prefixed entries; spec §12 checklist all covered; SKILL.md privacy note present; both manifest files at 1.1.2.

**If a worker hits a blocker mid-block:** stop, surface the issue, do NOT skip the task. Plan amendments go through the same review gate as the original spec.
