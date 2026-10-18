"""The migration journal: run/rollback/layout1-<UTC>/journal.jsonl (#548 §7.5, plan R31, R49).

One JSON object per line, each fsynced before the change it describes, so a kill at any
point leaves a journal that resume and rollback can read. What makes a directory a journal
is its journal.jsonl: h2t-setup sync keeps its own <UTC>/ snapshots and claude-pending.json
in the same run/rollback/, and neither is ever taken for one.
"""
from __future__ import annotations

import datetime
import json
import time
from pathlib import Path

from h2t_ops.core import paths, secrets, store
from h2t_ops.core.errors import ConfigError

PREFIX = "layout1-"
KEEP_DAYS = 30


def rollback_root() -> Path:
    return paths.run_dir() / "rollback"


def new_run_id() -> str:
    return PREFIX + datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S%fZ")


def current_bytes(path: Path, place: str) -> bytes | None:
    """The file as it is now, None if there is none. A secret is read through core.secrets."""
    path = Path(path)
    if not path.is_file():
        return None
    if place.startswith("secrets."):
        return secrets.read_secret_bytes(path)
    return path.read_bytes()


def current_sha(path: Path, place: str) -> str | None:
    data = current_bytes(path, place)
    return None if data is None else store.sha256(data)


class Journal:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.dir = rollback_root() / run_id
        self.file = self.dir / "journal.jsonl"

    # --- writing ----------------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        if not self.dir.is_dir():       # made on the first row, so a run that stops before
            store.mkdir(self.dir, place="run", mode=0o700)     # writing leaves none (R36)

    def _row(self, row: dict) -> None:
        self._ensure_dir()
        store.append(self.file, json.dumps(row, ensure_ascii=False), place="run", durable=True)

    @staticmethod
    def _file_row(op: str, path, place: str, source: str, sha256: str,
                  source_path, rule: str | None) -> dict:
        row = {"op": op, "path": str(path), "place": place, "source": source, "sha256": sha256}
        if source_path is not None:
            row["source_path"] = str(source_path)
        if rule is not None:
            row["rule"] = rule
        return row

    def intent(self, path: Path, place: str, source: str, sha256: str,
               source_path: Path | None = None, rule: str | None = None) -> None:
        self._row(self._file_row("intent", path, place, source, sha256, source_path, rule))

    def created(self, path: Path, place: str, source: str, sha256: str,
                source_path: Path | None = None, rule: str | None = None) -> None:
        self._row(self._file_row("created", path, place, source, sha256, source_path, rule))

    def save_prev(self, prev: bytes, *, keys: tuple[str, ...] = ()) -> str:
        """The bytes a change is about to replace or remove, kept for rollback (0600)."""
        self._ensure_dir()
        n = 1
        while True:
            ref = f"prev/{n}"
            if not (self.dir / ref).exists():
                try:
                    store.create(self.dir / ref, prev, place="run", mode=0o600, keys=keys)
                    return ref
                except store.AlreadyExists:
                    pass
            n += 1

    def replaced(self, path: Path, place: str, prev: bytes, new_sha: str, *,
                 keys: tuple[str, ...] = ()) -> str:
        ref = self.save_prev(prev, keys=keys)
        self._row({"op": "replaced", "path": str(path), "place": place,
                   "prev_sha": store.sha256(prev), "new_sha": new_sha, "prev": ref})
        return ref

    def removed(self, path: Path, place: str, prev: bytes, *, keys: tuple[str, ...] = ()) -> str:
        ref = self.save_prev(prev, keys=keys)
        self._row({"op": "removed", "path": str(path), "place": place,
                   "prev_sha": store.sha256(prev), "prev": ref})
        return ref

    def prev_bytes(self, ref: str) -> bytes:
        return (self.dir / ref).read_bytes()

    def winner(self, target: str, key: str, sha256: str) -> None:
        self._row({"op": "winner", "target": str(target), "key": key, "sha256": sha256})

    def baseline(self, pairs: set[tuple[str, str]]) -> None:
        for key, sha in sorted(pairs):
            self._row({"op": "baseline", "key": key, "sha256": sha})

    def machine(self, name: str) -> None:
        """The machine name this run migrates for: a resume in another shell keeps it."""
        self._row({"op": "machine", "name": name})

    def phase_done(self, phase: str) -> None:
        self._row({"op": "phase_done", "phase": phase})

    def rolling_back(self) -> None:
        """Rollback has begun: this journal is never resumed by migrate again."""
        self._row({"op": "rollback"})

    def reconcile(self) -> list[str]:
        """A kill between store.create and its created row left an intent: the file is the
        one the intent names when its hash matches, and gets its row. A file that is absent
        was never published; one with another hash is not ours — left, and returned."""
        rows = self.entries()
        done = {r["path"] for r in rows if r["op"] == "created"}
        foreign: list[str] = []
        for r in rows:
            if r["op"] != "intent" or r["path"] in done:
                continue
            sha = current_sha(Path(r["path"]), r["place"])
            if sha is None:
                continue
            if sha == r["sha256"]:
                self.created(Path(r["path"]), r["place"], r["source"], r["sha256"],
                             r.get("source_path"), r.get("rule"))
                done.add(r["path"])
            else:
                foreign.append(r["path"])
        return foreign

    # --- reading ----------------------------------------------------------------------------

    def entries(self) -> list[dict]:
        try:
            lines = self.file.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        out = []
        for i, line in enumerate(lines):
            try:
                out.append(json.loads(line))
            except ValueError:
                if i == len(lines) - 1:     # a kill mid-row: the change it named never began
                    continue
                raise ConfigError(f"{self.file}: line {i + 1} is not JSON",
                                  hint="the journal is damaged; restore it or remove the directory") from None
        return out

    def done_phases(self) -> set[str]:
        return {r["phase"] for r in self.entries() if r["op"] == "phase_done"}

    def finished(self) -> bool:
        return "markers" in self.done_phases()

    def rolled_back(self) -> bool:
        return any(r["op"] == "rollback" for r in self.entries())

    def recorded_machine(self) -> str | None:
        names = [r["name"] for r in self.entries() if r["op"] == "machine"]
        return names[0] if names else None

    def resumable(self) -> bool:
        return not self.finished() and not self.rolled_back()

    @staticmethod
    def all() -> list[Journal]:
        """Only directories that hold journal.jsonl, oldest first (R31)."""
        base = rollback_root()
        if not base.is_dir():
            return []
        return sorted((Journal(d.name) for d in base.iterdir()
                       if d.is_dir() and (d / "journal.jsonl").is_file()),
                      key=lambda j: j.run_id)

    @staticmethod
    def latest() -> Journal | None:
        """An unfinished one first, else the newest."""
        journals = Journal.all()
        open_ = [j for j in journals if j.resumable()]
        return (open_ or journals or [None])[-1]


def prune(now: float | None = None) -> list[str]:
    """Remove finished migration journals whose last row is older than 30 days (§7.5).
    An unfinished one is never touched; sync's snapshots are not journals at all."""
    now = time.time() if now is None else now
    gone = []
    for j in Journal.all():
        if j.finished() and now - j.file.stat().st_mtime > KEEP_DAYS * 86400:
            store.remove_tree(j.dir, place="run")
            gone.append(j.run_id)
    return gone
