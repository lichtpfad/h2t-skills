---
title: "Cross-repo practice harvest"
status: "draft"
date: "2026-07-10"
milestone: ""
issue: ""
---

# Cross-repo practice harvest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Собрать golden-source корпус за окно [2026-06-10 … 2026-07-10] детерминированным агрегатором, синтезировать реестр повторяющихся практик (два трека, ось recurrence×domain-independence, diff против существующих стандартов) и выдать черновые предложения гайдбуков в `docs/standards/`.

**Architecture:** Гибрид. Фаза A — детерминированный Python-пакет `lib/practice_harvest/` (TDD, тестируемый: lineage-collapse → сбор источников → dedup → эмиссия `corpus.json`). Фаза B — интерпретативный синтез поверх `corpus.json`, чей *выход* (`registry.json`) проверяется sealed-валидатором `validate_registry.py` (паттерн из h2t-core autonomous-run: не-кодовый артефакт держится детерминированной схемой + проверкой существования source-path).

**Tech Stack:** Python stdlib (pathlib, json, hashlib, re, datetime), pytest. Никаких внешних зависимостей, без Node, без Workflow/агентов (корпус ≈ сотни КБ).

**Spec:** `docs/superpowers/specs/2026-07-10-cross-repo-practice-harvest.md`

---

## File Structure

| Файл | Ответственность |
|---|---|
| `lib/practice_harvest/__init__.py` | пакет-маркер |
| `lib/practice_harvest/lineage.py` | fork/worktree → canonical lineage (§1 нормализация) |
| `lib/practice_harvest/session_parse.py` | парсинг markdown-секций session-md |
| `lib/practice_harvest/collect.py` | сбор источников в окне + классификация kind/track |
| `lib/practice_harvest/build_index.py` | CLI: dedup + эмиссия `corpus.json` |
| `lib/practice_harvest/validate_registry.py` | sealed-валидатор реестра синтеза |
| `lib/practice_harvest/render_registry.py` | `registry.json` → человекочитаемый `.md` |
| `tests/practice_harvest/` | pytest для всех детерминированных модулей |
| `docs/reports/2026-07-10-practice-harvest-corpus.json` | выход фазы A (артефакт, gitignored — сырьё) |
| `docs/reports/2026-07-10-practice-harvest-registry.{json,md}` | выход фазы B (канон, в git) |
| `docs/reports/proposed-standards/*.md` | черновые гайдбуки для оператора |

Разделение путей источников (важно): **rules / CLAUDE.md / memory = текущий снимок** (что закристаллизовано *сейчас*); **session-md / specs / plans = mtime в окне** (активность за месяц).

Все команды из корня `C:/dev/h2t-skills`. Python: `C:/dev/h2t-skills/.venv/Scripts/python`, pytest: `C:/dev/h2t-skills/.venv/Scripts/pytest`.

---

### Task 1: Lineage canonicalization

**Files:**
- Modify: `pyproject.toml` (pytest pythonpath — упрочнить импорт `lib.*`)
- Create: `lib/practice_harvest/__init__.py`
- Create: `lib/practice_harvest/lineage.py`
- Test: `tests/practice_harvest/test_lineage.py`

- [ ] **Step 0: Гарантировать импорт `lib.*` под pytest**

Проверить `pyproject.toml` на секцию `[tool.pytest.ini_options]`. Если `pythonpath` не задан — добавить (иначе резолв `lib.practice_harvest` зависит от editable-venv, codex P2):
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```
Если секция уже есть с другими ключами — добавить `pythonpath = ["."]`, не трогая остальное. (Эмпирически импорт работает и через rootdir-insertion, но явный pythonpath убирает завязку на окружение.)

- [ ] **Step 1: Write the failing test**

```python
# tests/practice_harvest/test_lineage.py
from lib.practice_harvest.lineage import canonical_lineage

def test_crypto_variants_collapse():
    assert canonical_lineage("crypto-regime-spike-dmde") == "crypto-regime-spike"
    assert canonical_lineage("crypto-regime-test") == "crypto-regime-spike"
    assert canonical_lineage("crypto-regime-spike") == "crypto-regime-spike"

def test_h2t_skills_variants_collapse():
    assert canonical_lineage("agent-skills") == "h2t-skills"
    assert canonical_lineage("h2t-skills-119-editorial-pilot") == "h2t-skills"
    assert canonical_lineage("h2t-skills-editorial-wireframe") == "h2t-skills"

def test_memory_project_bucket_collapses():
    # ~/.claude/projects/C--dev-h2t-skills/memory → h2t-skills, не отдельный lineage
    assert canonical_lineage("C--dev-h2t-skills") == "h2t-skills"

def test_unknown_passthrough():
    assert canonical_lineage("quant-kb") == "quant-kb"
    assert canonical_lineage("rejuve") == "rejuve"

def test_worktree_path_collapses():
    # директории worktree тоже сворачиваются к родителю
    assert canonical_lineage("h2t-skills/.worktrees/pre-release-audit") == "h2t-skills"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/test_lineage.py -v`
Expected: FAIL — `ModuleNotFoundError: lib.practice_harvest.lineage`

- [ ] **Step 3: Write minimal implementation**

```python
# lib/practice_harvest/lineage.py
"""Свернуть форки/worktree/переименования проектов к каноничному lineage.

Справочник ведётся вручную; ревьюится оператором до синтеза (спец §Boundaries).
Новый форк без записи здесь → риск инфляции recurrence.
"""
from __future__ import annotations

# canonical -> список variant-имён (директорий проектов / session-папок)
LINEAGE_MAP: dict[str, list[str]] = {
    "crypto-regime-spike": [
        "crypto-regime-spike-dmde",
        "crypto-regime-test",
    ],
    "h2t-skills": [
        "agent-skills",
        "h2t-skills-119-editorial-pilot",
        "h2t-skills-editorial-wireframe",
        "C--dev-h2t-skills",  # ~/.claude/projects/<slug>/memory bucket name
    ],
}

# обратный индекс variant -> canonical
_VARIANT_TO_CANON = {
    variant: canon
    for canon, variants in LINEAGE_MAP.items()
    for variant in variants
}


def canonical_lineage(name: str) -> str:
    """Вернуть каноничное имя lineage для проекта/пути.

    Сворачивает: worktree-подпути (берётся первый сегмент до '/'),
    известные варианты форков, иначе passthrough.
    """
    head = name.replace("\\", "/").split("/", 1)[0].strip()
    return _VARIANT_TO_CANON.get(head, head)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/test_lineage.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add lib/practice_harvest/__init__.py lib/practice_harvest/lineage.py tests/practice_harvest/test_lineage.py
git commit -m "feat(practice-harvest): lineage canonicalization (fork/worktree collapse)"
```

---

### Task 2: session-md parser

**Files:**
- Create: `lib/practice_harvest/session_parse.py`
- Test: `tests/practice_harvest/test_session_parse.py`

session-md формат — markdown-секции (`## Meta` с `- **Date:**`, `## What Was Done`, `## What Remains`, `## Artifacts`), НЕ YAML. Используется в Task 5 (`build_corpus` берёт только `what_done`+`what_remains`, отбрасывая шум Meta/Artifacts).

- [ ] **Step 1: Write the failing test**

```python
# tests/practice_harvest/test_session_parse.py
from lib.practice_harvest.session_parse import parse_session_md

SAMPLE = """# Session: dev-h2t-skills-demo-2026-07-01

## Meta
- **Date:** 2026-07-01
- **Domain:** dev
- **Project:** h2t-skills

## What Was Done
- Сделал A.
- Сделал B.

## What Remains
- [ ] Осталось C.

## Artifacts
- commit: abc1234
"""

def test_parses_meta_and_sections():
    r = parse_session_md(SAMPLE)
    assert r["date"] == "2026-07-01"
    assert r["project"] == "h2t-skills"
    assert r["what_done"] == ["Сделал A.", "Сделал B."]
    assert r["what_remains"] == ["Осталось C."]

def test_missing_section_yields_empty():
    r = parse_session_md("# Session: x\n\n## Meta\n- **Project:** quant-kb\n")
    assert r["project"] == "quant-kb"
    assert r["what_done"] == []
    assert r["date"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/test_session_parse.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# lib/practice_harvest/session_parse.py
"""Парсинг markdown-секций session-md в структуру."""
from __future__ import annotations
import re

_META_RE = re.compile(r"^- \*\*(?P<key>[^:*]+):\*\*\s*(?P<val>.+?)\s*$", re.M)


def _section_bullets(text: str, header: str) -> list[str]:
    """Bullets ('- ...') под заголовком '## <header>' до следующего '## '."""
    m = re.search(rf"^##\s+{re.escape(header)}\s*$", text, re.M)
    if not m:
        return []
    rest = text[m.end():]
    nxt = re.search(r"^##\s+", rest, re.M)
    body = rest[: nxt.start()] if nxt else rest
    out = []
    for line in body.splitlines():
        s = line.strip()
        # снять '- ' и checkbox-префикс '- [ ] ' / '- [x] '
        m2 = re.match(r"^-\s+(?:\[[ xX]\]\s+)?(.*)$", s)
        if m2 and m2.group(1):
            out.append(m2.group(1).strip())
    return out


def parse_session_md(text: str) -> dict:
    meta = {k.strip().lower(): v.strip() for k, v in _META_RE.findall(text)}
    return {
        "date": meta.get("date", ""),
        "domain": meta.get("domain", ""),
        "project": meta.get("project", ""),
        "what_done": _section_bullets(text, "What Was Done"),
        "what_remains": _section_bullets(text, "What Remains"),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/test_session_parse.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add lib/practice_harvest/session_parse.py tests/practice_harvest/test_session_parse.py
git commit -m "feat(practice-harvest): session-md section parser"
```

---

### Task 3: Source collection + window + classification

**Files:**
- Create: `lib/practice_harvest/collect.py`
- Test: `tests/practice_harvest/test_collect.py`

Собирает источники в `SourceRecord`-ы. Классификация `kind` → `track`:
`rules`/`claude_md` → process; `session`/`spec`/`plan` → technical; `memory` → both.
Окно применяется только к mtime-источникам (session/spec/plan); rules/claude_md/memory — текущий снимок.

- [ ] **Step 1: Write the failing test**

```python
# tests/practice_harvest/test_collect.py
from pathlib import Path
from lib.practice_harvest.collect import classify_kind, track_for_kind, SourceRecord

def test_classify_kind():
    assert classify_kind(Path("x/.claude/rules/git.md")) == "rules"
    assert classify_kind(Path("x/CLAUDE.md")) == "claude_md"
    assert classify_kind(Path("x/docs/superpowers/specs/y.md")) == "spec"
    assert classify_kind(Path("x/docs/superpowers/plans/y.md")) == "plan"
    assert classify_kind(Path("mem/memory/feedback_x.md")) == "memory"
    assert classify_kind(Path("sessions/AUTOMATA/h2t-skills/s.md")) == "session"

def test_documentation_md_excluded():
    # синхронный шаблон — не находка
    assert classify_kind(Path("x/.claude/rules/documentation.md")) is None

def test_track_mapping():
    assert track_for_kind("rules") == "process"
    assert track_for_kind("spec") == "technical"
    assert track_for_kind("memory") == "both"

def test_record_carries_lineage(tmp_path):
    f = tmp_path / "CLAUDE.md"
    f.write_text("# hi", encoding="utf-8")
    rec = SourceRecord.from_path(f, lineage="quant-kb", kind="claude_md")
    assert rec.lineage == "quant-kb"
    assert rec.track == "process"
    assert rec.text == "# hi"
    assert rec.path.endswith("CLAUDE.md")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/test_collect.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# lib/practice_harvest/collect.py
"""Сбор источников корпуса с привязкой к файлу, lineage, kind, track."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

# kind -> track
_TRACK = {
    "rules": "process",
    "claude_md": "process",
    "session": "technical",
    "spec": "technical",
    "plan": "technical",
    "memory": "both",
}


def track_for_kind(kind: str) -> str:
    return _TRACK[kind]


def classify_kind(path: Path) -> str | None:
    """Определить kind по пути; None → исключить из корпуса."""
    p = path.as_posix()
    name = path.name
    if name == "documentation.md":
        return None  # синхронный шаблон
    if "/.claude/rules/" in p:
        return "rules"
    if name == "CLAUDE.md":
        return "claude_md"
    if "/docs/superpowers/specs/" in p:
        return "spec"
    if "/docs/superpowers/plans/" in p:
        return "plan"
    if "/memory/" in p:
        return "memory"
    if "/sessions/" in p and name.endswith(".md") and name != "latest.json":
        return "session"
    return None


@dataclass
class SourceRecord:
    path: str
    lineage: str
    kind: str
    track: str
    text: str

    @classmethod
    def from_path(cls, path: Path, lineage: str, kind: str) -> "SourceRecord":
        return cls(
            path=path.as_posix(),
            lineage=lineage,
            kind=kind,
            track=track_for_kind(kind),
            text=path.read_text(encoding="utf-8", errors="replace"),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/test_collect.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add lib/practice_harvest/collect.py tests/practice_harvest/test_collect.py
git commit -m "feat(practice-harvest): source collection + kind/track classification"
```

---

### Task 4: Dedup across lineage

**Files:**
- Modify: `lib/practice_harvest/collect.py` (добавить `dedup_records`)
- Test: `tests/practice_harvest/test_dedup.py`

Идентичные rule-файлы, размноженные форками, — один источник после collapse. Dedup по `(canonical_lineage, kind, content-hash)`: если один и тот же контент уже учтён для того же lineage — отбросить дубль.

**Dedup = exact (sha256) + fork-collapse; near-dup (MinHash/shingling) сознательно отложен.** Спека §5 облегчает анти-галлюц-аппарат; near-dup — как раз тяжёлая часть. Для rules/session-корпуса реальные дубли — это клоны форков (ловятся exact+collapse) либо содержательно разные файлы. near-dup вводить только если реальный корпус покажет near-дубли (YAGNI). Расхождение со спекой §5 («exact + near-dup») устранено правкой спеки в этом же прогоне (Decision-log runbook).

- [ ] **Step 1: Write the failing test**

```python
# tests/practice_harvest/test_dedup.py
from lib.practice_harvest.collect import SourceRecord, dedup_records

def _rec(path, lineage, text):
    return SourceRecord(path=path, lineage=lineage, kind="rules",
                        track="process", text=text)

def test_identical_content_same_lineage_collapses():
    recs = [
        _rec("crypto-regime-spike/.claude/rules/git.md", "crypto-regime-spike", "RULE"),
        _rec("crypto-regime-spike-dmde/.claude/rules/git.md", "crypto-regime-spike", "RULE"),
    ]
    out = dedup_records(recs)
    assert len(out) == 1

def test_different_content_kept():
    recs = [
        _rec("a/.claude/rules/git.md", "a", "RULE-A"),
        _rec("b/.claude/rules/git.md", "b", "RULE-B"),
    ]
    assert len(dedup_records(recs)) == 2

def test_same_content_different_lineage_kept():
    # одинаковый текст в РАЗНЫХ lineage = реальный кросс-repo сигнал, не дубль
    recs = [
        _rec("a/.claude/rules/git.md", "a", "RULE"),
        _rec("b/.claude/rules/git.md", "b", "RULE"),
    ]
    assert len(dedup_records(recs)) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/test_dedup.py -v`
Expected: FAIL — `ImportError: cannot import name 'dedup_records'`

- [ ] **Step 3: Write minimal implementation**

```python
# добавить в lib/practice_harvest/collect.py
import hashlib


def dedup_records(records: list["SourceRecord"]) -> list["SourceRecord"]:
    """Отбросить дубли (canonical_lineage, kind, content-hash).

    Одинаковый контент в одном lineage (клон форка) → один.
    Одинаковый контент в разных lineage → оба (реальный кросс-repo сигнал).
    """
    seen: set[tuple[str, str, str]] = set()
    out: list[SourceRecord] = []
    for r in records:
        h = hashlib.sha256(r.text.encode("utf-8")).hexdigest()
        key = (r.lineage, r.kind, h)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/test_dedup.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add lib/practice_harvest/collect.py tests/practice_harvest/test_dedup.py
git commit -m "feat(practice-harvest): dedup identical rule files within lineage"
```

---

### Task 5: Corpus index CLI

**Files:**
- Create: `lib/practice_harvest/build_index.py`
- Test: `tests/practice_harvest/test_build_index.py`

CLI обходит реальные корни, собирает `SourceRecord`-ы, dedup, пишет `corpus.json`:
`{"window": [...], "lineage_counts": {...}, "records": [{path,lineage,kind,track,text}]}`.
Корни и окно — аргументы (для тестируемости на фикстурах). session/spec/plan фильтруются по mtime в окне; rules/claude_md/memory берутся как снимок.

- [ ] **Step 1: Write the failing test**

```python
# tests/practice_harvest/test_build_index.py
import json
from pathlib import Path
from lib.practice_harvest.build_index import build_corpus

def _touch(p: Path, text="x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

def test_build_corpus_collects_and_counts(tmp_path):
    # repo A: rules + documentation (excluded)
    _touch(tmp_path / "repoA/.claude/rules/git.md", "GIT")
    _touch(tmp_path / "repoA/.claude/rules/documentation.md", "TEMPLATE")
    _touch(tmp_path / "repoA/CLAUDE.md", "CA")
    # repo-форк A': тот же git.md -> должен схлопнуться в lineage repoA через map
    corpus = build_corpus(
        repo_roots=[tmp_path / "repoA"],
        session_roots=[],
        memory_roots=[],
        lineage_of=lambda name: "repoA",
    )
    kinds = sorted(r["kind"] for r in corpus["records"])
    assert kinds == ["claude_md", "rules"]  # documentation.md исключён
    assert corpus["lineage_counts"]["repoA"] >= 1
    assert all("text" in r and "path" in r for r in corpus["records"])

def test_session_text_stripped_to_meaningful_sections(tmp_path):
    md = ("# Session: s\n\n## Meta\n- **Project:** repoA\n"
          "## What Was Done\n- Did X.\n## Artifacts\n- commit: abc\n")
    sess = tmp_path / "sessions/AUTOMATA/repoA/s.md"
    _touch(sess, md)
    corpus = build_corpus(
        repo_roots=[], memory_roots=[],
        session_roots=[tmp_path / "sessions/AUTOMATA"],
        lineage_of=lambda name: "repoA",
        start="2000-01-01", end="2100-01-01",  # окно заведомо покрывает mtime
    )
    rec = next(r for r in corpus["records"] if r["kind"] == "session")
    assert rec["text"] == "Did X."          # только What Was Done
    assert "commit" not in rec["text"]      # Artifacts/Meta отброшены
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/test_build_index.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# lib/practice_harvest/build_index.py
"""Собрать корпус из реальных корней и записать corpus.json."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from lib.practice_harvest.collect import (
    SourceRecord, classify_kind, dedup_records, track_for_kind,
)
from lib.practice_harvest.lineage import canonical_lineage
from lib.practice_harvest.session_parse import parse_session_md

WINDOW_START = "2026-06-10"
WINDOW_END = "2026-07-10"
_MTIME_KINDS = {"session", "spec", "plan"}


def _in_window(path: Path, start: str, end: str) -> bool:
    mt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date()
    return start <= mt.isoformat() <= end


def build_corpus(
    repo_roots: list[Path],
    session_roots: list[Path],
    memory_roots: list[Path],
    lineage_of: Callable[[str], str] = canonical_lineage,
    start: str = WINDOW_START,
    end: str = WINDOW_END,
) -> dict:
    records: list[SourceRecord] = []

    def add(path: Path, lineage: str):
        if not path.is_file():
            return  # опциональный файл (напр. репо без CLAUDE.md) — тихо пропустить
        kind = classify_kind(path)
        if kind is None:
            return
        if kind in _MTIME_KINDS and not _in_window(path, start, end):
            return
        if kind == "session":
            # session-md шумный: оставляем только смысловые секции
            parsed = parse_session_md(path.read_text(encoding="utf-8", errors="replace"))
            text = "\n".join(parsed["what_done"] + parsed["what_remains"])
            records.append(SourceRecord(path=path.as_posix(), lineage=lineage,
                                        kind=kind, track=track_for_kind(kind), text=text))
            return
        records.append(SourceRecord.from_path(path, lineage, kind))

    # repo snapshot: только целевые пути (точечно, без широкого rglob —
    # иначе подхватятся вложенные CLAUDE.md/.claude/rules из vendor/docs; codex P2)
    for root in repo_roots:
        if not root.is_dir():
            raise FileNotFoundError(f"repo-root missing: {root}")
        lineage = lineage_of(root.name)
        rules_dir = root / ".claude" / "rules"
        if rules_dir.is_dir():
            for f in rules_dir.glob("*.md"):
                add(f, lineage)
        add(root / "CLAUDE.md", lineage)  # add() пропустит, если файла нет
        for sub in ("specs", "plans"):
            d = root / "docs" / "superpowers" / sub
            if d.is_dir():
                for f in d.glob("*.md"):
                    add(f, lineage)

    # sessions: <root>/<project>/*.md
    for root in session_roots:
        if not root.is_dir():
            raise FileNotFoundError(f"session-root missing: {root}")
        for f in root.rglob("*.md"):
            project = f.parent.name
            add(f, lineage_of(project))

    # memory: <root>/*.md (кроме MEMORY.md-индекса); lineage из имени бакета
    # (напр. C--dev-h2t-skills → h2t-skills через LINEAGE_MAP, codex P1)
    for root in memory_roots:
        if not root.is_dir():
            raise FileNotFoundError(f"memory-root missing: {root}")
        for f in root.glob("*.md"):
            if f.name == "MEMORY.md":
                continue
            add(f, lineage_of(root.parent.name))

    records = dedup_records(records)
    counts = Counter(r.lineage for r in records)
    return {
        "window": [start, end],
        "lineage_counts": dict(counts),
        "records": [r.__dict__ for r in records],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/reports/2026-07-10-practice-harvest-corpus.json")
    ap.add_argument("--repo-root", action="append", default=[], type=Path)
    ap.add_argument("--session-root", action="append", default=[], type=Path)
    ap.add_argument("--memory-root", action="append", default=[], type=Path)
    args = ap.parse_args()
    corpus = build_corpus(args.repo_root, args.session_root, args.memory_root)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"corpus: {len(corpus['records'])} records across "
          f"{len(corpus['lineage_counts'])} lineages -> {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/test_build_index.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Gitignore the raw corpus artifact**

Add to `.gitignore`:
```
docs/reports/*-practice-harvest-corpus.json
```

- [ ] **Step 6: Commit**

```bash
git add lib/practice_harvest/build_index.py tests/practice_harvest/test_build_index.py .gitignore
git commit -m "feat(practice-harvest): corpus index CLI (build_corpus + gitignore raw)"
```

---

### Task 6: Registry sealed-validator

**Files:**
- Create: `lib/practice_harvest/validate_registry.py`
- Test: `tests/practice_harvest/test_validate_registry.py`

Валидатор — гейт для интерпретативного выхода фазы B. Схема одной находки:
`practice, track∈{process,technical}, lineage_sources[≥1], recurrence:int≥1,
domain_independence∈{high,medium,low}, current_location, lift_verdict, source_paths[≥1]`.
`lift_verdict` ∈ `{new-standard, append:<file>, skip, deferred:code, deferred:skill}`.
Каждый `source_paths[i]` ДОЛЖЕН существовать на диске (проверяемость факта «практика в файле Y»).
Registry-уровень: опциональный `examined_no_lift: [lineage,…]` — lineage, просмотренные,
но не давшие находок (для coverage-гейта). `validate_coverage` требует, чтобы КАЖДЫЙ
lineage корпуса был либо в `finding.lineage_sources`, либо в `examined_no_lift` — иначе
синтез неполон (форм-валидатор один этого не ловит).

- [ ] **Step 1: Write the failing test**

```python
# tests/practice_harvest/test_validate_registry.py
import pytest
from lib.practice_harvest.validate_registry import (
    validate_finding, validate_coverage, ValidationError,
)

def _ok(tmp_path):
    f = tmp_path / "rule.md"
    f.write_text("x", encoding="utf-8")
    return {
        "practice": "codex second-opinion gate",
        "track": "process",
        "lineage_sources": ["quant-kb"],
        "recurrence": 1,
        "domain_independence": "high",
        "current_location": "quant-kb/.claude/rules/codex-review.md",
        "lift_verdict": "new-standard",
        "source_paths": [str(f)],
    }

def test_valid_finding_passes(tmp_path):
    validate_finding(_ok(tmp_path))  # no raise

def test_bad_track_rejected(tmp_path):
    f = _ok(tmp_path); f["track"] = "hybrid"
    with pytest.raises(ValidationError):
        validate_finding(f)

def test_bad_verdict_rejected(tmp_path):
    f = _ok(tmp_path); f["lift_verdict"] = "maybe"
    with pytest.raises(ValidationError):
        validate_finding(f)

def test_missing_source_path_on_disk_rejected(tmp_path):
    f = _ok(tmp_path); f["source_paths"] = [str(tmp_path / "nope.md")]
    with pytest.raises(ValidationError):
        validate_finding(f)

def test_recurrence_must_match_unique_lineage(tmp_path):
    # recurrence врёт: 3, но уникальный lineage один
    f = _ok(tmp_path); f["recurrence"] = 3; f["lineage_sources"] = ["quant-kb"]
    with pytest.raises(ValidationError):
        validate_finding(f)

def test_append_verdict_with_target_ok(tmp_path):
    f = _ok(tmp_path); f["lift_verdict"] = "append:git-naming-conventions.md"
    validate_finding(f)  # no raise

def test_coverage_all_lineages_accounted_passes():
    # каждый lineage корпуса покрыт: либо в finding, либо в examined_no_lift
    corpus = {"lineage_counts": {"quant-kb": 3, "rejuve": 5}}
    registry = {
        "findings": [{"lineage_sources": ["quant-kb"]}],
        "examined_no_lift": ["rejuve"],
    }
    validate_coverage(registry, corpus)  # no raise

def test_coverage_missing_lineage_rejected():
    # rejuve присутствует в корпусе, но нигде не учтён → синтез неполон
    corpus = {"lineage_counts": {"quant-kb": 3, "rejuve": 5}}
    registry = {"findings": [{"lineage_sources": ["quant-kb"]}], "examined_no_lift": []}
    with pytest.raises(ValidationError):
        validate_coverage(registry, corpus)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/test_validate_registry.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# lib/practice_harvest/validate_registry.py
"""Sealed-валидатор реестра синтеза (фаза B). Держит интерпретативный выход
детерминированной схемой + проверкой существования source-path."""
from __future__ import annotations
import json
import sys
from pathlib import Path

TRACKS = {"process", "technical"}
INDEP = {"high", "medium", "low"}
SIMPLE_VERDICTS = {"new-standard", "skip", "deferred:code", "deferred:skill"}


class ValidationError(Exception):
    pass


def _valid_verdict(v: str) -> bool:
    if v in SIMPLE_VERDICTS:
        return True
    return v.startswith("append:") and len(v.split(":", 1)[1].strip()) > 0


def validate_finding(f: dict) -> None:
    req = ["practice", "track", "lineage_sources", "recurrence",
           "domain_independence", "current_location", "lift_verdict", "source_paths"]
    for k in req:
        if k not in f:
            raise ValidationError(f"missing field: {k}")
    if f["track"] not in TRACKS:
        raise ValidationError(f"bad track: {f['track']}")
    if f["domain_independence"] not in INDEP:
        raise ValidationError(f"bad domain_independence: {f['domain_independence']}")
    if not _valid_verdict(f["lift_verdict"]):
        raise ValidationError(f"bad lift_verdict: {f['lift_verdict']}")
    if not isinstance(f["recurrence"], int) or f["recurrence"] < 1:
        raise ValidationError(f"bad recurrence: {f['recurrence']}")
    if not f["lineage_sources"]:
        raise ValidationError("lineage_sources empty")
    # recurrence ДОЛЖЕН равняться числу уникальных lineage (спец §3: source-diversity).
    # Без этого метрика может врать и пройти гейт (codex plan-gate P1).
    if f["recurrence"] != len(set(f["lineage_sources"])):
        raise ValidationError(
            f"recurrence {f['recurrence']} != unique lineage_sources "
            f"{len(set(f['lineage_sources']))}")
    if not f["source_paths"]:
        raise ValidationError("source_paths empty")
    for sp in f["source_paths"]:
        if not Path(sp).exists():
            raise ValidationError(f"source_path missing on disk: {sp}")


def validate_coverage(registry: dict, corpus: dict) -> None:
    """Гейт полноты синтеза: каждый lineage корпуса должен быть либо в
    каком-то finding.lineage_sources, либо явно в registry.examined_no_lift.
    Превращает «я посмотрел везде» в проверяемое свойство — форм-валидатор
    один этого не ловит (advisor 2026-07-10)."""
    corpus_lineages = set(corpus.get("lineage_counts", {}))
    covered: set[str] = set(registry.get("examined_no_lift", []))
    for f in registry.get("findings", []):
        covered.update(f.get("lineage_sources", []))
    missing = corpus_lineages - covered
    if missing:
        raise ValidationError(
            f"coverage gap — lineages neither lifted nor examined_no_lift: "
            f"{sorted(missing)}")


def validate_registry(path: str, corpus_path: str | None = None) -> int:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    findings = data["findings"] if isinstance(data, dict) else data
    for i, f in enumerate(findings):
        try:
            validate_finding(f)
        except ValidationError as e:
            print(f"FAIL finding[{i}] ({f.get('practice','?')}): {e}")
            return 1
    if corpus_path:
        corpus = json.loads(Path(corpus_path).read_text(encoding="utf-8"))
        try:
            validate_coverage(data, corpus)
        except ValidationError as e:
            print(f"FAIL coverage: {e}")
            return 1
    print(f"PASS: {len(findings)} findings valid"
          + (" + coverage complete" if corpus_path else ""))
    return 0


if __name__ == "__main__":
    # usage: validate_registry <registry.json> [corpus.json]
    _corpus = sys.argv[2] if len(sys.argv) > 2 else None
    sys.exit(validate_registry(sys.argv[1], _corpus))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/test_validate_registry.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add lib/practice_harvest/validate_registry.py tests/practice_harvest/test_validate_registry.py
git commit -m "feat(practice-harvest): sealed registry validator (schema + source-path + coverage gate)"
```

---

### Task 7: Run aggregator + synthesize registry

**Files:**
- Create: `docs/reports/2026-07-10-practice-harvest-registry.json` (выход синтеза)
- Read: `docs/reports/2026-07-10-practice-harvest-corpus.json`, `C:/dev/docs/standards/*.md`

Это интерпретативная задача (не TDD). Дисциплина держится валидатором из Task 6.

- [ ] **Step 1: Собрать реальный корпус**

Run (одной строкой, реальные корни):
```bash
C:/dev/h2t-skills/.venv/Scripts/python -m lib.practice_harvest.build_index --repo-root C:/dev/crypto-regime-spike --repo-root C:/dev/quant-kb --repo-root C:/dev/h2t-skills --repo-root C:/dev/POS --repo-root C:/dev/kraken --repo-root C:/dev/h2t-business --repo-root C:/dev/invest-research --repo-root C:/work/rejuve --repo-root C:/work/claudeworking --session-root "C:/Users/<user>/.h2t/sessions/AUTOMATA" --memory-root "C:/Users/<user>/.claude/projects/C--dev-h2t-skills/memory"
```
Expected: `corpus: N records across M lineages -> docs/reports/2026-07-10-practice-harvest-corpus.json`

- [ ] **Step 2: Прочитать список существующих стандартов** (для diff, Task-spec §4)

Run: `ls C:/dev/docs/standards/`
Записать имена — база для `lift_verdict = append:<file>` / `skip`.

Общие правила синтеза (для обоих треков ниже):
- **recurrence** = число *разных canonical lineage*, где практика встречается (source-diversity: 1 lineage → пометить, но не выбрасывать).
- **domain_independence** = оценка переносимости (high/medium/low), НЕ производная от recurrence.
- **lift_verdict** через diff против списка из Step 2: `new-standard` | `append:<file>` | `skip` (уже покрыто) | `deferred:code`/`deferred:skill` (дом — не гайдбук).
- **source_paths** = реальные пути из `record.path` (валидатор проверит существование).
- Каждый рассмотренный canonical lineage должен попасть либо в чью-то `lineage_sources`, либо в registry-level `examined_no_lift` (coverage-гейт Step 5).

- [ ] **Step 3a: Синтез процессного трека**

Прочитать `corpus.json`, отфильтровать `record.track ∈ {process, both}` (rules / CLAUDE.md / memory). Сгруппировать по повторяющейся практике (codex-дисциплина, destructive-ops/git-safety, autonomous-runbook, gates, research/evidence). Для каждой — finding-объект с `track: "process"` по схеме Task 6. Накапливать в списке `findings`.

- [ ] **Step 3b: Синтез технического трека**

Отфильтровать `record.track ∈ {technical, both}` (session what-done / specs / plans / pipeline-rules). Сгруппировать пайплайн-паттерны (extraction/distillation, research-intake, two-gate verdict, validation-library, batch-telemetry). Для каждой — finding-объект с `track: "technical"`. Добавить в `findings`.

- [ ] **Step 3c: Собрать registry.json + учесть непокрытые lineage**

Объединить оба трека. Любой canonical lineage из `corpus.lineage_counts`, не попавший ни в одну находку, внести в `examined_no_lift` (осознанно просмотрен, находок нет). Записать `docs/reports/2026-07-10-practice-harvest-registry.json`:
```json
{
  "window": ["2026-06-10", "2026-07-10"],
  "generated": "2026-07-10",
  "examined_no_lift": ["kraken"],
  "findings": [
    {
      "practice": "codex second-opinion gate before merge",
      "track": "process",
      "lineage_sources": ["quant-kb", "h2t-skills"],
      "recurrence": 2,
      "domain_independence": "high",
      "current_location": "quant-kb/.claude/rules/codex-review.md",
      "lift_verdict": "new-standard",
      "source_paths": ["C:/dev/quant-kb/.claude/rules/codex-review.md"]
    }
  ]
}
```

- [ ] **Step 4: Прогнать sealed-валидатор c coverage-гейтом — ГЕЙТ**

Run (registry + corpus для coverage):
```bash
C:/dev/h2t-skills/.venv/Scripts/python -m lib.practice_harvest.validate_registry docs/reports/2026-07-10-practice-harvest-registry.json docs/reports/2026-07-10-practice-harvest-corpus.json
```
Expected: `PASS: N findings valid + coverage complete`
Если FAIL по finding — починить finding (не валидатор). Если FAIL coverage — добить непокрытый lineage (находка или `examined_no_lift`). Повторять до PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/reports/2026-07-10-practice-harvest-registry.json
git commit -m "docs(practice-harvest): synthesized practice registry (validated)"
```

---

### Task 8: Render registry + draft guidebooks

**Files:**
- Create: `lib/practice_harvest/render_registry.py`
- Create: `tests/practice_harvest/test_render_registry.py`
- Create: `docs/reports/2026-07-10-practice-harvest-registry.md` (рендер)
- Create: `docs/reports/proposed-standards/*.md` (черновики для оператора)

Рендер — детерминированный (TDD). Черновики гайдбуков — интерпретативные (для оператора; docs/standards живёт в другом репо C:/dev/docs, поэтому черновики кладём в h2t-skills под `proposed-standards/`, оператор переносит после ревью).

- [ ] **Step 1: Write the failing test**

```python
# tests/practice_harvest/test_render_registry.py
from lib.practice_harvest.render_registry import render_md

REG = {
    "window": ["2026-06-10", "2026-07-10"],
    "findings": [
        {"practice": "codex gate", "track": "process", "lineage_sources": ["quant-kb"],
         "recurrence": 1, "domain_independence": "high",
         "current_location": "quant-kb/.claude/rules/codex-review.md",
         "lift_verdict": "new-standard", "source_paths": ["x"]},
        {"practice": "two-gate verdict", "track": "technical", "lineage_sources": ["quant-kb", "crypto-regime-spike"],
         "recurrence": 2, "domain_independence": "medium",
         "current_location": "…", "lift_verdict": "deferred:code", "source_paths": ["y"]},
    {"practice": "batch telemetry", "track": "technical", "lineage_sources": ["crypto-regime-spike"],
         "recurrence": 1, "domain_independence": "low",
         "current_location": "…", "lift_verdict": "skip", "source_paths": ["z"]},
    ],
}

def test_render_groups_by_track_and_has_columns():
    md = render_md(REG)
    assert "## Process track" in md
    assert "## Technical track" in md
    assert "codex gate" in md
    assert "two-gate verdict" in md
    # single-lineage помечен как low source-diversity
    assert "⚠" in md

def test_render_sorts_by_recurrence_desc_within_track():
    md = render_md(REG)
    # technical: два finding — recurrence 2 (two-gate) должен идти ВЫШЕ recurrence 1 (batch)
    assert md.index("two-gate verdict") < md.index("batch telemetry")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/test_render_registry.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# lib/practice_harvest/render_registry.py
"""registry.json -> человекочитаемый markdown, сгруппированный по треку."""
from __future__ import annotations
import json
import sys
from pathlib import Path

_COLS = "| practice | recurrence | domain-indep | verdict | source diversity | current location |"
_SEP = "|---|---|---|---|---|---|"


def _rows(findings: list[dict]) -> str:
    lines = []
    for f in sorted(findings, key=lambda x: -x["recurrence"]):
        flag = "⚠ single-lineage" if f["recurrence"] < 2 else "ok"
        lines.append(
            f"| {f['practice']} | {f['recurrence']} | {f['domain_independence']} "
            f"| `{f['lift_verdict']}` | {flag} | {f['current_location']} |"
        )
    return "\n".join(lines)


def render_md(reg: dict) -> str:
    findings = reg["findings"]
    win = reg.get("window", ["", ""])
    out = [f"# Practice harvest registry ({win[0]} … {win[1]})", ""]
    for track, title in [("process", "Process track"), ("technical", "Technical track")]:
        fs = [f for f in findings if f["track"] == track]
        out += [f"## {title}", "", _COLS, _SEP, _rows(fs) if fs else "| — | | | | | |", ""]
    return "\n".join(out)


def main() -> None:
    reg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    out.write_text(render_md(reg), encoding="utf-8")
    print(f"rendered -> {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/test_render_registry.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Render the real registry**

Run: `C:/dev/h2t-skills/.venv/Scripts/python -m lib.practice_harvest.render_registry docs/reports/2026-07-10-practice-harvest-registry.json docs/reports/2026-07-10-practice-harvest-registry.md`
Expected: `rendered -> docs/reports/2026-07-10-practice-harvest-registry.md`

- [ ] **Step 6: Draft guidebooks for `new-standard` verdicts**

Для каждой находки с `lift_verdict == new-standard`: создать черновик `docs/reports/proposed-standards/<slug>.md` — заголовок, TL;DR практики, откуда собрана (lineage_sources + source_paths), предлагаемый дом в `C:/dev/docs/standards/`. Для `append:<file>` — короткая записка «что добавить в `<file>`» в том же каталоге. Это заготовки для операторского ревью (перенос в infra-репо `C:/dev/docs` — вручную, вне этого плана).

- [ ] **Step 7: Full test-suite green + commit**

Run: `C:/dev/h2t-skills/.venv/Scripts/pytest tests/practice_harvest/ -v`
Expected: PASS (все задачи)

```bash
git add lib/practice_harvest/render_registry.py tests/practice_harvest/test_render_registry.py docs/reports/2026-07-10-practice-harvest-registry.md docs/reports/proposed-standards/
git commit -m "docs(practice-harvest): render registry + draft standard proposals"
```

---

## Notes for the executor

- **Не запускать Workflow/агентов.** Корпус мал; всё делается скриптом + прямым чтением.
- **Фаза A (Tasks 1–6) — чистый TDD.** Фаза B (Tasks 7–8) — интерпретация, дисциплинируемая sealed-валидатором и рендер-тестами.
- **lineage.py LINEAGE_MAP** — единственная ручная точка; при новом форке дополнить и переревьюить (спец §Boundaries: fork-collapse — операторский справочник).
- **source-diversity:** находка на 1 canonical lineage валидна, но помечается `⚠` в рендере — не выдавать за общий паттерн без домен-независимости.
- **Границы честности:** корпус ловит только закристаллизованное (rules/handoff/memory); невыписанные уроки на этой глубине невидимы.
- **mtime ≠ авторство** для specs/plans: недавний `git pull`/clone ставит mtime = время checkout, окно может втянуть всё или ничего. Session-md пишутся однократно → их mtime надёжен (и это основной источник технического трека). Near-пустой harvest specs/plans — возможно mtime-артефакт, а не реальное отсутствие; не делать вывод «практик нет».
- **memory-охват — только h2t-skills** (один `--memory-root`; lineage резолвится в бакет `C--dev-h2t-skills`). memory других проектов (`~/.claude/projects/*/memory/`) не покрыта — осознанный scope-call, не полная картина памяти.

