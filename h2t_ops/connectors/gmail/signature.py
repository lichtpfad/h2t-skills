"""The owner's email signature variants, read from about-me/signatures.md (#585).

The file is the owner's: a variant is a `##` or `###` heading followed by a ```text block
before the next heading. Gmail's `sendAs` signature is never read — one source, not two.
"""
from __future__ import annotations

import re
from pathlib import Path

from h2t_ops.core import paths
from h2t_ops.core.errors import ConfigError, UsageError

_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")


def signatures_file() -> Path:
    return paths.config_dir() / "about-me" / "signatures.md"


def variants(text: str) -> dict[str, str]:
    """Heading → the first ```text block under it; headings without one are not variants."""
    found: dict[str, str] = {}
    heading, block = None, None
    for line in text.splitlines():
        if block is not None:
            if line.strip() == "```":
                found[heading] = "\n".join(block).strip("\n")
                heading, block = None, None
            else:
                block.append(line)
            continue
        m = _HEADING.match(line)
        if m:
            heading = m.group(1)
        elif heading is not None and line.strip() == "```text":
            block = []
    return found


def _matches(name: str, heading: str) -> bool:
    # "А" names "А. Hou2Touch"; "Полная" names "Полная (факт: …)".
    n, h = name.strip().casefold(), heading.casefold()
    return h == n or h.startswith(n + ".") or h.startswith(n + " ")


def resolve(name: str) -> str:
    """The signature text of the named variant; never an empty one."""
    f = signatures_file()
    try:
        text = f.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise ConfigError(f"no signatures file: {f}",
                          hint="create it, or drop --signature") from e
    found = variants(text)
    hits = [h for h in found if _matches(name, h)]
    if len(hits) != 1:
        what = "is ambiguous" if hits else "not found"
        raise UsageError(f"signature variant {name!r} {what} in {f}",
                         hint="variants: " + "; ".join(hits or found))
    if not found[hits[0]].strip():
        raise ConfigError(f"signature variant {hits[0]!r} is empty in {f}")
    return found[hits[0]]


def append(body: str | None, name: str | None) -> str | None:
    if not name:
        return body
    signature = resolve(name)
    return f"{body.rstrip()}\n\n{signature}" if body else signature
