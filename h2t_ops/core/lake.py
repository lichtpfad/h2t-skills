"""A connector's directory in the lake, and the manifest that says which files are its own
(#548 §7.1).

The lake is shared with the owner: a file the package did not write there is foreign, and
the package never replaces it. Ownership is the manifest, not the filesystem — every
publish appends a `pending` row with the hashes it is about to write, writes, then appends
a `committed` row with what it actually wrote. A kill between the two leaves a pending row;
recover() owns only the files whose bytes match it.

Cursors are not lake data: they live in state/cursors/<provider>.json (§3).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from h2t_ops.core import paths, store

# 3.x Granola rows carry no file list; sync wrote <part>/<note_id>.{md,json} for each part
# of "include", both parts when the field is absent (granola/sync.py VALID_INCLUDE).
_LEGACY_PARTS = ("summaries", "transcripts")


def manifest_line(row: dict) -> str:
    """The one serialization of a manifest row (R39): sorted keys, no spaces, UTF-8 kept."""
    return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _real(p) -> Path:
    return Path(os.path.realpath(p))


def _inside(a: Path, b: Path) -> bool:
    return a == b or b in a.parents


def origin(path) -> tuple[str, bool]:
    """(place, dest) for a write at path (R28): inside the lake set in paths.yaml → "lake";
    inside the default data/lake → "data"; anywhere else → dest=True, a path the user named.
    The 3.x lake (~/.dor/lake) is written only once paths.yaml declares it (R2)."""
    real = _real(path)
    configured = paths.place("lake")
    if configured is not None and _inside(real, _real(configured)):
        return "lake", False
    if _inside(real, _real(paths.data_dir() / "lake")):
        return "data", False
    old = paths.legacy("lake.dor")
    if _inside(real, _real(old)):
        raise store.WriteRefused(f"{path} is in the 3.x lake {old}, which paths.yaml does not declare",
                                 hint=f"h2t-ops paths set lake {old}")
    return "lake", True


class ConnectorDir:
    def __init__(self, provider: str, root: Path | None = None):
        self.provider = provider
        if root is None:
            base, _defaulted = paths.place_or_default("lake")
            root = base / provider
        self.root = Path(root)
        self.manifest = self.root / "manifest.jsonl"
        self.place, self.dest = origin(self.root)

    def _rows(self) -> list[dict]:
        if not self.manifest.is_file():
            return []
        out = []
        for line in self.manifest.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
        return out

    def committed_rows(self) -> list[dict]:
        """Every committed row in order, with the connector's own fields. A 3.x row (no
        "state") counts as committed."""
        return [r for r in self._rows() if r.get("state", "committed") == "committed"]

    def owned(self) -> dict[str, str]:
        """rel path → sha256 from the last committed row that wrote it. A path in that row's
        "refused" is never owned, even if an older writer listed it in "files" too.

        A 3.x Granola row has no file list and no hash: its files are derived from note_id
        and include, and count as owned without a hash check (the value is "")."""
        out: dict[str, str] = {}
        for row in self.committed_rows():
            if "state" not in row:
                nid = row.get("note_id")
                if nid:
                    parts = row.get("include")
                    for part in parts if isinstance(parts, list) else _LEGACY_PARTS:
                        for ext in ("md", "json"):
                            out[f"{part}/{nid}.{ext}"] = ""
                continue
            refused = set(row.get("refused") or ())
            for rel, digest in (row.get("files") or {}).items():
                if rel not in refused:
                    out[rel] = digest
        return out

    def _target(self, rel: str) -> Path:
        p = Path(rel)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(f"{rel!r} is not a path inside {self.root}")
        return self.root / p

    def _append(self, row: dict) -> None:
        store.append(self.manifest, manifest_line(row), place=self.place, dest=self.dest)

    def publish(self, files: dict[str, bytes], *, op_id: str, meta: dict | None = None) -> list[str]:
        """Write files (rel path → bytes) by the §7.1 protocol; return the refused paths.

        An own file is replaced; a new path is created, and if a file is already there it is
        foreign — left untouched and refused. meta goes into the committed row as is. The
        caller moves its cursor only after this returns."""
        own = self.owned()
        hashes = {rel: store.sha256(data) for rel, data in files.items()}
        self._append({"op": op_id, "state": "pending",
                      "files": {rel: {"sha256": h, "owned_before": rel in own} for rel, h in hashes.items()}})
        written: dict[str, str] = {}
        refused: list[str] = []
        for rel, data in files.items():
            target = self._target(rel)
            if rel in own:
                store.replace(target, data, place=self.place, dest=self.dest)
            else:
                try:
                    store.create(target, data, place=self.place, dest=self.dest)
                except store.AlreadyExists:
                    refused.append(rel)
                    continue
            written[rel] = hashes[rel]
        self._append({**(meta or {}), "op": op_id, "state": "committed",
                      "files": written, "refused": refused})
        return refused

    def recover(self) -> list[str]:
        """Close every pending row that has no committed row: own only the files whose bytes
        match the pending hash. Returns the paths it took as own."""
        rows = self._rows()
        done = {r.get("op") for r in rows if r.get("state") == "committed"}
        recovered: list[str] = []
        for row in rows:
            op = row.get("op")
            if row.get("state") != "pending" or op in done:
                continue
            matched: dict[str, str] = {}
            for rel, info in (row.get("files") or {}).items():
                target = self._target(rel)
                if target.is_file() and store.sha256(target.read_bytes()) == (info or {}).get("sha256"):
                    matched[rel] = info["sha256"]
            self._append({"op": op, "state": "committed", "files": matched, "refused": [],
                          "recovered": True})
            done.add(op)
            recovered += list(matched)
        return recovered


def cursor_path(provider: str) -> Path:
    return paths.state_dir() / "cursors" / f"{provider}.json"


def _load(path: Path) -> dict:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, OSError):
            pass
    return {}


def read_cursor(provider: str, path: Path | None = None) -> dict:
    """The cursor at path, or state/cursors/<provider>.json; while that does not exist, the
    3.x one in ~/.dor/lake/_cursors (4.0.x fallback read — it is never written)."""
    if path is not None:
        return _load(path)
    new = cursor_path(provider)
    if new.is_file():
        return _load(new)
    return _load(paths.legacy("lake.dor") / "_cursors" / f"{provider}.json")


def write_cursor(provider: str, data: dict, path: Path | None = None) -> Path:
    """Write the cursor to state/cursors/<provider>.json, or to a path the user named."""
    target = Path(path) if path is not None else cursor_path(provider)
    user = path is not None and store.classify(target) != "state"
    store.replace(target, json.dumps(data, ensure_ascii=False, indent=2), place="state", dest=user)
    return target
