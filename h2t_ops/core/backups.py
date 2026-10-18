"""Copies of config files before an edit, in state/backups (#548 R14, R46).

config/ is synchronised, so a copy beside the file would travel to every machine and
conflict there; state is per machine. A copy is <name>.<YYYYmmdd-HHMMSS>, and a second edit
in the same second gets -2, -3… — create never overwrites, so no copy is lost. The newest
ten per file are kept, ordered by (stamp, n).
"""
from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

from h2t_ops.core import paths, store

KEEP = 10


def _now() -> _dt.datetime:
    return _dt.datetime.now()


def _copies(folder: Path, name: str) -> list[tuple[tuple[str, int], Path]]:
    pattern = re.compile(re.escape(name) + r"\.(\d{8}-\d{6})(?:-(\d+))?")
    try:
        entries = list(folder.iterdir())
    except FileNotFoundError:
        return []
    out = []
    for p in entries:
        m = pattern.fullmatch(p.name)
        if m:
            out.append(((m.group(1), int(m.group(2) or 1)), p))
    return sorted(out)


def save_backup(path: Path) -> Path:
    """Copy `path` into state/backups and keep the newest KEEP copies of that name."""
    path = Path(path)
    data = path.read_bytes()
    folder = paths.backups_dir()
    stamp = _now().strftime("%Y%m%d-%H%M%S")
    n = 1
    while True:
        target = folder / (f"{path.name}.{stamp}" if n == 1 else f"{path.name}.{stamp}-{n}")
        try:
            store.create(target, data, place="state")
            break
        except store.AlreadyExists:
            n += 1
    copies = _copies(folder, path.name)
    for _key, old in copies[:-KEEP]:
        store.remove(old, place="state")
    return target
