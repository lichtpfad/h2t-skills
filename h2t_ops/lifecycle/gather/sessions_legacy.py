"""The 3.x session roots, read until `h2t-setup sync` moves them into records/ (#548 §5).

3.x wrote `~/.h2t/sessions/<machine>/<key>/` — markdown plus a bounded latest.json — and
DOR before it wrote markdown under `~/.dor/sessions/`. A 4.0.x install that has not
migrated yet has an empty index and its whole history here, so session-start reads it
the way 3.x did. Read only: nothing is ever written to either root.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from h2t_ops.core import paths

ROOTS = ("sessions.h2t", "sessions.dor")


def roots() -> list[Path]:
    """The legacy roots that exist; the h2t one first."""
    return [p for p in (paths.legacy(n) for n in ROOTS) if p.is_dir()]


def _leaves(keys: list[str]) -> list[tuple[Path, Path]]:
    """(root, machine/key directory) for every key under every existing root."""
    found = []
    for root in roots():
        for machine_dir in root.iterdir():
            if not machine_dir.is_dir():
                continue
            for key in keys:
                leaf = machine_dir / key
                if leaf.is_dir():
                    found.append((root, leaf))
    return found


def find_session_files(keys: list[str]) -> list[str]:
    """Markdown under any key, newest first by mtime, as 3.x listed it."""
    files: list[Path] = []
    seen: set[str] = set()
    for _root, leaf in _leaves(keys):
        for f in leaf.glob("*.md"):
            if str(f) not in seen:
                seen.add(str(f))
                files.append(f)
    return [str(f) for f in sorted(files, key=os.path.getmtime, reverse=True)]


def find_latest(keys: list[str]) -> tuple[dict, Path] | None:
    """The newest latest.json by mtime under the 3.x h2t root, with the machine directory
    it was found in. DOR never wrote latest.json, so its root holds only markdown."""
    h2t = paths.legacy("sessions.h2t")
    candidates = [leaf / "latest.json" for root, leaf in _leaves(keys)
                  if root == h2t and (leaf / "latest.json").is_file()]
    if not candidates:
        return None
    path = max(candidates, key=os.path.getmtime)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data, path
