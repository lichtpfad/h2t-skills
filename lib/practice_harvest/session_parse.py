"""Парсинг markdown-секций session-md в структуру."""
from __future__ import annotations

import re

_META_RE = re.compile(r"^- \*\*(?P<key>[^:*]+):\*\*\s*(?P<val>.+?)\s*$", re.M)


def _section_items(text: str, header: str) -> list[str]:
    """Элементы секции '## <header>' до следующего '## '.

    Предпочитает буллеты ('- ...'); если их нет, а тело — проза (параграфы),
    возвращает непустые не-заголовочные строки. Реальные сессии часто пишут
    What Was Done / What Remains прозой — буллет-only парсинг молча терял их
    (council Lens 1 blocker, 2026-07-10).
    """
    m = re.search(rf"^##\s+{re.escape(header)}\s*$", text, re.M)
    if not m:
        return []
    rest = text[m.end():]
    nxt = re.search(r"^##\s+", rest, re.M)
    body = rest[: nxt.start()] if nxt else rest
    bullets = []
    for line in body.splitlines():
        s = line.strip()
        # снять '- ' и checkbox-префикс '- [ ] ' / '- [x] '
        m2 = re.match(r"^-\s+(?:\[[ xX]\]\s+)?(.*)$", s)
        if m2 and m2.group(1):
            bullets.append(m2.group(1).strip())
    if bullets:
        return bullets
    # prose fallback: непустые не-заголовочные строки-параграфы секции
    return [s for ln in body.splitlines()
            if (s := ln.strip()) and not s.startswith("#")]


def parse_session_md(text: str) -> dict:
    meta = {k.strip().lower(): v.strip() for k, v in _META_RE.findall(text)}
    return {
        "date": meta.get("date", ""),
        "domain": meta.get("domain", ""),
        "project": meta.get("project", ""),
        "what_done": _section_items(text, "What Was Done"),
        "what_remains": _section_items(text, "What Remains"),
    }
