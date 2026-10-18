"""Copies of config files before an edit, in state/backups (#548 R14, R46).

config/ is synchronised, so a copy beside the file would travel to every machine and
conflict there; state is per machine. A copy is <name>.<YYYYmmdd-HHMMSS>, and a second edit
in the same second gets -2, -3… — create never overwrites, so no copy is lost. The newest
ten per file are kept, ordered by (stamp, n). "Per file" is per source path: a file of the
same name in another config root (apply_registration --config-root) keeps its copies in
state/backups/<hash of its directory>/, so ten edits there never prune config/'s.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import os
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


def _folder(path: Path) -> Path:
    """state/backups for a file in config/ (§7.1's own address); a subfolder named by the
    real directory of any other source, so retention never mixes two files of one name."""
    parent = os.path.realpath(path.parent)
    if parent == os.path.realpath(paths.config_dir()):
        return paths.backups_dir()
    return paths.backups_dir() / hashlib.sha256(parent.encode("utf-8")).hexdigest()[:12]


def save_backup(path: Path) -> Path:
    """Copy `path` into state/backups and keep the newest KEEP copies of that source."""
    path = Path(path)
    data = path.read_bytes()
    folder = _folder(path)
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
