"""Сбор источников корпуса с привязкой к файлу, lineage, kind, track."""
from __future__ import annotations
import hashlib
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
    if ("/sessions/" in p or p.startswith("sessions/")) and name.endswith(".md") and name != "latest.json":
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
