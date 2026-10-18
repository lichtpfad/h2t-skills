"""The migration journal: run/rollback/layout1-<UTC>/journal.jsonl (#548 §7.5, plan R31, R49).

One JSON object per line, each fsynced before the change it describes, so a kill at any
point leaves a journal that resume and rollback can read. What makes a directory a journal
is its journal.jsonl: h2t-setup sync keeps its own <UTC>/ snapshots and claude-pending.json
in the same run/rollback/, and neither is ever taken for one.
"""
from __future__ import annotations

import contextlib
import datetime
import json
import time
from collections.abc import Iterator
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

    def _torn(self) -> bool:
        """The last row was cut by a kill: the file does not end in a newline."""
        try:
            with open(self.file, "rb") as fh:
                fh.seek(-1, 2)
                return fh.read(1) != b"\n"
        except (FileNotFoundError, OSError):
            return False

    def _row(self, row: dict) -> None:
        self._ensure_dir()
        if self._torn():
            # Close the cut line, and say so on the next one: entries() skips the fragment
            # only where a torn_row follows it, so damage anywhere else is still an error.
            store.append(self.file, "\n" + json.dumps({"op": "torn_row"}), place="run", durable=True)
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

    def source(self, old: Path, new: Path) -> None:
        """An old file this run read for `new` — copied, merged, transformed, or found already
        there with the same hash. MOVED-TO.txt goes where these point, whatever verification
        the file gets (source_path is only for byte copies, R25)."""
        self._row({"op": "source", "old": str(old), "new": str(new)})

    def rolling_back(self) -> None:
        """Rollback has begun: this journal is never resumed by migrate again."""
        self._row({"op": "rollback"})

    def rollback_done(self) -> None:
        self._row({"op": "rollback_done"})

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
            # Bytes, line by line: a row cut mid-character must not fail the whole decode.
            lines = self.file.read_bytes().splitlines()
        except FileNotFoundError:
            return []
        torn = json.dumps({"op": "torn_row"}).encode()
        out = []
        for i, line in enumerate(lines):
            try:
                row = json.loads(line.decode("utf-8"))
            except ValueError:
                # A kill mid-row: the change it named never began. Last line, or closed by
                # the torn_row the next append wrote.
                if i == len(lines) - 1 or lines[i + 1] == torn:
                    continue
                raise ConfigError(f"{self.file}: line {i + 1} is not JSON",
                                  hint="the journal is damaged; restore it or remove the directory") from None
            if row.get("op") != "torn_row":
                out.append(row)
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

    def rollback_pending(self) -> bool:
        """A rollback began and did not reach its end: only rollback may touch it next."""
        pending = False                 # a re-run rollback writes rollback again: last wins
        for r in self.entries():
            if r["op"] in ("rollback", "rollback_done"):
                pending = r["op"] == "rollback"
        return pending

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


BUSY = "another layout migration or rollback is running"


@contextlib.contextmanager
def exclusive() -> Iterator[None]:
    """One migrate or rollback at a time on this machine: run/layout.lock, not waited for."""
    with contextlib.ExitStack() as stack:
        try:                            # only the acquisition: a LockBusy from a phase is its own
            stack.enter_context(store.locked(paths.run_dir() / "layout.lock", place="run", timeout=0))
        except store.LockBusy:
            raise ConfigError(BUSY, hint="wait for it to finish, then run the command again",
                              details={"reason": "busy"}) from None
        yield


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
