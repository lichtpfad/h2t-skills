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
