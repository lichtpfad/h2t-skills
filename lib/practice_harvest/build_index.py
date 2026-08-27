"""Собрать корпус из реальных корней и записать corpus.json."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from lib.practice_harvest.collect import (
    SourceRecord,
    classify_kind,
    dedup_records,
    track_for_kind,
)
from lib.practice_harvest.lineage import canonical_lineage
from lib.practice_harvest.session_parse import parse_session_md

WINDOW_START = "2026-06-10"
WINDOW_END = "2026-07-10"
_MTIME_KINDS = {"session", "spec", "plan"}


def _in_window(path: Path, start: str, end: str) -> bool:
    mt = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).date()
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
            if not text.strip():
                return  # пустая session после parse — не эмитить (иначе coverage-гейт
                        # сертифицирует пустышку как «examined»; council Lens 1)
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
    # Windows encodes a piped stdout with the ANSI codepage, whatever chcp says, so
    # a non-ASCII payload reaches the caller as cp1252 — or kills the write outright
    # where cp1252 has no byte for the character. Every caller decodes UTF-8 (#428).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
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
