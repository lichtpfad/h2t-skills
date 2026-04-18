# h2t-ops:research Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `h2t-ops:research` skill (Exa-based semantic research), integrate BayramAnnakov/lead-search plugin (Anysite lead-gen), deprecate old `h2t:research-agent` — per approved spec `docs/superpowers/specs/2026-04-18-research-skill-architecture-design.md`. Root cause addressed: silent fallback + authoritative unsourced synthesis (#69).

**Architecture:** Engine-split via skill names (`/research` → Exa, `/search-leads` → Anysite via Bayram plugin). Exa transport is a stdlib-only Python CLI wrapper (`scripts/exa_search.py`) invoked from SKILL.md — NOT MCP. All tool calls are transparent in main conversation. Persistence to `~/.h2t/research/` with REPORT-SPEC.md format including telemetry integrity check. Fail-loud protocol: structured `EXA_ERROR:*` stderr + typed exit codes, no silent fallback.

**Tech Stack:** Python 3.11+ (stdlib: `urllib.request`, `json`, `argparse`, `pathlib`, `hashlib`, `datetime`); pytest + `unittest.mock` for tests; Bash for SKILL.md runtime discovery (`H2T_PYTHON` + `${CLAUDE_PLUGIN_ROOT}` pattern); Exa HTTP API v1; Anysite HTTP MCP (user-scope install).

---

## File Structure

### New files (to create)

```
plugins/h2t-ops/
├── commands/
│   └── research.md                            # slash-command wrapper
└── skills/
    └── research/
        ├── SKILL.md                           # main 7-step workflow
        ├── REPORT-SPEC.md                     # report template + integrity rules
        ├── reference.md                       # Exa API parameter reference
        ├── examples.md                        # invocation examples
        ├── systemprompts/
        │   ├── fast.md
        │   ├── generic.md
        │   ├── news.md
        │   ├── academic.md
        │   ├── competitor.md
        │   ├── people.md
        │   └── deep.md
        ├── scripts/
        │   └── exa_search.py                  # Python CLI wrapper (stdlib)
        └── tests/
            ├── __init__.py
            └── test_exa_search.py             # pytest suite
```

### Modified / replaced files

```
plugins/h2t/agents/research-agent.md           # REPLACE with deprecation stub
~/.claude/CLAUDE.md                            # APPEND routing rule (user-level, outside repo)
```

### Responsibilities

- `scripts/exa_search.py` — single source of truth for Exa API. argparse CLI; mode→params mapping; filter validation; HTTP via urllib; response parsing; markdown/json persistence; telemetry client (fail-graceful); structured stderr + exit codes.
- `tests/test_exa_search.py` — pytest coverage: mode config, argparse, validation rules, HTTP mocking, response parsing, persistence, telemetry buffering.
- `systemprompts/{mode}.md` — YAML frontmatter (`exa_type`, `exa_category`, `output_schema`) + body = Exa `systemPrompt` text.
- `reference.md` — full Exa API reference, mode mapping table, cost data placeholder.
- `examples.md` — 6+ invocation examples (valid combinations), sample output format reference.
- `REPORT-SPEC.md` — canonical report template with meta + telemetry + sources + findings + grounding + limitations.
- `SKILL.md` — 7-step workflow, architecture diagram, fail-loud rules, antipatterns.
- `commands/research.md` — thin slash-command wrapper delegating to `h2t-ops:research` skill.

---

## Pre-flight Setup (once, before Task 1)

Verify venv exists and pytest works:

```bash
H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
"$H2T_PYTHON" -m pytest --version
```

Expected: pytest version printed. If missing — run `/h2t-core:setup` first.

---

## Phase 1: Script Foundation (TDD)

### Task 1: Scaffold directory + --version flag

**Files:**
- Create: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Create: `plugins/h2t-ops/skills/research/tests/__init__.py` (empty)
- Create: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write the failing test**

```python
# plugins/h2t-ops/skills/research/tests/test_exa_search.py
"""Tests for exa_search.py CLI wrapper."""
import subprocess
import sys
from pathlib import Path

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
```

- [ ] **Step 2: Run to verify FAIL**

```bash
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: FAIL — `FileNotFoundError` or `assert SCRIPT.is_file()` fails (script doesn't exist yet).

- [ ] **Step 3: Write minimal implementation**

Create empty `tests/__init__.py` (0 bytes) and:

```python
# plugins/h2t-ops/skills/research/scripts/exa_search.py
#!/usr/bin/env python3
"""exa_search.py — Exa API wrapper for h2t-ops:research skill.

See docs/superpowers/specs/2026-04-18-research-skill-architecture-design.md
"""
from __future__ import annotations

__version__ = "0.1.0"

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="exa_search",
        description="Exa API wrapper (preflight / search / crawl subcommands).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"exa_search {__version__}",
    )
    sub = parser.add_subparsers(dest="cmd", required=False)
    # subcommands added in later tasks
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify PASS**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/scripts/exa_search.py \
        plugins/h2t-ops/skills/research/tests/__init__.py \
        plugins/h2t-ops/skills/research/tests/test_exa_search.py
git commit -m "feat(h2t-ops:research): scaffold exa_search.py + version flag"
```

---

### Task 2: MODE_CONFIG constants

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append to `test_exa_search.py`:

```python
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
```

- [ ] **Step 2: Run to verify FAIL**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: new tests FAIL with `AttributeError: module 'exa_search' has no attribute 'MODE_CONFIG'`.

- [ ] **Step 3: Implement MODE_CONFIG**

Add to `exa_search.py` after the imports:

```python
from typing import Any

# Mode → Exa API params (spec §5.2).
# highlight_chars = default maxCharacters for contents.highlights.
MODE_CONFIG: dict[str, dict[str, Any]] = {
    "fast":       {"type": "fast", "category": None,             "highlight_chars": 2000, "num_results": 10},
    "generic":    {"type": "auto", "category": None,             "highlight_chars": 4000, "num_results": 10},
    "news":       {"type": "auto", "category": "news",           "highlight_chars": 3000, "num_results": 10},
    "academic":   {"type": "auto", "category": "research paper", "highlight_chars": 4000, "num_results": 8},
    "competitor": {"type": "auto", "category": "company",        "highlight_chars": 4000, "num_results": 10},
    "people":     {"type": "auto", "category": "people",         "highlight_chars": 3000, "num_results": 10},
    "deep":       {"type": "deep", "category": None,             "highlight_chars": 5000, "num_results": 10},
}
```

- [ ] **Step 4: Run to verify PASS**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/
git commit -m "feat(h2t-ops:research): add MODE_CONFIG for 7 modes"
```

---

### Task 3: Category filter blocks (CATEGORY_BLOCKS)

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append to `test_exa_search.py`:

```python
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
```

- [ ] **Step 2: Run to verify FAIL**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: 3 new tests FAIL with `AttributeError: module 'exa_search' has no attribute 'CATEGORY_BLOCKS'`.

- [ ] **Step 3: Implement CATEGORY_BLOCKS**

Add after `MODE_CONFIG`:

```python
# Category-specific param incompatibilities (spec §5.7).
# Each listed param causes HTTP 400 from Exa when combined with that category.
CATEGORY_BLOCKS: dict[str, set[str]] = {
    "company":          {"start_date", "end_date", "include_domains", "exclude_domains"},
    "people":           {"start_date", "end_date", "include_text", "exclude_text", "exclude_domains"},
    "financial report": {"exclude_text"},
}
```

- [ ] **Step 4: Run to verify PASS**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/
git commit -m "feat(h2t-ops:research): add CATEGORY_BLOCKS for filter validation"
```

---

### Task 4: Structured error exit helper (`die()`)

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append to `test_exa_search.py`:

```python
def test_die_writes_stderr_and_exits_with_code(capsys):
    with pytest.raises(SystemExit) as excinfo:
        exa_search.die(4, "EXA_ERROR:ENV EXA_API_KEY missing")
    assert excinfo.value.code == 4
    captured = capsys.readouterr()
    assert "EXA_ERROR:ENV" in captured.err
    assert "EXA_API_KEY missing" in captured.err
    assert captured.out == ""
```

Add near the top of the file (after imports):

```python
import pytest
```

- [ ] **Step 2: Run to verify FAIL**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: FAIL with `AttributeError: module 'exa_search' has no attribute 'die'`.

- [ ] **Step 3: Implement die()**

Add after `CATEGORY_BLOCKS`:

```python
def die(code: int, stderr_msg: str) -> None:
    """Write structured error to stderr and exit. Spec §5.4."""
    print(stderr_msg, file=sys.stderr)
    sys.exit(code)
```

- [ ] **Step 4: Run to verify PASS**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/
git commit -m "feat(h2t-ops:research): add die() fail-loud exit helper"
```

---

### Task 5: validate_args() — category filter enforcement

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append to `test_exa_search.py`:

```python
from types import SimpleNamespace


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
```

- [ ] **Step 2: Run to verify FAIL**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: 4 new tests FAIL (`validate_args` undefined).

- [ ] **Step 3: Implement validate_args**

Add after `die()`:

```python
def validate_args(args: argparse.Namespace) -> None:
    """Fail-fast validation per spec §5.7 to prevent HTTP 400 from Exa."""
    cfg = MODE_CONFIG[args.mode]
    category = cfg["category"]

    if category in CATEGORY_BLOCKS:
        blocked = CATEGORY_BLOCKS[category]
        attempted: dict[str, Any] = {
            "start_date": args.start_date,
            "end_date": args.end_date,
            "include_domains": args.include_domains,
            "exclude_domains": args.exclude_domains,
            "include_text": args.include_text,
            "exclude_text": args.exclude_text,
        }
        conflicts = [k for k in blocked if attempted.get(k)]
        if conflicts:
            first = conflicts[0].replace("_", "-")
            die(
                1,
                f"EXA_ERROR:ARGS mode={args.mode} (category={category}) "
                f"incompatible with --{first}. "
                f"Blocked params for this category: {sorted(blocked)}. "
                f"Switch to --mode news or generic to use these filters.",
            )

    # Universal: include_text / exclude_text are single-item only (spec §5.7).
    for name in ("include_text", "exclude_text"):
        val = getattr(args, name, None)
        if isinstance(val, list) and len(val) > 1:
            die(
                1,
                f"EXA_ERROR:ARGS --{name.replace('_', '-')} supports only "
                f"single-item arrays; got {len(val)} items. Split into separate calls.",
            )
```

- [ ] **Step 4: Run to verify PASS**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/
git commit -m "feat(h2t-ops:research): validate_args prevents 400 from invalid category combos"
```

---

### Task 6: load_system_prompt() — read systemprompts/{mode}.md

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append to `test_exa_search.py`:

```python
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
```

- [ ] **Step 2: Run to verify FAIL**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: FAIL (`load_system_prompt` undefined).

- [ ] **Step 3: Implement load_system_prompt**

Add after `validate_args`. Also add `SYSTEMPROMPTS_DIR` near module globals:

```python
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SYSTEMPROMPTS_DIR = SCRIPT_DIR.parent / "systemprompts"


def load_system_prompt(mode: str) -> tuple[str, dict[str, Any]]:
    """Read systemprompts/{mode}.md. Returns (body_text, output_schema_or_empty).

    YAML frontmatter recognised keys: mode, exa_type, exa_category, output_schema.
    output_schema must be a single-line JSON object OR a JSON block quoted with `|`.
    Body = systemPrompt for Exa API.
    """
    path = SYSTEMPROMPTS_DIR / f"{mode}.md"
    if not path.is_file():
        die(1, f"EXA_ERROR:ARGS systemprompt file missing: {path}")
    raw = path.read_text(encoding="utf-8")
    schema: dict[str, Any] = {}
    body = raw
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end > 0:
            fm = raw[4:end]
            body = raw[end + 5:].lstrip()
            # Look for single-line JSON: output_schema: {...}
            for line in fm.splitlines():
                stripped = line.strip()
                if stripped.startswith("output_schema:"):
                    val = stripped.split(":", 1)[1].strip()
                    if val.startswith("{"):
                        try:
                            schema = json.loads(val)
                        except json.JSONDecodeError:
                            pass
    return body.strip(), schema
```

Add `import json` if not already imported at top.

- [ ] **Step 4: Run to verify PASS**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/
git commit -m "feat(h2t-ops:research): load_system_prompt reads mode frontmatter"
```

---

### Task 7: build_body() — construct Exa request JSON

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append to `test_exa_search.py`:

```python
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
```

- [ ] **Step 2: Run to verify FAIL**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: FAIL (`build_body` undefined).

- [ ] **Step 3: Implement build_body**

Add after `load_system_prompt`:

```python
def build_body(
    args: argparse.Namespace,
    system_prompt: str,
    output_schema: dict[str, Any],
) -> dict[str, Any]:
    """Compose Exa /search request body (spec §5.2 + §5.8)."""
    cfg = MODE_CONFIG[args.mode]
    body: dict[str, Any] = {
        "query": args.query,
        "type": cfg["type"],
        "numResults": args.num_results or cfg["num_results"],
        "contents": {"highlights": {"maxCharacters": cfg["highlight_chars"]}},
    }
    if cfg["category"]:
        body["category"] = cfg["category"]
    if system_prompt:
        body["systemPrompt"] = system_prompt
    if output_schema:
        body["outputSchema"] = output_schema
        body["structuredOutput"] = True
    if args.additional_queries:
        body["additionalQueries"] = list(args.additional_queries)
    if args.start_date:
        body["startPublishedDate"] = args.start_date
    if args.end_date:
        body["endPublishedDate"] = args.end_date
    if args.include_domains:
        body["includeDomains"] = list(args.include_domains)
    if args.exclude_domains:
        body["excludeDomains"] = list(args.exclude_domains)
    if args.include_text:
        body["includeText"] = list(args.include_text)
    if args.exclude_text:
        body["excludeText"] = list(args.exclude_text)
    if args.country:
        body["userLocation"] = args.country
    if args.full_text:
        body["contents"]["text"] = {"maxCharacters": 15000}
    if args.mode == "deep" and output_schema:
        # Spec §5.8 — minimize highlight when structuredOutput is active.
        body["contents"]["highlights"] = {"maxCharacters": 1}
    return body
```

- [ ] **Step 4: Run to verify PASS**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/
git commit -m "feat(h2t-ops:research): build_body composes Exa /search payload"
```

---

### Task 8: call_exa() — HTTP client with fail-loud HTTP errors

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append to `test_exa_search.py`:

```python
from unittest.mock import patch, MagicMock
import urllib.error
import io


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


def test_call_exa_http_429_returns_error_body(capsys):
    err = urllib.error.HTTPError(
        url="https://api.exa.ai/search",
        code=429,
        msg="Too Many Requests",
        hdrs=None,
        fp=io.BytesIO(json.dumps({"error": "rate_limit_exceeded"}).encode("utf-8")),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        status, body, latency_ms = exa_search.call_exa(
            "/search", {"query": "q"}, api_key="testkey"
        )
    assert status == 429
    assert body["error"] == "rate_limit_exceeded"


def test_call_exa_network_timeout_exits_3(capsys):
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timed out")):
        with pytest.raises(SystemExit) as excinfo:
            exa_search.call_exa("/search", {"query": "q"}, api_key="testkey")
    assert excinfo.value.code == 3
    err = capsys.readouterr().err
    assert "EXA_ERROR:NETWORK" in err
    assert "timed out" in err
```

Add at top of test file if not already: `import json, io`.

- [ ] **Step 2: Run to verify FAIL**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: FAIL (`call_exa` undefined).

- [ ] **Step 3: Implement call_exa**

Add `import time, urllib.request, urllib.error, json` at top if missing. Then after `build_body`:

```python
EXA_API = "https://api.exa.ai"


def call_exa(
    endpoint: str,
    body: dict[str, Any],
    api_key: str,
    timeout: int = 60,
) -> tuple[int, dict[str, Any], int]:
    """POST to Exa. Returns (http_status, response_json_or_error_body, latency_ms).

    Network errors (URLError) exit 3 via die() — these cannot be silently swallowed.
    HTTP errors (4xx/5xx) return (status, error_body, latency) to caller for decision.
    """
    req = urllib.request.Request(
        f"{EXA_API}{endpoint}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = int((time.monotonic() - start) * 1000)
            return resp.status, json.loads(resp.read().decode("utf-8")), latency
    except urllib.error.HTTPError as e:
        latency = int((time.monotonic() - start) * 1000)
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = {"error": "non_json_error_response"}
        return e.code, err_body, latency
    except urllib.error.URLError as e:
        latency = int((time.monotonic() - start) * 1000)
        die(3, f"EXA_ERROR:NETWORK {e.reason} after {latency}ms")
        raise  # unreachable — satisfies type checker
```

- [ ] **Step 4: Run to verify PASS**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/
git commit -m "feat(h2t-ops:research): call_exa HTTP client with fail-loud network errors"
```

---

### Task 9: preflight() subcommand

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append:

```python
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
```

- [ ] **Step 2: Run to verify FAIL**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: FAIL (`preflight` undefined).

- [ ] **Step 3: Implement preflight**

Add after `call_exa`:

```python
def preflight() -> None:
    """Step 0: env + connectivity probe (spec §4 Step 0)."""
    if not os.environ.get("EXA_API_KEY"):
        die(4, "EXA_ERROR:ENV EXA_API_KEY missing; obtain at https://dashboard.exa.ai/api-keys")
    req = urllib.request.Request(f"{EXA_API}/", method="GET")
    try:
        urllib.request.urlopen(req, timeout=5)
    except urllib.error.URLError as e:
        die(4, f"EXA_ERROR:NETWORK cannot reach {EXA_API}: {e.reason}")
    print("OK")
```

Add `import os` at top if missing.

- [ ] **Step 4: Run to verify PASS**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/
git commit -m "feat(h2t-ops:research): preflight subcommand checks env + connectivity"
```

---

### Task 10: slugify() + persistence paths

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append:

```python
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
```

- [ ] **Step 2: Run to verify FAIL**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement**

Add `import re` near top imports. Then append:

```python
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 50) -> str:
    """Lowercase, collapse non-alnum → hyphen, trim, cap length."""
    s = _SLUG_RE.sub("-", text.lower()).strip("-")
    return s[:max_len]


def output_paths(
    output_dir: Path, project: str, topic: str, date: str
) -> dict[str, Path]:
    """Per spec §8: persistence filenames."""
    output_dir.mkdir(parents=True, exist_ok=True)
    base = f"{slugify(project)}-{slugify(topic)}-{date}"
    return {
        "partial_md": output_dir / f"{base}.partial.md",
        "final_md": output_dir / f"{base}.md",
        "sources_json": output_dir / f"{base}.sources.json",
    }
```

- [ ] **Step 4: Run to verify PASS**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/
git commit -m "feat(h2t-ops:research): slugify + output_paths for persistence naming"
```

---

### Task 11: render_stdout_summary() + write_partial_md() + write_sources_json()

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append:

```python
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


def test_render_stdout_summary_includes_query_and_cost(capsys):
    data = _sample_exa_response()
    exa_search.render_stdout_summary(
        data, query="Rejuve.bio competitors", mode="competitor",
        latency_ms=2100, partial_path=Path("/tmp/x.partial.md"),
        json_path=Path("/tmp/x.sources.json"),
    )
    out = capsys.readouterr().out
    assert "Rejuve.bio competitors" in out
    assert "competitor" in out
    assert "$0.012" in out
    assert "2100ms" in out or "2.1s" in out
    assert "rejuve.bio/about" in out
    assert "/tmp/x.partial.md" in out


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
```

- [ ] **Step 2: Run to verify FAIL**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement**

Append to `exa_search.py`:

```python
def render_stdout_summary(
    data: dict[str, Any],
    *,
    query: str,
    mode: str,
    latency_ms: int,
    partial_path: Path,
    json_path: Path,
) -> None:
    """Compact markdown summary printed to stdout (spec §5.5)."""
    results = data.get("results", [])
    cost = data.get("costDollars", {}).get("total", 0)
    print(f"## Exa Search: {query!r}")
    print(f"**Mode:** {mode} | **Results:** {len(results)} | **Cost:** ${cost:.3f} | **Latency:** {latency_ms}ms")
    print()
    for i, r in enumerate(results, 1):
        title = r.get("title", "(no title)")
        url = r.get("url", "")
        highlights = r.get("highlights") or []
        snippet = highlights[0][:260] if highlights else ""
        print(f"{i}. [{title}]({url})")
        if snippet:
            print(f"   {snippet}")
    print()
    print(f"Saved: {partial_path}")
    print(f"JSON:  {json_path}")


def write_sources_json(
    path: Path,
    meta: dict[str, Any],
    response: dict[str, Any],
) -> None:
    """Raw Exa API response + metadata sidecar."""
    path.write_text(
        json.dumps({"meta": meta, "response": response}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_partial_md(
    path: Path,
    *,
    meta: dict[str, Any],
    telemetry_rows: list[dict[str, Any]],
) -> None:
    """Per spec §8.3: script writes technical Meta + Telemetry; agent finishes to final .md."""
    total_cost = sum(r["cost_usd"] for r in telemetry_rows)
    total_latency = sum(r["latency_ms"] for r in telemetry_rows)
    total_results = sum(r["results"] for r in telemetry_rows)
    errors = sum(1 for r in telemetry_rows if r["http"] >= 400)
    exa_calls = sum(1 for r in telemetry_rows if "exa_search.py" in r["tool"])
    total_calls = len(telemetry_rows)

    lines: list[str] = []
    lines.append(f"# Research: {meta['query']}\n")
    lines.append("## Meta\n")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| **Date** | {meta['date']} |")
    lines.append(f"| **Project** | {meta['project']} |")
    lines.append(f"| **Query** | {meta['query']} |")
    lines.append(f"| **Mode** | {meta['mode']} |")
    lines.append(f"| **Depth** | {meta['depth']} |")
    lines.append(f"| **Engine** | Exa (via scripts/exa_search.py) |")
    lines.append(f"| **Status** | {meta['status']} |")
    lines.append(f"| **Cache hit** | {meta['cache_hit']} |\n")
    lines.append("## Telemetry\n")
    lines.append("| # | Tool | Args | HTTP | Latency | Cost | Results |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in telemetry_rows:
        lines.append(
            f"| {r['num']} | `{r['tool']}` | `{r['args']}` | "
            f"{r['http']} | {r['latency_ms']}ms | ${r['cost_usd']:.3f} | {r['results']} |"
        )
    lines.append(
        f"| **Totals** | | | **{errors} errors** | "
        f"**{total_latency}ms** | **${total_cost:.3f}** | **{total_results} items** |\n"
    )
    lines.append(
        f"> **Integrity check:** {exa_calls}/{total_calls} calls used Exa API. "
        f"0 fallbacks to WebSearch.\n"
    )
    lines.append("## Sources\n\n*(agent fills in from .sources.json)*\n")
    lines.append("## Key Findings\n\n*(agent fills in — requires URL + verbatim quote + confidence per spec §4 Step 5)*\n")
    lines.append("## Grounding Notes\n\n*(agent fills in)*\n")
    lines.append("## Limitations\n\n*(agent fills in)*\n")
    lines.append("## Follow-up Suggestions\n\n*(agent fills in)*\n")
    path.write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: Run to verify PASS**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/
git commit -m "feat(h2t-ops:research): stdout summary + partial.md + sources.json persistence"
```

---

### Task 12: Telemetry client (fail-graceful)

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append:

```python
def test_post_telemetry_disabled_when_env_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("H2T_EVALS_URL", raising=False)
    status = exa_search.post_telemetry(
        event={"foo": "bar"}, buffer_path=tmp_path / "buf.jsonl"
    )
    assert status == "disabled"
    assert not (tmp_path / "buf.jsonl").exists()


def test_post_telemetry_buffers_on_network_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_EVALS_URL", "https://evals.example.com")
    buf = tmp_path / "buf.jsonl"
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
        status = exa_search.post_telemetry(event={"a": 1}, buffer_path=buf)
    assert status == "buffered"
    assert buf.exists()
    line = buf.read_text(encoding="utf-8").strip()
    assert json.loads(line) == {"a": 1}


def test_post_telemetry_sent_on_success(monkeypatch, tmp_path):
    monkeypatch.setenv("H2T_EVALS_URL", "https://evals.example.com")
    buf = tmp_path / "buf.jsonl"
    with patch("urllib.request.urlopen", return_value=_mock_urlopen_response(202, {})):
        status = exa_search.post_telemetry(event={"a": 1}, buffer_path=buf)
    assert status == "sent"
    assert not buf.exists()
```

- [ ] **Step 2: Run to verify FAIL**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement**

Append to `exa_search.py`:

```python
def post_telemetry(event: dict[str, Any], buffer_path: Path) -> str:
    """Fail-graceful telemetry (spec §9.2).
    Returns one of: 'sent', 'buffered', 'disabled', 'awaiting_endpoint'.
    """
    evals_url = os.environ.get("H2T_EVALS_URL")
    if not evals_url:
        return "disabled"
    token = os.environ.get("H2T_EVALS_TOKEN", "")
    req = urllib.request.Request(
        f"{evals_url.rstrip('/')}/api/telemetry/research",
        data=json.dumps(event).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}" if token else "",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if 200 <= resp.status < 300:
                return "sent"
    except urllib.error.URLError:
        pass
    except urllib.error.HTTPError:
        pass
    # Fallback: buffer locally
    buffer_path.parent.mkdir(parents=True, exist_ok=True)
    with buffer_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    return "buffered"
```

- [ ] **Step 4: Run to verify PASS**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/
git commit -m "feat(h2t-ops:research): fail-graceful telemetry client with local buffer"
```

---

### Task 13: argparse wiring — preflight / search / crawl subcommands

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append:

```python
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
```

- [ ] **Step 2: Run to verify FAIL**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: FAIL (subcommands not wired).

- [ ] **Step 3: Replace main() with full argparse**

Replace the stub `main()` in `exa_search.py`:

```python
MODES = list(MODE_CONFIG.keys())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="exa_search",
        description="Exa API wrapper (preflight / search / crawl).",
    )
    parser.add_argument("--version", action="version", version=f"exa_search {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=False)

    sub.add_parser("preflight", help="Check env + connectivity.")

    s = sub.add_parser("search", help="Run Exa /search.")
    s.add_argument("--query", required=True)
    s.add_argument("--mode", choices=MODES, default="generic")
    s.add_argument("--depth", choices=["shallow", "standard", "deep"], default="standard")
    s.add_argument("--num-results", type=int, default=None, dest="num_results")
    s.add_argument("--additional-queries", default=None,
                   help="Comma-separated list (2-3 recommended for mode=deep).",
                   dest="additional_queries_raw")
    s.add_argument("--start-date", default=None, dest="start_date")
    s.add_argument("--end-date", default=None, dest="end_date")
    s.add_argument("--include-domains", default=None, dest="include_domains_raw")
    s.add_argument("--exclude-domains", default=None, dest="exclude_domains_raw")
    s.add_argument("--include-text", default=None, dest="include_text_raw")
    s.add_argument("--exclude-text", default=None, dest="exclude_text_raw")
    s.add_argument("--country", default=None)
    s.add_argument("--full-text", action="store_true", dest="full_text")
    s.add_argument("--output-dir", default=str(Path.home() / ".h2t" / "research"),
                   dest="output_dir")
    s.add_argument("--project", default="default")

    c = sub.add_parser("crawl", help="Run Exa /contents on one URL.")
    c.add_argument("--url", required=True)
    c.add_argument("--output-dir", default=str(Path.home() / ".h2t" / "research"),
                   dest="output_dir")
    c.add_argument("--project", default="default")

    return parser


def _split_csv(raw: str | None) -> list[str] | None:
    return [x.strip() for x in raw.split(",") if x.strip()] if raw else None


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "preflight":
        preflight()
        return 0
    if args.cmd == "search":
        # Expand CSV flags to lists
        args.additional_queries = _split_csv(args.additional_queries_raw)
        args.include_domains = _split_csv(args.include_domains_raw)
        args.exclude_domains = _split_csv(args.exclude_domains_raw)
        args.include_text = _split_csv(args.include_text_raw)
        args.exclude_text = _split_csv(args.exclude_text_raw)
        return _run_search(args)
    if args.cmd == "crawl":
        return _run_crawl(args)
    parser.print_help()
    return 0


def _run_search(args: argparse.Namespace) -> int:
    """Wiring added in Task 14."""
    raise NotImplementedError  # filled in Task 14


def _run_crawl(args: argparse.Namespace) -> int:
    """Wiring added in Task 15."""
    raise NotImplementedError  # filled in Task 15
```

- [ ] **Step 4: Run to verify PASS**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: argparse-level tests PASS. `test_cli_preflight_invokes_preflight` PASSES. Other preflight/search/crawl smoke tests not added yet.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/
git commit -m "feat(h2t-ops:research): full argparse for preflight/search/crawl"
```

---

### Task 14: _run_search() end-to-end

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append to `test_exa_search.py`:

```python
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
```

- [ ] **Step 2: Run to verify FAIL**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: FAIL (`_run_search` raises `NotImplementedError`).

- [ ] **Step 3: Implement _run_search**

Replace `_run_search` placeholder:

```python
def _run_search(args: argparse.Namespace) -> int:
    validate_args(args)
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        die(4, "EXA_ERROR:ENV EXA_API_KEY missing")
    system_prompt, schema = load_system_prompt(args.mode)
    body = build_body(args, system_prompt, schema)
    status, data, latency_ms = call_exa("/search", body, api_key)
    if status >= 400:
        err_body = json.dumps(data)[:300]
        die(2, f"EXA_ERROR:API http={status} body={err_body!r}")

    # Persist + report
    out_dir = Path(args.output_dir)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    topic = args.query
    paths = output_paths(out_dir, args.project, topic, date)

    cost = float(data.get("costDollars", {}).get("total", 0))
    n_results = len(data.get("results", []))
    cat = MODE_CONFIG[args.mode]["category"]
    tel_args = f"type={MODE_CONFIG[args.mode]['type']}"
    if cat:
        tel_args += f",category={cat}"
    tel_args += f",numResults={body['numResults']}"

    telemetry_rows = [{
        "num": 1,
        "tool": "exa_search.py search",
        "args": tel_args,
        "http": status,
        "latency_ms": latency_ms,
        "cost_usd": cost,
        "results": n_results,
    }]
    meta = {
        "query": args.query,
        "mode": args.mode,
        "depth": args.depth,
        "project": args.project,
        "date": timestamp,
        "status": "completed" if n_results > 0 else "partial",
        "cache_hit": False,
    }
    write_sources_json(paths["sources_json"], meta, data)
    write_partial_md(paths["partial_md"], meta=meta, telemetry_rows=telemetry_rows)
    render_stdout_summary(
        data,
        query=args.query,
        mode=args.mode,
        latency_ms=latency_ms,
        partial_path=paths["partial_md"],
        json_path=paths["sources_json"],
    )

    # Fire-and-forget telemetry
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
            "num_results_returned": n_results,
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

Add these imports at top if missing:

```python
from datetime import datetime, timezone
from hashlib import sha256
```

- [ ] **Step 4: Run to verify PASS**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/
git commit -m "feat(h2t-ops:research): _run_search end-to-end with persistence+telemetry"
```

---

### Task 15: _run_crawl() — Exa /contents endpoint

**Files:**
- Modify: `plugins/h2t-ops/skills/research/scripts/exa_search.py`
- Modify: `plugins/h2t-ops/skills/research/tests/test_exa_search.py`

- [ ] **Step 1: Write failing test**

Append:

```python
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
```

- [ ] **Step 2: Run to verify FAIL**

```bash
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: FAIL (`_run_crawl` raises `NotImplementedError`).

- [ ] **Step 3: Implement _run_crawl**

Replace placeholder:

```python
def _run_crawl(args: argparse.Namespace) -> int:
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        die(4, "EXA_ERROR:ENV EXA_API_KEY missing")
    body = {"urls": [args.url], "text": {"maxCharacters": 15000}}
    status, data, latency_ms = call_exa("/contents", body, api_key)
    if status >= 400:
        err_body = json.dumps(data)[:300]
        die(2, f"EXA_ERROR:API http={status} body={err_body!r}")

    out_dir = Path(args.output_dir)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    topic = f"crawl-{args.url}"
    paths = output_paths(out_dir, args.project, topic, date)

    cost = float(data.get("costDollars", {}).get("total", 0))
    n_results = len(data.get("results", []))
    meta = {
        "query": f"crawl({args.url})",
        "mode": "crawl",
        "depth": "n/a",
        "project": args.project,
        "date": timestamp,
        "status": "completed" if n_results > 0 else "partial",
        "cache_hit": False,
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
"$H2T_PYTHON" -m pytest plugins/h2t-ops/skills/research/tests/test_exa_search.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/h2t-ops/skills/research/
git commit -m "feat(h2t-ops:research): _run_crawl for Exa /contents endpoint"
```

---

## Phase 2: Supporting Markdown Files

### Task 16: Create all 7 systemprompts/*.md

**Files:**
- Create: `plugins/h2t-ops/skills/research/systemprompts/fast.md`
- Create: `plugins/h2t-ops/skills/research/systemprompts/generic.md`
- Create: `plugins/h2t-ops/skills/research/systemprompts/news.md`
- Create: `plugins/h2t-ops/skills/research/systemprompts/academic.md`
- Create: `plugins/h2t-ops/skills/research/systemprompts/competitor.md`
- Create: `plugins/h2t-ops/skills/research/systemprompts/people.md`
- Create: `plugins/h2t-ops/skills/research/systemprompts/deep.md`

- [ ] **Step 1: Write content — `fast.md`**

```markdown
---
mode: fast
exa_type: fast
---

Return concise factual answers. Cite each claim with a URL. Prefer authoritative sources (Wikipedia, official documentation, government sites) over blogs and forums. Omit marketing language.
```

- [ ] **Step 2: Write content — `generic.md`**

```markdown
---
mode: generic
exa_type: auto
---

You are a neutral research assistant. Return a balanced view from multiple source types (official pages, reporting, analysis). Cite each finding with a URL. Avoid speculation; where a claim cannot be sourced, omit it.
```

- [ ] **Step 3: Write content — `news.md`**

```markdown
---
mode: news
exa_type: auto
exa_category: news
---

Prefer primary news sources and official announcements over aggregators and opinion pieces. Include publication dates in output. Flag any source older than 12 months as `[stale: YYYY-MM-DD]`. Do not mix editorial/opinion with reporting.
```

- [ ] **Step 4: Write content — `academic.md`**

```markdown
---
mode: academic
exa_type: auto
exa_category: research paper
---

Return peer-reviewed research only. For each paper include title, authors, publication venue, year, and DOI when available. Prefer arxiv.org, openreview.net, pubmed.ncbi.nlm.nih.gov over news coverage of research. Note when findings are contested across papers.
```

- [ ] **Step 5: Write content — `competitor.md`**

```markdown
---
mode: competitor
exa_type: auto
exa_category: company
output_schema: {"type": "object", "properties": {"company_name": {"type": "string", "description": "company name in 5 words or less"}, "hq_location": {"type": "string", "description": "city, country in 4 words or less"}, "founded": {"type": "string", "description": "year or 'unknown'"}, "product_categories": {"type": "array", "items": {"type": "string", "description": "each in 3 words or less"}}, "funding_stage": {"type": "string", "description": "one of: bootstrap, seed, series A/B/C+, public, unknown"}, "team_size_estimate": {"type": "string", "description": "employee count range in 5 words or less"}}, "required": ["company_name"]}
---

You are a competitive intelligence researcher. Prefer official company pages (about, pricing, product, team) and SEC filings over press coverage. Include concrete data: founding year, HQ location, product line, team size estimate, funding stage. Deduplicate results — same company from different domains should be merged. Flag any information older than 12 months as `[stale: YYYY-MM-DD]`.
```

- [ ] **Step 6: Write content — `people.md`**

```markdown
---
mode: people
exa_type: auto
exa_category: people
---

Return verified professional profiles only. For each person include name, current role, company, and location when available. Prefer LinkedIn, company team pages, and conference speaker bios over unverified directories. Exclude namesakes unrelated to the query — if uncertain, list with `[ambiguous: reason]` flag instead of including.
```

- [ ] **Step 7: Write content — `deep.md`**

```markdown
---
mode: deep
exa_type: deep
---

Multi-step synthesis: cross-reference claims across 3+ independent sources. Cite a URL for every factual assertion. When sources disagree, present both positions with their citations — do not pick a winner without evidence. Structure output as: (1) consensus points with shared sources, (2) contested points with per-side sources, (3) open questions with URLs to pursue.
```

- [ ] **Step 8: Sanity check files load without error**

```bash
"$H2T_PYTHON" -c "
import sys
sys.path.insert(0, 'plugins/h2t-ops/skills/research/scripts')
import exa_search
from pathlib import Path
exa_search.SYSTEMPROMPTS_DIR = Path('plugins/h2t-ops/skills/research/systemprompts')
for m in ['fast','generic','news','academic','competitor','people','deep']:
    body, schema = exa_search.load_system_prompt(m)
    assert body, f'{m}: empty body'
    print(f'{m}: body={len(body)}ch schema={len(schema)}keys')
"
```

Expected: 7 lines printed, each with `body=` and `schema=` counts; `competitor` has `schema=1keys` (wrapper object).

- [ ] **Step 9: Commit**

```bash
git add plugins/h2t-ops/skills/research/systemprompts/
git commit -m "feat(h2t-ops:research): add 7 systemprompts for all modes"
```

---

### Task 17: Create `reference.md`

**Files:**
- Create: `plugins/h2t-ops/skills/research/reference.md`

- [ ] **Step 1: Write file**

```markdown
# Exa API Reference — h2t-ops:research

> Lazy-loaded by agent when detailed API knowledge is needed. Not in main SKILL.md to keep it under 500 lines.

## Endpoints Used

| Endpoint | Purpose | Subcommand |
|---|---|---|
| `POST /search` | Semantic / keyword / deep search | `exa_search.py search` |
| `POST /contents` | Fetch clean text (JS-rendered, PDFs auto-handled) | `exa_search.py crawl` |

Base URL: `https://api.exa.ai`.
Auth: `x-api-key: $EXA_API_KEY` header.

## Search Types (consolidated 4-type model)

| type | Median latency | Use |
|---|---|---|
| `fast` | ~500ms | Single-step factual Q&A, autocomplete, voice agents |
| `auto` (default) | ~1000ms | Balanced general-purpose |
| `deep` | ~5000ms | Multi-hop synthesis, agentic workflows |
| `neural` | embedded | Semantic similarity (incorporated into fast/auto) |

**Compare within latency classes only** — `fast` vs `deep` = different use cases.

## Mode → Exa Params Mapping (canonical)

| mode | type | category | highlights.maxChars | default numResults |
|---|---|---|---|---|
| `fast` | `fast` | — | 2000 | 10 |
| `generic` | `auto` | — | 4000 | 10 |
| `news` | `auto` | `news` | 3000 | 10 |
| `academic` | `auto` | `research paper` | 4000 | 8 |
| `competitor` | `auto` | `company` | 4000 | 10 |
| `people` | `auto` | `people` | 3000 | 10 |
| `deep` | `deep` | — | 5000 | 10 |

## Supported Filters per Mode (critical — prevents 400 errors)

| mode | date filters | include/excludeDomains | include/excludeText | country |
|---|:---:|:---:|:---:|:---:|
| `fast` | ✅ | ✅ | ⚠ single-item | ✅ |
| `generic` | ✅ | ✅ | ⚠ single-item | ✅ |
| `news` | ✅ | ✅ | ⚠ single-item | ✅ |
| `academic` | ✅ | ✅ | ⚠ single-item | ✅ |
| `competitor` | ❌ | ❌ | ⚠ single-item | ✅ |
| `people` | ❌ | ⚠ linkedin.com only | ❌ | ✅ |
| `deep` | ✅ | ✅ | ⚠ single-item | ✅ |

Workarounds: need date/domain filters + company context → switch to `mode=news` or `mode=generic` (loses `category` boost but filters work).

## outputSchema Constraints

- Max 10 properties total across all nesting levels
- Array items: flat objects only, primitive fields (`string` / `integer` / `boolean` / `array` of strings)
- No nested objects inside array items (400)
- Root must be `{"type": "object"}`
- `null` silently ignored
- Every string field description MUST include a length constraint (e.g. "in 12 words or less")

## Deep Mode Required Params

When `mode=deep` script auto-sets:
- `type: "deep"`
- `structuredOutput: true` (when outputSchema present)
- `highlights.maxCharacters: 1` (when outputSchema present — minimizes duplication)
- Default `numResults: 10` (override via `--num-results` if systemPrompt requires batch)

## Cost (observed; updated via telemetry)

| Operation | Typical cost |
|---|---|
| `search` mode=generic, 5 results, highlights | $0.007 |
| `search` mode=deep, 5 results | $0.02–0.05 |
| `crawl` single URL with text | $0.001–0.003 |

See `~/.h2t/research/.pending_telemetry.jsonl` for accumulated observations.

## Known Limitations (Exa, documented)

- Cannot filter by gender, ethnicity, or other demographics
- `people` category: `includeDomains` = LinkedIn only (other domains get 400)
- Multi-item `includeText`/`excludeText` arrays = 400 error; use separate calls
- `context` parameter deprecated (use `text` or `highlights` instead)
- No real-time monitoring (see Exa Monitors — separate API, not in v0.1)

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `EXA_ERROR:ENV EXA_API_KEY missing` | env var not exported | `export EXA_API_KEY=...` |
| `EXA_ERROR:NETWORK` | firewall / proxy / api.exa.ai down | Check proxy, retry later |
| `EXA_ERROR:API http=429` | rate limit | Wait 60s; Exa deep has lower QPS |
| `EXA_ERROR:API http=401` | invalid API key | Rotate at dashboard.exa.ai |
| `EXA_ERROR:ARGS ... incompatible with --start-date` | mode=competitor/people blocks filter | Switch to `--mode news` or `generic` |
| Empty results | query too narrow or niche vertical | Try query variations, widen date range, switch category |
```

- [ ] **Step 2: Commit**

```bash
git add plugins/h2t-ops/skills/research/reference.md
git commit -m "feat(h2t-ops:research): add reference.md (Exa API reference)"
```

---

### Task 18: Create `examples.md`

**Files:**
- Create: `plugins/h2t-ops/skills/research/examples.md`

- [ ] **Step 1: Write file**

```markdown
# Examples — h2t-ops:research

## Valid CLI Invocations

All examples assume `H2T_PYTHON` and `EXA_CLI` are set per SKILL.md Step 0.

### 1. Quick factual lookup (fast mode)

```bash
$EXA_CLI search \
  --query "What is the 2026 EU AI Act enforcement deadline?" \
  --mode fast \
  --num-results 5 \
  --project policy
```

### 2. Generic balanced research (depth=standard)

```bash
$EXA_CLI search \
  --query "Rejuve.bio longevity research DAO governance" \
  --mode generic \
  --depth standard \
  --num-results 10 \
  --project rejuve
```

### 3. News with date + domain filters

```bash
$EXA_CLI search \
  --query "Rejuve.bio Switzerland press coverage" \
  --mode news \
  --start-date 2025-10-01 --end-date 2026-04-18 \
  --include-domains "techcrunch.com,swissbiotech.ch" \
  --num-results 10 \
  --project rejuve
```

### 4. Academic papers

```bash
$EXA_CLI search \
  --query "small-molecule NAD+ precursors aging" \
  --mode academic \
  --start-date 2024-01-01 \
  --num-results 8 \
  --project longevity
```

### 5. Competitor research (company category — no date/domain filters)

```bash
$EXA_CLI search \
  --query "Switzerland-based biotech longevity startups 2026" \
  --mode competitor \
  --country CH \
  --num-results 10 \
  --project rejuve
```

### 6. People research

```bash
$EXA_CLI search \
  --query "Alex Zhavoronkov Insilico Medicine" \
  --mode people \
  --num-results 5 \
  --project rejuve
```

### 7. Deep synthesis with query variations

```bash
$EXA_CLI search \
  --query "quantum computing impact on cryptography 2026" \
  --mode deep \
  --additional-queries "post-quantum cryptography research,NIST PQC standards update" \
  --num-results 10 \
  --project security
```

### 8. Crawl a known URL

```bash
$EXA_CLI crawl \
  --url "https://rejuve.bio/about" \
  --project rejuve
```

## Output Format

Every run produces two files in `--output-dir` (default `~/.h2t/research/`):

- `{project}-{topic-slug}-{YYYY-MM-DD}.partial.md` — script-written Meta + Telemetry
- `{project}-{topic-slug}-{YYYY-MM-DD}.sources.json` — raw Exa response + metadata

The agent reads `.partial.md`, adds Sources / Key Findings / Grounding / Limitations / Follow-up per `REPORT-SPEC.md`, then writes final `{project}-{topic-slug}-{YYYY-MM-DD}.md` and deletes `.partial.md`.

## Sample Output (stdout)

```
## Exa Search: 'Rejuve.bio longevity research DAO governance'
**Mode:** generic | **Results:** 8 | **Cost:** $0.008 | **Latency:** 1040ms

1. [Rejuve.bio — About](https://rejuve.bio/about)
   Rejuve.bio operates as a decentralized autonomous organization (DAO) focused on longevity research...
2. [SingularityNET Longevity Initiative](https://singularitynet.io/longevity)
   Partner organization powering the Rejuve.bio protocol infrastructure...
...

Saved: ~/.h2t/research/rejuve-rejuve-bio-longevity-research-dao-governance-2026-04-18.partial.md
JSON:  ~/.h2t/research/rejuve-rejuve-bio-longevity-research-dao-governance-2026-04-18.sources.json
```

## Cross-Engine Recipe (manual)

Research a company end-to-end requires two skills:

```
User: "Research Rejuve.bio — company + people + news."

Agent plan:
1. /research --mode competitor --query "Rejuve.bio about product team"     (company pages)
2. /research --mode news --query "Rejuve.bio" --start-date 2025-10-01     (recent coverage)
3. /search-leads (Bayram plugin) — "Rejuve.bio founders and core team"    (LinkedIn)

Agent synthesises manually across the three outputs in conversation.
```

There is no automatic cross-engine orchestration in v0.1.
```

- [ ] **Step 2: Commit**

```bash
git add plugins/h2t-ops/skills/research/examples.md
git commit -m "feat(h2t-ops:research): add examples.md (valid CLI invocations + output format)"
```

---

### Task 19: Create `REPORT-SPEC.md`

**Files:**
- Create: `plugins/h2t-ops/skills/research/REPORT-SPEC.md`

- [ ] **Step 1: Write file**

```markdown
# Research Report Template — h2t-ops:research

> Canonical format for `~/.h2t/research/{project}-{topic-slug}-{YYYY-MM-DD}.md`. Script writes Meta + Telemetry sections; agent completes Sources / Key Findings / Grounding / Limitations / Follow-up per this spec.

## Template

```markdown
# Research: {topic}

## Meta

| Field | Value |
|---|---|
| **Date** | {ISO-8601 timestamp, UTC} |
| **Project** | {project slug} |
| **Session** | {$H2T_SESSION_ID if set} |
| **Query** | {exact user query} |
| **Mode** | {fast / generic / news / academic / competitor / people / deep} |
| **Depth** | {shallow / standard / deep} |
| **Engine** | Exa (via scripts/exa_search.py) |
| **Status** | ✅ completed / ⚠ partial / ❌ degraded |
| **Cache hit** | {false / path-to-cached-file} |

## Telemetry

| # | Tool | Args | HTTP | Latency | Cost | Results |
|---|---|---|---|---|---|---|
| 1 | `exa_search.py search` | `type=auto,category=company,numResults=10` | 200 | 2100ms | $0.012 | 10 |
| 2 | `exa_search.py crawl` | `url=rejuve.bio/about` | 200 | 1300ms | $0.002 | 1 |
| **Totals** | | | **0 errors** | **3400ms** | **$0.014** | **11 items** |

> **Integrity check:** 2/2 calls used Exa API. 0 fallbacks to WebSearch.

## Sources

1. [Title](url) — [source type, YYYY-MM-DD] — used in findings #1, #2
2. ...

## Key Findings

### Finding #1: {concise statement in one sentence}
- **Evidence:** "Exact verbatim quote from source highlight" — [Source #1]
- **Confidence:** high / medium / low
- **Reason for confidence:** {one sentence — multi-source confirmation / single authoritative / contested}
- **Implications:** {optional, 1–2 sentences}

### Finding #2: ...

## Grounding Notes

- Total sources cited: N
- Sources from Exa `/search`: N
- Sources from Exa `/contents` (crawl): N
- Sources from WebSearch / other: **0** (MUST be 0 if Status=completed)
- Unique domains: N
- Date range of content: YYYY-MM-DD → YYYY-MM-DD
- Freshness: {within 6 months ✅ / mixed / older}

## Limitations

- {What was NOT found}
- {What could not be verified / sources shaky}
- {Assumptions made explicit}

## Follow-up Suggestions

- For employees/team → `/search-leads` (Anysite)
- For financial filings → re-run `mode=academic` `category="financial report"`
- For press coverage 2025 → re-run `mode=news` + `--start-date 2025-01-01`

---

*Generated by `h2t-ops:research` skill v0.1.0 | Telemetry: {status}*
```

## Integrity Check Rule

Line `Integrity check: N/N calls used Exa API. M fallbacks to WebSearch.` is **mandatory**. If it reads `0/N calls used Exa. N fallbacks` — that is a debug signal that something went wrong and the script was not actually invoked. This was the detection mechanism in #69 — agent-written telemetry revealed Exa wasn't being used.

## Telemetry Status Literal

| Status | When |
|---|---|
| `✅ sent to h2t-evals` | HTTP 2xx from `$H2T_EVALS_URL` |
| `⏳ buffered locally at ~/.h2t/research/.pending_telemetry.jsonl` | Network error or non-2xx |
| `⊘ disabled` | `$H2T_EVALS_URL` not set |
| `🚧 awaiting endpoint` | MVP default — endpoint/schema not yet finalized |

## Grounding Rule (mandatory for ALL depths)

Every Key Finding MUST have:
1. Verbatim quote (in double quotes) from source highlight
2. URL to source (linked)
3. Confidence label (high / medium / low)

**No exceptions.** If there's nothing to quote — the finding goes to Limitations, not Key Findings. Unsourced synthesis was half of #69's root cause; this rule is a hard stop.

## Script vs Agent Responsibility

| File | Writer | Contains |
|---|---|---|
| `*.sources.json` | script | Raw Exa API response + metadata sidecar |
| `*.partial.md` | script | Meta + Telemetry (technical, factual) |
| `*.md` (final) | **agent** | Everything above + Sources + Key Findings + Grounding + Limitations + Follow-up |

After the agent writes `.md`, it deletes `.partial.md`.
```

- [ ] **Step 2: Commit**

```bash
git add plugins/h2t-ops/skills/research/REPORT-SPEC.md
git commit -m "feat(h2t-ops:research): add REPORT-SPEC.md with integrity rules"
```

---

## Phase 3: SKILL.md + Command Wrapper

### Task 20: Create `SKILL.md`

**Files:**
- Create: `plugins/h2t-ops/skills/research/SKILL.md`

- [ ] **Step 1: Write file**

```markdown
---
name: research
description: "Semantic web research via Exa API. Modes: fast / generic / news / academic / competitor / people / deep. Transparent telemetry, fail-loud protocol. Use for web search, news tracking, academic papers, competitor intel, people research. NOT for LinkedIn lead-gen (use /search-leads from BayramAnnakov plugin). Triggers: 'research', 'find out', 'look up', 'исследуй', 'h2t:research'."
compatibility: "Requires $EXA_API_KEY env var. Get key at https://dashboard.exa.ai/api-keys. Requires ~/.h2t/venv (run /h2t-core:setup if missing)."
metadata:
  author: lichtpfad
  version: 0.1.0
---

# h2t-ops:research

Semantic research via Exa HTTP API. Transparent (all tool calls visible in main conversation), fail-loud (no silent fallbacks), debug-friendly (telemetry block in every report).

## Architecture

```
User query
    ↓
Step 0: Preflight (env + connectivity)
    ↓
Step 1: Parse request → mode, depth, filters
Step 1b: Check cache → ~/.h2t/research/
    ↓
Step 2: Load systemprompts/{mode}.md
    ↓
Step 3: Call exa_search.py (search / crawl, parallel where possible)
    ↓
Step 4: Fail-loud checks (exit code ≠ 0 → STATUS:DEGRADED)
    ↓
Step 5: Synthesize findings (grounded — URL + quote + confidence)
    ↓
Step 6: Persist (script auto-writes .partial.md + .sources.json)
    ↓
Step 7: Present Output (agent finalises .md per REPORT-SPEC.md)
```

## Файлы скилла

| Файл | Назначение |
|---|---|
| `SKILL.md` | Этот файл — workflow, runtime contract, antipatterns |
| `REPORT-SPEC.md` | Точный формат report markdown |
| `reference.md` | Exa API reference, mode mapping, limitations (lazy-loaded) |
| `examples.md` | CLI invocation examples + output samples |
| `systemprompts/{mode}.md` | 7 готовых systemPrompt templates |
| `scripts/exa_search.py` | Python CLI wrapper (stdlib urllib, no pip) |
| `tests/test_exa_search.py` | pytest suite |

## Выходные файлы

| Файл | Когда | Writer |
|---|---|---|
| `~/.h2t/research/{project}-{slug}-{date}.partial.md` | После HTTP call | script |
| `~/.h2t/research/{project}-{slug}-{date}.sources.json` | После HTTP call | script |
| `~/.h2t/research/{project}-{slug}-{date}.md` | После synthesis | **agent** |
| `~/.h2t/research/.pending_telemetry.jsonl` | When evals unreachable | script |

## Runtime variables (set once at Step 0)

```bash
H2T_PYTHON="${H2T_PYTHON:-}"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/Scripts/python.exe" ] && H2T_PYTHON="$HOME/.h2t/venv/Scripts/python.exe"
[ -z "$H2T_PYTHON" ] && [ -f "$HOME/.h2t/venv/bin/python" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
[ -z "$H2T_PYTHON" ] && echo "ERROR: h2t venv not found. Run /h2t-core:setup" && exit 1

EXA_CLI="$H2T_PYTHON ${CLAUDE_PLUGIN_ROOT}/skills/research/scripts/exa_search.py"
```

## Tool Restriction (critical)

**ONLY use `$EXA_CLI`.** Do NOT use `WebSearch`, `WebFetch`, or direct `curl` as substitutes. If `$EXA_CLI` fails, return `STATUS: DEGRADED` with exact `EXA_ERROR:*` — never silently substitute.

## Workflow

### Step 0: Preflight

```bash
$EXA_CLI preflight
```

Failures:
- Exit 4 + `EXA_ERROR:ENV EXA_API_KEY missing` → tell user to export key, STOP
- Exit 4 + `EXA_ERROR:NETWORK` → api.exa.ai unreachable, STOP

No silent fallback. No WebSearch substitution.

### Step 1: Parse Research Request

Accept natural language OR structured input. Extract:

| Field | Required | Default | Notes |
|---|---|---|---|
| `topic` | yes | — | passed as `--query` |
| `mode` | no | `generic` | one of fast / generic / news / academic / competitor / people / deep |
| `depth` | no | `standard` | shallow (1 call) / standard (search + crawl top-3) / deep (+ deep_reasoning synthesis) |
| `country` | no | — | ISO code, e.g. `CH`, `US` |
| `start_date` / `end_date` | no | — | ISO date (content date filter) |
| `include_domains` / `exclude_domains` | no | — | CSV list; see filter matrix in reference.md |
| `num_results` | no | mode default | override |
| `project` | no | `default` | for output filename prefix |

Ambiguous? Ask ONE clarifying question. Example: user says "research Rejuve.bio" → ask: "Company intel, press coverage, or team research? (competitor / news / people)"

### Step 1b: Check Cached Research

```bash
ls ~/.h2t/research/*{slug}* 2>/dev/null
```

If file < 7 days old exists — show path, ask: *"Use cached or re-search?"*

### Step 2: Load systemPrompt Template

Agent does NOT read `systemprompts/{mode}.md` directly — the script does. Agent just selects `--mode`.

### Step 3: Execute Search (parallel where independent)

```bash
# depth=shallow: one call
$EXA_CLI search --query "..." --mode generic --num-results 5 --project X

# depth=standard/deep: 2–3 query variations in parallel + dedupe
$EXA_CLI search \
  --query "Rejuve.bio Switzerland press 2026" \
  --additional-queries "Swiss longevity startups,DAO biotech 2026" \
  --mode news --start-date 2025-10-01 \
  --num-results 10 --project rejuve

# depth=deep phase 2: parallel crawl top-3 URLs in a single message
$EXA_CLI crawl --url "URL_1" --project X &
$EXA_CLI crawl --url "URL_2" --project X &
$EXA_CLI crawl --url "URL_3" --project X &
wait
```

**Batch independent calls in a single message.** Never sequentialize parallel searches.

### Step 4: Fail-Loud Checks

On any non-zero exit from `$EXA_CLI`:

- Read first stderr line (structured `EXA_ERROR:*`)
- Return `STATUS: DEGRADED` + exact cause + what was attempted
- **Forbidden phrasing:** `"permission blocked"`, `"tool failed"` without specifics
- **Required phrasing:** exact `EXA_ERROR:*` message from stderr

| Exit | Meaning | Action |
|---|---|---|
| 0 | Success | Continue |
| 1 | Args error | Stop, fix invocation |
| 2 | HTTP error (4xx/5xx) | STATUS:DEGRADED, report exact code |
| 3 | Network timeout | STATUS:DEGRADED, suggest retry |
| 4 | Preflight (env/connectivity) | STOP, fix env |

### Step 5: Synthesize Findings

Read script's markdown stdout (title + URL + highlight per result).

**Grounding rule (ALL depths, no exceptions):** every Key Finding MUST have:
- Verbatim quote from highlight (double-quoted string)
- URL to source
- Confidence label: high / medium / low + one-sentence reason

No grounding → not a finding. Move to Limitations or flag as `[research incomplete]`.

### Step 6: Persist (script auto-done)

Script wrote `.partial.md` + `.sources.json`. Agent now reads `.partial.md` and builds final `.md` per `REPORT-SPEC.md`.

### Step 7: Present Output

Write final report to `~/.h2t/research/{project}-{slug}-{date}.md` following REPORT-SPEC.md. Delete `.partial.md` after writing. In main conversation, show:

- Path to saved file
- Summary (top 3 findings as bullets)
- Status label (✅ completed / ⚠ partial / ❌ degraded)
- Telemetry status literal

## Error Handling

| Signal | Reaction |
|---|---|
| User query too vague (e.g. "research stuff") | Ask ONE clarifying question with mode examples |
| User asks "how many results?" Ambiguous | Ask: "10 (default), 5 (quick), or 50 (bulk)?" |
| Exa returns 0 results | Report honestly. Suggest query variations or broader category. Do NOT synthesize from general knowledge. |
| User asks for LinkedIn lead-gen | Route to `/search-leads` (BayramAnnakov plugin, Anysite engine). This skill does Exa only. |
| `.partial.md` missing when writing final | Script failed silently (bug). Re-run search; if still failing, check stderr. |

## Antipatterns

- **Synthesize findings without URL + quote** — violates grounding rule. #69 root cause.
- **Claim `depth=deep` when only `search` was called** — status lying. Integrity check row in telemetry catches this.
- **Hide tool failures** — any non-zero exit code must propagate to Meta.Status.
- **"permission blocked" as diagnosis** — forbidden without evidence of CC permission denial. Use exact `EXA_ERROR:*`.
- **Silent fallback to WebSearch** — script never does this; agent must not either.
- **Parse HTML inline in agent** — script's job. Agent reads cleaned markdown only.
- **Forget to delete `.partial.md`** — leaves stale files. Always `rm .partial.md` after writing final `.md`.

## When to use this skill

✅ "Find companies in longevity space"
✅ "Recent news about AI chip export controls"
✅ "Academic papers on LLM RAG evaluation"
✅ "Who is the CEO of Insilico Medicine?"

❌ "Generate leads for my outbound campaign" → use `/search-leads`
❌ "Monitor Twitter for brand mentions" → use `/search-leads` (Anysite has Twitter)
❌ "Scrape this internal URL" → use WebFetch / Playwright (auth-gated)

## Research Request

$ARGUMENTS
```

- [ ] **Step 2: Commit**

```bash
git add plugins/h2t-ops/skills/research/SKILL.md
git commit -m "feat(h2t-ops:research): add SKILL.md (7-step workflow, fail-loud rules)"
```

---

### Task 21: Create `commands/research.md` slash-command wrapper

**Files:**
- Create: `plugins/h2t-ops/commands/research.md`

- [ ] **Step 1: Write file**

```markdown
---
description: "Semantic web research via Exa. Modes: fast/generic/news/academic/competitor/people/deep. Triggers: 'research', 'find out', 'look up', 'исследуй'."
---

Use the h2t-ops:research skill.
```

- [ ] **Step 2: Verify file format matches existing commands**

```bash
diff \
  <(head -3 plugins/h2t-ops/commands/gmail.md | tr -d '\r') \
  <(head -3 plugins/h2t-ops/commands/research.md | tr -d '\r') \
  || true
```

Both should start with `---\n` frontmatter fence. If diff shows a meaningful difference in structure, adjust.

- [ ] **Step 3: Commit**

```bash
git add plugins/h2t-ops/commands/research.md
git commit -m "feat(h2t-ops): add /research slash-command wrapper"
```

---

## Phase 4: Deprecation + Ecosystem

### Task 22: Replace old `plugins/h2t/agents/research-agent.md` with stub

**Files:**
- Modify: `plugins/h2t/agents/research-agent.md` (replace entire content)

- [ ] **Step 1: Read current file (for audit trail in commit message)**

```bash
wc -l plugins/h2t/agents/research-agent.md
```

Note the line count for the commit message.

- [ ] **Step 2: Replace with stub**

Overwrite file with:

```markdown
---
name: research-agent
description: "DEPRECATED. Use /research (Exa, h2t-ops plugin) for semantic research or /search-leads (Anysite, BayramAnnakov plugin) for LinkedIn lead generation. See lichtpfad/h2t-skills#69 for rationale."
tools:
  - Read
---

# research-agent — DEPRECATED

This agent is deprecated as of 2026-04-18.

## What to use instead

| You want... | Use |
|---|---|
| Web search, news, academic papers, company/people research | `/research` (h2t-ops:research skill, Exa engine) |
| LinkedIn lead generation, ICP-driven prospect lists | `/search-leads` (BayramAnnakov/lead-search plugin, Anysite engine) |
| Instagram, Reddit, Twitter, YouTube scraping | `/search-leads` (covers these via Anysite) |

## Why deprecated

See issue lichtpfad/h2t-skills#69. Root causes:

1. **Silent fallback** — sub-agent silently fell back to WebSearch when Exa MCP tools were not injected into its toolset, then misdiagnosed this as "permission blocked".
2. **Authoritative unsourced synthesis** — agent wrote findings without URL + verbatim quotes, presenting general-knowledge summaries as facts.

Replacement design: `docs/superpowers/specs/2026-04-18-research-skill-architecture-design.md`.

## Do not call this agent

If `Task(subagent_type=research-agent, ...)` is invoked, the caller should stop and switch to the slash commands above. This file exists only as a pointer.
```

- [ ] **Step 3: Commit**

```bash
git add plugins/h2t/agents/research-agent.md
git commit -m "deprecate(h2t): replace research-agent with stub → /research + /search-leads

Issue #69. Preserves Task tool discoverability but redirects callers to
the new h2t-ops:research skill (Exa) and Bayram plugin (Anysite)."
```

---

### Task 23: Append routing rule to `~/.claude/CLAUDE.md`

**Files:**
- Modify: `~/.claude/CLAUDE.md` (user-level, NOT in repo — this is a user action)

- [ ] **Step 1: Check current CLAUDE.md for existing research-related rules**

```bash
grep -n -i "research" ~/.claude/CLAUDE.md || echo "(no matches)"
```

- [ ] **Step 2: Append routing rule**

Append to end of `~/.claude/CLAUDE.md`:

```markdown

## Research routing

Для исследовательских задач — всегда через slash-skills, **никогда** через `general-purpose` agent:

| Задача | Skill |
|---|---|
| Web search, news, academic papers, company/people research | `/research` (h2t-ops:research, Exa engine) |
| LinkedIn lead-gen, ICP-driven prospect lists, Instagram/Reddit/Twitter/YouTube | `/search-leads` (BayramAnnakov/lead-search plugin, Anysite) |

`h2t:research-agent` — **deprecated** (см. lichtpfad/h2t-skills#69). Использование `general-purpose` для research запрещено: он не имеет дисциплины fail-loud protocol и может silent fallback на WebSearch.
```

- [ ] **Step 3: Verify rule visible**

```bash
tail -20 ~/.claude/CLAUDE.md
```

Should show the new section.

- [ ] **Step 4: Note — no git commit**

`~/.claude/CLAUDE.md` is outside the repo. Nothing to commit. Just make sure the file is saved.

---

### Task 24: Install Anysite MCP + Bayram plugin (user actions)

**Files:** (none — user shell actions)

- [ ] **Step 1: Install Anysite MCP on user scope**

The user runs:

```bash
claude mcp add --transport http --scope user anysite "https://mcp.anysite.io/mcp?api_key=YOUR_ANYSITE_KEY"
```

After this, restart Claude Code so the MCP is loaded.

- [ ] **Step 2: Verify MCP is configured**

```bash
grep -A3 '"anysite"' ~/.claude.json | head -5
```

Expected: shows `"type": "http"` and `"url":` with `mcp.anysite.io`.

- [ ] **Step 3: Install BayramAnnakov lead-search plugin**

In a Claude Code session:

```
/plugin marketplace add BayramAnnakov/lead-search-plugin
/plugin install lead-search@lead-search-marketplace
```

- [ ] **Step 4: Verify Bayram command registered**

After plugin install, in a new Claude Code session:

```
/search-leads --help
```

Expected: Bayram plugin responds (its skill loads and asks for ICP). If `/search-leads` is not recognized, plugin install didn't take effect — retry install + restart.

- [ ] **Step 5: Note — no git commit**

These are user-level configurations outside the repo.

---

## Phase 5: Smoke Tests (manual verification before calling it done)

### Task 25: Smoke test — preflight passes

**Files:** (none — terminal run)

- [ ] **Step 1: Export API key (if not already exported)**

```bash
export EXA_API_KEY=<your-key>
```

- [ ] **Step 2: Resolve H2T_PYTHON + EXA_CLI**

```bash
H2T_PYTHON="${H2T_PYTHON:-$HOME/.h2t/venv/Scripts/python.exe}"
[ ! -f "$H2T_PYTHON" ] && H2T_PYTHON="$HOME/.h2t/venv/bin/python"
EXA_CLI="$H2T_PYTHON $PWD/plugins/h2t-ops/skills/research/scripts/exa_search.py"
```

- [ ] **Step 3: Run preflight**

```bash
$EXA_CLI preflight
```

Expected: stdout prints `OK`, exit code 0.

If `EXA_ERROR:ENV` — fix `$EXA_API_KEY`.
If `EXA_ERROR:NETWORK` — check firewall/proxy; retry.

- [ ] **Step 4: No commit (verification only)**

---

### Task 26: Smoke test — real generic search

**Files:** (none — terminal run, real API call costs ~$0.007)

- [ ] **Step 1: Run generic search**

```bash
$EXA_CLI search \
  --query "What is Exa AI and who founded it?" \
  --mode generic \
  --num-results 5 \
  --output-dir /tmp/h2t-research-smoke \
  --project smoke-test
```

Expected:
- Exit code 0
- Stdout shows `## Exa Search: ...` with 5 numbered results, each with URL + highlight snippet
- Stdout ends with `Saved:` and `JSON:` pointing to `/tmp/h2t-research-smoke/`

- [ ] **Step 2: Verify files created**

```bash
ls -la /tmp/h2t-research-smoke/
cat /tmp/h2t-research-smoke/smoke-test-*.partial.md | head -40
```

Expected: two files (`.partial.md` and `.sources.json`). The `.partial.md` has Meta + Telemetry tables with real cost/latency numbers and the `Integrity check: 1/1 calls used Exa API. 0 fallbacks to WebSearch.` row.

- [ ] **Step 3: No commit**

---

### Task 27: Smoke test — invalid combination fails correctly

**Files:** (none — terminal run, zero cost since script exits before HTTP)

- [ ] **Step 1: Run invalid combination**

```bash
$EXA_CLI search \
  --query "x" \
  --mode competitor \
  --start-date 2025-01-01 \
  --output-dir /tmp/h2t-research-smoke \
  --project smoke-test \
  2>&1 | tee /tmp/exa-invalid.log
echo "exit=$?"
```

Expected:
- Exit code 1
- Stderr (captured in log): `EXA_ERROR:ARGS mode=competitor (category=company) incompatible with --start-date.`
- Suggests switching to `--mode news` or `generic`

- [ ] **Step 2: Verify no files written for this failed run**

```bash
ls /tmp/h2t-research-smoke/ | wc -l
```

Expected: same file count as after Task 26 (no new files — fail-fast prevented output).

- [ ] **Step 3: Cleanup smoke test artifacts**

```bash
rm -rf /tmp/h2t-research-smoke /tmp/exa-invalid.log
```

- [ ] **Step 4: No commit**

---

### Task 28: Smoke test — /research slash command end-to-end

**Files:** (none — inside Claude Code session)

- [ ] **Step 1: Reload plugin (to pick up new commands/research.md)**

In Claude Code:

```
/plugin
```

Or restart Claude Code. Verify `h2t-ops:research` skill appears in the skills list and `/research` command is recognized.

- [ ] **Step 2: Invoke /research**

```
/research Что такое Exa AI и кто основатели компании?
```

Expected agent behaviour:
1. Runs Step 0 preflight.
2. Parses mode (probably `generic`), depth (`standard`).
3. Calls `$EXA_CLI search` with the query.
4. Reads `.partial.md` and `.sources.json` from `~/.h2t/research/`.
5. Writes final `.md` per REPORT-SPEC.md (Meta + Telemetry + Sources + Key Findings with grounded quotes + Grounding Notes + Limitations + Follow-up).
6. Deletes `.partial.md`.
7. In conversation: summary + path.

- [ ] **Step 3: Open the final report and audit it**

```bash
cat ~/.h2t/research/*exa-ai*$(date +%Y-%m-%d)*.md
```

Verify:
- **Meta table** has Mode, Depth, Engine=Exa, Status=✅ completed
- **Telemetry table** shows `exa_search.py search` call with real HTTP 200 + cost
- **Integrity check row** reads `1/1 calls used Exa API. 0 fallbacks to WebSearch.`
- Every **Key Finding** has a verbatim double-quoted excerpt AND a URL AND a confidence label
- **Grounding Notes** shows `Sources from WebSearch / other: 0`
- Footer shows `Telemetry: 🚧 awaiting endpoint` (if `$H2T_EVALS_URL` not set) OR `⏳ buffered locally` (if set but unreachable)

If any of these checks fail, the SKILL.md needs adjustment — refer to spec §4 Step 5 and REPORT-SPEC.md.

- [ ] **Step 4: No commit (verification only)**

---

## Phase 6: Plugin Version Bump

### Task 29: Bump h2t-ops plugin version

**Files:**
- Modify: `plugins/h2t-ops/.claude-plugin/plugin.json`

- [ ] **Step 1: Read current version**

```bash
cat plugins/h2t-ops/.claude-plugin/plugin.json
```

- [ ] **Step 2: Bump patch version**

Increment the `version` field in the JSON (e.g. `"1.2.3"` → `"1.2.4"`). Only the patch number changes — this is a feature addition validated in smoke tests but not yet proven in production, per the user's semver rule in global CLAUDE.md (minor bumps only after live confirmation).

Example edit using the Edit tool (replace old version string with new one verbatim).

- [ ] **Step 3: Commit**

```bash
git add plugins/h2t-ops/.claude-plugin/plugin.json
git commit -m "chore(h2t-ops): bump version for research skill + /research command"
```

---

### Task 30: Close issue #69 with summary comment

**Files:** (GitHub — no local file changes)

- [ ] **Step 1: Post completion comment**

```bash
gh issue comment 69 --repo lichtpfad/h2t-skills --body "$(cat <<'EOF'
## Implementation complete

**Spec:** `docs/superpowers/specs/2026-04-18-research-skill-architecture-design.md`
**Plan:** `docs/superpowers/plans/2026-04-18-research-skill-implementation.md`

### What shipped

- `plugins/h2t-ops/skills/research/` — new skill: SKILL.md, REPORT-SPEC.md, reference.md, examples.md, 7 systemprompts, scripts/exa_search.py + tests
- `plugins/h2t-ops/commands/research.md` — slash-command wrapper
- `plugins/h2t/agents/research-agent.md` — replaced with deprecation stub
- `~/.claude/CLAUDE.md` — routing rule added (research → /research or /search-leads, never general-purpose)

### Anti-silent-fallback mechanics

1. Script has no WebSearch code path — physically cannot fallback
2. Structured `EXA_ERROR:*` stderr + typed exit codes (1/2/3/4)
3. SKILL.md Tool Restriction forbids WebSearch/WebFetch substitution
4. REPORT-SPEC Integrity check row (`N/N calls used Exa API. 0 fallbacks`) catches drift
5. Grounding rule (verbatim quote + URL + confidence per finding, all depths) blocks unsourced synthesis

### Smoke tests passed

- Preflight OK (~5ms)
- Generic search — real HTTP 200 + valid report + grounded findings
- Invalid combo (competitor + date filter) — fail-fast exit 1 with actionable message

### Deferred to v0.2

- `context: fork` variant (`/research-deep` for heavy parallel research)
- `/research --eval <dataset>` for benchmark-style evaluation
- h2t-evals endpoint integration (schema + auth contract — currently buffered to .pending_telemetry.jsonl)
EOF
)"
```

- [ ] **Step 2: Close issue**

```bash
gh issue close 69 --repo lichtpfad/h2t-skills --reason completed
```

- [ ] **Step 3: No commit (GitHub action only)**

---

## Self-Review Results

**Spec coverage check:**
- §1 Context/Root Cause → referenced in Task 22 (stub) + Task 30 (issue close)
- §2 Architecture (engine-split, curl not MCP, inline not fork) → Tasks 16–21, SKILL.md/scripts
- §3 File layout → Tasks 1, 16–21 + Task 23 (CLAUDE.md)
- §4 Workflow (7 steps) → covered in SKILL.md (Task 20)
- §5 exa_search.py spec → Tasks 1–15
- §6 Exa API surface scope → reference.md (Task 17)
- §7 supporting files → Tasks 16–18
- §8 REPORT-SPEC.md → Task 19
- §9 Telemetry (technical + semantic) → Task 12 + SKILL.md Step 7 + telemetry footer in REPORT-SPEC
- §10 Testing → every Phase 1 task has test-first steps
- §11 Migration → Phase 4 (Tasks 22–24) + Phase 5 (Tasks 25–28)
- §12 Gershuni practices → architecture diagram + file tables + antipatterns in SKILL.md
- §12a Exa official patterns → Tool Restriction + Query variation + filter matrix + etc. all in SKILL.md + reference.md
- §13 Antipatterns → SKILL.md (Task 20)
- §14 Open questions → telemetry status `🚧 awaiting endpoint` default, Bayram install path documented, Anysite key in user scope

**Placeholder scan:**
No "TBD" / "TODO" / "implement later" / "similar to Task N" / vague "add error handling" in any step. Every step has either: a concrete test/code block, an exact shell command with expected output, or a complete file content.

**Type consistency check:**
- `MODE_CONFIG` structure consistent across Task 2 definition and Tasks 5, 7, 14 consumption.
- `CATEGORY_BLOCKS` consistent across Task 3 definition and Task 5 usage.
- `die(code, msg)` signature stable across Tasks 4, 5, 8, 9, 14, 15.
- `call_exa(endpoint, body, api_key, timeout)` → `(status, body, latency_ms)` stable across Tasks 8, 9, 14, 15.
- `output_paths(output_dir, project, topic, date)` → dict keys `{partial_md, final_md, sources_json}` stable across Tasks 10, 14, 15.
- `post_telemetry(event, buffer_path)` → status literal stable across Tasks 12, 14, 15.
- `MODES` list (`list(MODE_CONFIG.keys())`) used in argparse choices — consistent with Task 2 keys.

No mismatches detected.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-18-research-skill-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
