"""Where a download lands when the user names no path, and how it is written (#548 §6 п. 1).

No path: the inbox place, or data/inbox while paths.yaml does not set it (R28); the file is
created, never written over one already there — that one keeps its bytes and the new file
takes -2, -3 (§7.1, R47). A path the user named goes through store with dest=True.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from h2t_ops.core import paths, store

_RESERVED = frozenset({"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                       *(f"LPT{i}" for i in range(1, 10))})


def plain_name(raw: str) -> str:
    """One path segment on every platform: no / or \\, no drive colon, no leading dot, no
    trailing dot or space (Windows drops them), and not a Windows device name (CON, NUL.txt,
    com1.log open the device, not a file) — those get a leading underscore."""
    for ch in ("/", "\\", ":"):
        raw = raw.replace(ch, "_")
    name = raw.strip().lstrip(".").rstrip(". ")
    if name.split(".", 1)[0].rstrip(" ").upper() in _RESERVED:
        name = "_" + name
    return name


def last_segment(raw: str | None) -> str:
    """A provider's file name, last segment only: "../a/report.pdf" is report.pdf."""
    return plain_name(str(raw or "").replace("\\", "/").rsplit("/", 1)[-1])


@dataclass(frozen=True)
class Default:
    dir: Path
    place: str          # the place id when paths.yaml sets it, "data" for data/<place> (R28)
    defaulted: bool


def default_dir(place_id: str = "inbox") -> Default:
    found, defaulted = paths.place_or_default(place_id)
    return Default(found, "data" if defaulted else place_id, defaulted)


def save_new(directory: Path, name: str, write: Callable[[BinaryIO], object], *,
             place: str, dest: bool = False) -> Path:
    """Create `name` directly in `directory`, or the first free <stem>-N<suffix>.

    `write` fills the handle and must be repeatable: when another writer takes the name
    between the check and the link, it runs again for the next name (Telegram re-downloads).
    """
    if not name or name in (".", "..") or Path(name).name != name or "\\" in name:
        raise store.WriteRefused(f"file name {name!r} leaves {directory}",
                                 hint="the file is written only directly into that directory")
    for target in store.unique_name(Path(directory) / name):
        if os.path.lexists(target):
            continue
        try:
            with store.writer(target, place=place, dest=dest, exclusive=True) as fh:
                write(fh)
        except store.AlreadyExists:
            continue                    # taken between the check and the link: next name
        return target
    raise AssertionError("unique_name is endless")   # pragma: no cover


def say_saved(path: Path, defaulted: bool, place_id: str = "inbox") -> None:
    note = f" ({place_id} not set: h2t-ops paths set {place_id} <path>)" if defaulted else ""
    print(f"saved to {path}{note}", file=sys.stderr)


def save_default(name: str, write: Callable[[BinaryIO], object], *,
                 place_id: str = "inbox") -> tuple[Path, bool]:
    """No path from the user: create in the default place and say where. (path, defaulted)."""
    d = default_dir(place_id)
    path = save_new(d.dir, name, write, place=d.place)
    say_saved(path, d.defaulted, place_id)
    return path, d.defaulted


def save_bytes_default(name: str, payload: bytes, *, place_id: str = "inbox") -> tuple[Path, bool]:
    return save_default(name, lambda fh: fh.write(payload), place_id=place_id)
