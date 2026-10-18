"""The only writer (#548 §7.2): create, append, replace, managed, remove.

Every write is classified by the realpath of its target against every place's root,
whatever place the caller named and wherever the path came from (--dest, a symlink).
A write into vault that does not come through ingest_write is refused. Each write is
logged to logs/writes.jsonl — for doctor and for a person; correctness never rests on it.
"""
from __future__ import annotations

import contextlib
import contextvars
import glob
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.parse
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

from h2t_ops.core import paths
from h2t_ops.core.errors import ConfigError


class WriteRefused(ConfigError):
    """A write the ownership table (§7.1) does not allow."""


class AlreadyExists(FileExistsError):
    """create() found a file at the target; nothing was written."""


class Changed(Exception):
    """replace(expect=...) found the target changed since the caller read it; nothing was
    written. The caller reads again and retries (a file another program also writes)."""


_ANY = object()


def stamp(path) -> tuple[int, int] | None:
    """(size, mtime_ns) of a file, None if there is none: what replace(expect=) compares."""
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    return (st.st_size, st.st_mtime_ns)


_PACKAGE = ("run", "config", "secrets.shared", "secrets.local", "records.sessions",
            "records.activity", "records.evals", "records.imports", "data", "state", "logs",
            "layout")   # layout.json: a file place, classified by its exact path
_REMOVABLE = {"run", "state", "logs", "tmp", "harness"}
_SECRET = {"secrets.shared", "secrets.local"}
_DEST_FORBIDDEN = {*_PACKAGE, "vault", "legacy", "harness", "h2t-root"}
_LOG_LIMIT = 10 * 1024 * 1024
_LOG_KEEP = 5
_LOG_LOCK = ".writes.jsonl.lock"

_INGEST: contextvars.ContextVar[bool] = contextvars.ContextVar("h2t_ingest", default=False)
_MIGRATING: contextvars.ContextVar[bool] = contextvars.ContextVar("h2t_migrating", default=False)
_DELEGATED: dict[str, tuple[str, int]] = {}   # realpath -> (library, open scopes)
_DELEGATED_LOCK = threading.Lock()
_SIDECARS = ("-journal", "-wal", "-shm")


def _real(p) -> Path:
    return Path(os.path.realpath(p))


def _roots() -> tuple[list[tuple[str, Path]], ConfigError | None]:
    """Every place's real root, deepest first, and the paths.yaml error if there is one.

    A broken paths.yaml must not stop writes inside ~/.h2t (plan R17, gates.md): the package
    places are still classified; only the places it would have declared are unknown.
    """
    out = [(pid, _real(paths.dir_of(pid))) for pid in (*_PACKAGE, "harness", "tmp")]
    broken: ConfigError | None = None
    try:
        declared = {pid: paths.place(pid) for pid in paths.YAML_PLACES}
    except ConfigError as exc:
        declared, broken = {}, exc
    declared["vault"] = paths.vault()
    out += [(pid, _real(p)) for pid, p in declared.items() if p is not None]
    out += [("legacy", _real(p)) for p in paths.legacy_roots()]
    # Catch-all for anything else under ~/.h2t: no write goes there, --dest included; the
    # child places above are deeper and win the sort (round 5).
    out.append(("h2t-root", _real(paths.root())))
    return sorted(out, key=lambda kv: len(kv[1].parts), reverse=True), broken


def _classify(path) -> tuple[str, ConfigError | None]:
    real = _real(path)
    roots, broken = _roots()
    for pid, r in roots:
        if real == r or r in real.parents:
            return pid, broken
    return "elsewhere", broken


def classify(path) -> str:
    return _classify(path)[0]


def _compat_allowed(path: Path) -> bool:
    real = _real(path)
    if real == _real(paths.legacy("google.store") / "tokens.json"):
        return True
    return _MIGRATING.get() and path.name == "MOVED-TO.txt"


def _check(path: Path, place: str, *, dest: bool = False, compat: bool = False) -> str:
    got, broken = _classify(path)
    # Vault by the filesystem, before the deepest root decides: a package root inside the
    # vault, or a vault that encloses ~/.h2t, would otherwise classify its files as data or
    # state and let any writer into POS's vault.
    vault = _real(paths.vault())
    real = _real(path)
    if got != "vault" and (real == vault or vault in real.parents) and not _INGEST.get():
        raise WriteRefused(f"{path} is inside vault {vault}, though it classifies as {got}",
                           hint="vault and the package places must not overlap: move the "
                                "vault or the h2t root apart (h2t-ops paths list)")
    # A place paths.yaml would declare may sit inside a legacy root or tmp (lake: ~/.dor/lake,
    # R2): while the file is broken it classifies as that, and the refusal must name the file.
    if broken is not None and (got == "elsewhere" or place in paths.YAML_PLACES):
        raise WriteRefused(f"{path}: cannot tell whose place this is while paths.yaml is broken ({broken})",
                           hint="fix it: h2t-ops paths set <place> <path>, or edit the file")
    if got == "vault" and not _INGEST.get():
        raise WriteRefused(f"{path} is inside vault; only ingest writes there",
                           hint="vault is POS's; the package writes raw material to lake (§6)")
    if got == "legacy":
        if compat and _compat_allowed(path):
            return got
        raise WriteRefused(f"{path} is a legacy 3.x location; 4.0 does not write there",
                           hint="write the new place from core.paths; legacy files stay as copies")
    if dest:
        if got in _DEST_FORBIDDEN:
            raise WriteRefused(f"--dest {path} points into {got}", hint="choose a path outside ~/.h2t")
        return got
    if got != place:
        raise WriteRefused(f"{path} is in {got}, not {place}",
                           hint="name the place the path really belongs to")
    return got


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _default_mode(place: str) -> int:
    if place in _SECRET:
        return 0o600
    um = os.umask(0)
    os.umask(um)
    return 0o666 & ~um


def _mode(place: str, got: str, mode: int | None) -> int:
    """A file under secrets/** is 0600 whatever mode the caller passed (Global Constraints)."""
    if place in _SECRET or got in _SECRET:
        return 0o600
    return _default_mode(place) if mode is None else mode


def _ensure_dir(directory: Path, place: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    if place in _SECRET and os.name != "nt":
        top = paths.dir_of(place)
        for d in (paths.root() / "secrets", top, directory):
            if d.exists() and (d == top or top in d.parents or d == paths.root() / "secrets"):
                os.chmod(d, 0o700)


def _caller() -> str:
    f = sys._getframe(1)
    here = __file__
    while f is not None and f.f_code.co_filename == here:
        f = f.f_back
    return f"{f.f_globals.get('__name__', '?')}:{f.f_lineno}" if f else "?"


def _rotate(log: Path) -> None:
    try:
        if log.stat().st_size < _LOG_LIMIT:
            return
    except FileNotFoundError:
        return
    for i in range(_LOG_KEEP - 1, 0, -1):
        older = log.with_name(f"writes.{i}.jsonl")
        if older.exists():
            os.replace(older, log.with_name(f"writes.{i + 1}.jsonl"))
    os.replace(log, log.with_name("writes.1.jsonl"))


def _file_sha(path: Path) -> str | None:
    """Streamed hash of a published file (writer, managed): no whole-file read into memory."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _log(op: str, place: str, path: Path, data: bytes | None, *, key: str | None = None,
         keys: tuple[str, ...] = (), digest: str | None = None) -> None:
    """key: a library or source label; keys: secret key NAMES from core.secrets (§7.2, R41);
    digest: the hash of a file published without passing its bytes here (§7.2: every write
    has a hash, secrets excepted)."""
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "op": op, "place": place, "path": str(path),
           "sha256": None if place in _SECRET else (digest if data is None else sha256(data)),
           "caller": _caller()}
    if key:
        row["key"] = key
    # A write is a secret write if it lands in secrets/* or if core.secrets named its keys:
    # dest=True into a user directory and the Google compat mirror classify elsewhere, yet
    # carry a secret (self-check, round 3).
    if keys:
        row["keys"] = sorted(keys)
        row["sha256"] = None
    log = paths.logs_dir() / "writes.jsonl"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        # Rotation renames writes.jsonl, so the lock lives on a file that is never renamed:
        # rotate and append are one critical section across processes.
        lock = os.open(log.with_name(_LOG_LOCK), os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o644)
        try:
            with _lock(lock):
                _rotate(log)
                fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o644)
                try:
                    _write_all(fd, (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8"))
                finally:
                    os.close(fd)
        finally:
            os.close(lock)
    except OSError as exc:
        # The journal is for people; a write must not fail because its log row did (gates.md),
        # but a lost row is said, not swallowed.
        print(f"h2t: write not logged to {log}: {exc}", file=sys.stderr)


def _write_all(fd: int, data: bytes) -> None:
    """os.write may write less than asked; loop until every byte is out."""
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view):]


_LOCK_OFFSET = 2 ** 40   # far past any real EOF: msvcrt locks are mandatory, and a lock on
                         # byte 0 would make a reader of the file (gather, doctor) fail


class LockBusy(TimeoutError):
    """locked(timeout=) found the lock held for the whole timeout; nothing was done."""


@contextlib.contextmanager
def _lock(fd: int, timeout: float | None = None) -> Iterator[None]:
    deadline = None if timeout is None else time.monotonic() + timeout
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if deadline is not None and time.monotonic() >= deadline:
                    raise LockBusy(f"lock held past {timeout} s") from None
                time.sleep(0.02)
        try:
            yield               # O_APPEND writes land at EOF whatever the file position
        finally:
            os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        if deadline is None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        else:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise LockBusy(f"lock held past {timeout} s") from None
                    time.sleep(0.02)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)


@contextlib.contextmanager
def locked(path, *, place: str, timeout: float | None = None) -> Iterator[None]:
    """Hold an exclusive lock on a lock file for the block: two processes that both write
    one file through a library (the index) take turns. With timeout, LockBusy once it has
    been held that long by someone else. The file stays and stays empty — removing it would
    race a peer that has just opened it; its creation is logged once, an acquisition never."""
    path = Path(path)
    got = _check(path, place)
    _ensure_dir(path.parent, place)
    flags = os.O_RDWR | getattr(os, "O_BINARY", 0)
    try:
        fd, created = os.open(path, flags | os.O_CREAT | os.O_EXCL, _mode(place, got, None)), True
    except FileExistsError:
        fd, created = os.open(path, flags), False
    try:
        if created:
            _log("create", got, path, b"")
        with _lock(fd, timeout):
            yield
    finally:
        os.close(fd)


def _bytes(data: str | bytes) -> bytes:
    return data.encode("utf-8") if isinstance(data, str) else data


_TMP_SUFFIX = ".h2t-tmp"   # a killed write leaves .<name>.XXXX.h2t-tmp; doctor reports them (R48)


def unique_name(path: Path) -> Iterator[Path]:
    """path, then <stem>-2<suffix>, -3, ... (plan R47)."""
    path = Path(path)
    yield path
    n = 2
    while True:
        yield path.with_name(f"{path.stem}-{n}{path.suffix}")
        n += 1


def _tmp_beside(path: Path, payload: bytes, mode: int) -> str:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".", suffix=_TMP_SUFFIX)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        if os.name != "nt":             # no effect on Windows; the profile ACL protects (§11.3)
            os.chmod(tmp, mode)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
    return tmp


def replace(path, data: str | bytes, *, place: str, mode: int | None = None,
            compat: bool = False, dest: bool = False, keys: tuple[str, ...] = (),
            in_place: bool = False, expect=_ANY) -> Path:
    """in_place: truncate and write the target itself, no temp file. Only for a target
    os.replace cannot take — an NTFS alternate data stream, "name:stream" (research
    objects on Windows); a reader may then see a partial file.

    expect: the target's stamp() when the caller read it (None: it did not exist). Compared
    after the temp file is written, immediately before publication; on a mismatch the temp
    file is removed and Changed is raised, so a concurrent writer's save is not overwritten
    with the caller's stale copy. What is left is the gap between that stat and os.replace."""
    path = Path(path)
    got = _check(path, place, dest=dest, compat=compat)
    # Not a general escape from the atomic write: a stream name only, never a secret.
    if in_place and expect is not _ANY:
        raise WriteRefused(f"{path}: an in-place write has no publication to make conditional",
                           hint="write it with replace() without in_place")
    if in_place and (":" not in path.name or place in _SECRET or got in _SECRET):
        raise WriteRefused(f"{path}: an in-place write is only for an NTFS stream "
                           "(name:stream) outside secrets",
                           hint="write it with replace() without in_place")
    payload = _bytes(data)
    _ensure_dir(path.parent, place)
    if in_place:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0),
                     _mode(place, got, mode))
        try:
            if os.name != "nt":         # an existing file keeps no mode wider than the place's
                os.fchmod(fd, _mode(place, got, mode))
            _write_all(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        _log("replace", got, path, payload, keys=keys)
        return path
    tmp = _tmp_beside(path, payload, _mode(place, got, mode))
    try:
        if expect is not _ANY and stamp(path) != expect:
            raise Changed(f"{path} changed since it was read; not replaced")
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
    _log("replace", got, path, payload, keys=keys)
    return path


def create(path, data: str | bytes, *, place: str, mode: int | None = None,
           dest: bool = False, keys: tuple[str, ...] = (), compat: bool = False) -> Path:
    path = Path(path)
    got = _check(path, place, dest=dest, compat=compat)   # compat: MOVED-TO.txt while migrating
    payload = _bytes(data)
    _ensure_dir(path.parent, place)
    tmp = _tmp_beside(path, payload, _mode(place, got, mode))
    try:
        try:
            os.link(tmp, path)          # atomic and never overwrites
        except FileExistsError:
            raise AlreadyExists(str(path)) from None
        except OSError as exc:          # no hard links here (FAT, exFAT, some network shares)
            # No fallback into the final path: an interrupted direct write would leave half a
            # file that no manifest owns (§7.2, plan R20).
            raise ConfigError(f"{path.parent}: this filesystem has no hard links, so create "
                              f"cannot publish {path.name} atomically ({exc})",
                              hint="move this place to a local disk: h2t-ops paths set <place> <path>") from exc
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
    _log("create", got, path, payload, keys=keys)
    return path


# Places whose files the migration merges into (activity, §8 п. 4): an append there also
# holds a lock that outlives the file's inode, so a merge that replaces the file cannot
# publish over a row appended to the inode it read.
_MERGED = {"records.activity"}


def _merge_lock_path(path: Path) -> Path:
    """Beside nothing synced: run/ is local, and a lock file in records/ would travel."""
    key = hashlib.sha256(str(_real(path)).encode("utf-8")).hexdigest()[:16]
    return paths.run_dir() / "locks" / f"{key}.lock"


@contextlib.contextmanager
def merging(path, *, place: str) -> Iterator[None]:
    """Hold the lock append() takes for a file in a merged place, for a read-merge-replace:
    appends wait until the merged file is published, then land in it."""
    path = Path(path)
    got = _check(path, place)
    if got not in _MERGED:
        raise WriteRefused(f"{path}: merging() is only for {', '.join(sorted(_MERGED))}",
                           hint="other places are written by one writer at a time")
    with locked(_merge_lock_path(path), place="run"):
        yield


def append(path, line: str, *, place: str, dest: bool = False, durable: bool = False) -> None:
    path = Path(path)
    got = _check(path, place, dest=dest)
    payload = (line if line.endswith("\n") else line + "\n").encode("utf-8")
    _ensure_dir(path.parent, place)
    # Taken before the file is opened: the descriptor then names the file a merge published.
    merge = locked(_merge_lock_path(path), place="run") if got in _MERGED else contextlib.nullcontext()
    with merge:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0),
                     _mode(place, got, None))
        try:
            if os.name != "nt" and (place in _SECRET or got in _SECRET):
                os.fchmod(fd, 0o600)    # an existing secret file is repaired, not trusted
            with _lock(fd):
                _write_all(fd, payload)  # the whole line under the lock, short writes included
                if durable:
                    os.fsync(fd)        # migration journal: the row survives a kill (R49)
        finally:
            os.close(fd)
    _log("append", got, path, payload)


def mkdir(path, *, place: str, mode: int | None = None, dest: bool = False) -> Path:
    path = Path(path)
    _check(path, place, dest=dest)
    _ensure_dir(path, place)
    if mode is not None and os.name != "nt":
        os.chmod(path, mode)            # run/rollback/<id> is 0700 (plan R36)
    return path


def _old_config_backup(path: Path, place: str) -> bool:
    """3.x left *.yaml.bak copies in config/; the migration moves them to state/backups (R14)."""
    return place == "config" and _MIGRATING.get() and ".yaml.bak" in path.name


def remove(path, *, place: str, journal: bool = False) -> None:
    path = Path(path)
    got = _check(path, place, compat=journal)
    if place not in _REMOVABLE and not journal and not _old_config_backup(path, place):
        raise WriteRefused(f"remove is not allowed in {place}", hint="only run, state, logs, tmp, harness")
    with contextlib.suppress(FileNotFoundError):
        path.unlink()
    _log("remove", got, path, None)


def remove_tree(path, *, place: str) -> None:
    path = Path(path)
    got = _check(path, place)
    if place not in _REMOVABLE:
        raise WriteRefused(f"remove_tree is not allowed in {place}", hint="only run, state, logs, tmp, harness")
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        return                          # nothing was there; nothing removed, nothing logged
    _log("remove_tree", got, path, None)


def delegated(path) -> str | None:
    real = str(_real(path))
    with _DELEGATED_LOCK:
        for key, (lib, _count) in _DELEGATED.items():
            if real == key or real in {key + s for s in _SIDECARS}:
                return lib
    return None


def _delegate(key: str, library: str) -> None:
    with _DELEGATED_LOCK:
        lib, count = _DELEGATED.get(key, (library, 0))
        _DELEGATED[key] = (lib, count + 1)


def _undelegate(key: str) -> None:
    """Nested managed() on one path (Task 9: a helper inside an open client) is counted:
    only the outermost exit ends the delegation."""
    with _DELEGATED_LOCK:
        lib, count = _DELEGATED[key]
        if count > 1:
            _DELEGATED[key] = (lib, count - 1)
        else:
            del _DELEGATED[key]


def _set_place_mode(path: Path, mode: int) -> OSError | None:
    """chmod the file and its sidecars; the first failure is returned, not swallowed."""
    first: OSError | None = None
    for side in (path, *(path.with_name(path.name + s) for s in _SIDECARS)):
        try:
            os.chmod(side, mode)
        except FileNotFoundError:
            continue
        except OSError as exc:
            first = first or exc
    return first


@contextlib.contextmanager
def managed(path, *, place: str, library: str, dest: bool = False) -> Iterator[Path]:
    """Resolve and check the path, then hand the file to a library that opens it itself."""
    path = Path(path)
    got = _check(path, place, dest=dest)
    _ensure_dir(path.parent, place)
    if os.name != "nt" and (place in _SECRET or got in _SECRET):
        # 0600 before the library opens it, not only on exit: a process killed inside the
        # block (a first Telegram login) must not leave a secret at the umask's mode. An
        # empty file is a valid empty database to sqlite, and its journals copy its mode.
        os.close(os.open(path, os.O_WRONLY | os.O_CREAT, 0o600))
        os.chmod(path, 0o600)
    key = str(_real(path))
    _delegate(key, library)

    def finish() -> OSError | None:
        _undelegate(key)
        # Windows: the profile ACL protects (§11.3)
        err = _set_place_mode(path, _mode(place, got, None)) if os.name != "nt" else None
        _log("managed", got, path, None, key=library,
             digest=None if place in _SECRET else _file_sha(path))
        return err

    try:
        yield path
    except BaseException as exc:
        err = finish()
        if err is not None:             # said on the library's error, never in its place
            exc.add_note(f"h2t: also could not set the mode of {path}: {err}")
        raise
    err = finish()
    if err is not None:
        raise err                       # a secret left wider than 0600 is not a success


@contextlib.contextmanager
def writer(path, *, place: str, mode: int | None = None, dest: bool = False,
           exclusive: bool = False) -> Iterator[BinaryIO]:
    """A stream into a temp file beside the target (plan R29). Clean exit publishes it:
    os.replace, or with exclusive=True os.link — create-or-fail, never over a file the
    caller does not own (§7.1, R47). An exception leaves the old file, if any, untouched."""
    path = Path(path)
    got = _check(path, place, dest=dest)
    _ensure_dir(path.parent, place)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".", suffix=_TMP_SUFFIX)
    try:
        with os.fdopen(fd, "wb") as fh:
            yield fh
            fh.flush()
            os.fsync(fh.fileno())
        if os.name != "nt":
            os.chmod(tmp, _mode(place, got, mode))
        if exclusive:
            try:
                os.link(tmp, path)
            except FileExistsError:
                raise AlreadyExists(str(path)) from None
            except OSError as exc:
                raise ConfigError(f"{path.parent}: no hard links, cannot create {path.name} "
                                  f"atomically ({exc})", hint="move this place to a local disk") from exc
            os.unlink(tmp)
        else:
            os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
    _log("create" if exclusive else "replace", got, path, None,
         digest=None if place in _SECRET else _file_sha(path))


@contextlib.contextmanager
def connect_sqlite(path, *, place: str, library: str = "sqlite3",
                   dest: bool = False) -> Iterator[sqlite3.Connection]:
    """The one sqlite3.connect in the package (plan R18)."""
    with managed(path, place=place, library=library, dest=dest) as p:
        conn = sqlite3.connect(p)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


@contextlib.contextmanager
def read_sqlite(path) -> Iterator[sqlite3.Connection]:
    """A read-only connection for a report (doctor): mode=ro, so no file or directory is
    created, nothing is chmodded, committed or logged. A missing file is an OperationalError."""
    uri = "file:" + urllib.parse.quote(Path(path).as_posix(), safe="/:") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        yield conn
    finally:
        conn.close()


def sqlite_copy(src, dest, *, place: str) -> Path:
    """Copy a live SQLite file whole: backup() reads a consistent snapshot even if another
    process has the source open, where a byte copy can tear it (plan R18, Task 9). The copy
    is built beside the target and published by os.replace, so a kill mid-backup never
    leaves a half database at dest that the next run would take as done (R49)."""
    src, dest = Path(src), Path(dest)
    tmp = dest.with_name(f".{dest.name}.backup{_TMP_SUFFIX}")
    source = sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)
    try:
        with connect_sqlite(tmp, place=place, library="sqlite-backup") as target:
            source.backup(target)
    finally:
        source.close()
    got = _check(dest, place)
    os.replace(tmp, dest)
    _log("replace", got, dest, None, digest=None if place in _SECRET else _file_sha(dest))
    return dest


def ingest_write(path, data: str | bytes) -> Path:
    """The vault's single door (§7.2). One import site: the ingest module (subsystem 4)."""
    token = _INGEST.set(True)
    try:
        return replace(path, data, place="vault")
    finally:
        _INGEST.reset(token)


@contextlib.contextmanager
def migrating() -> Iterator[None]:
    token = _MIGRATING.set(True)
    try:
        yield
    finally:
        _MIGRATING.reset(token)


class RepoWriter:
    def __init__(self, root: Path, command: str, rules: dict[str, tuple[str, ...]]):
        self.root, self.command, self.rules = _real(root), command, rules

    def _target(self, op: str, rel: str) -> Path:
        import fnmatch
        target = _real(self.root / rel)
        if target != self.root and self.root not in target.parents:
            raise WriteRefused(f"{rel} is outside the repository {self.root}", hint="")
        posix = target.relative_to(self.root).as_posix()
        # git's own directory is never a repository write, whatever a rule's glob says: any
        # depth, any case (a case-insensitive disk opens .GIT as .git). The one exception is
        # the exact path a command lists literally — scaffold appends to .git/info/exclude.
        if any(part.casefold() == ".git" for part in posix.split("/")) \
                and posix not in self.rules.get(op, ()):
            raise WriteRefused(f"{self.command} may not {op} {posix}: .git is git's, not a repository file",
                               hint="")
        if not any(fnmatch.fnmatchcase(posix, g) for g in self.rules.get(op, ())):
            raise WriteRefused(f"{self.command} may not {op} {posix}",
                               hint="h2t_ops/core/repo_writers.py lists what each command writes")
        if classify(target) not in ("elsewhere", "tmp", "repo"):
            raise WriteRefused(f"{target} is a package or external place, not a repository", hint="")
        return target

    def create(self, rel: str, data) -> Path:
        t = self._target("create", rel)
        return create(t, data, place="repo", dest=True)

    def replace(self, rel: str, data) -> Path:
        t = self._target("replace", rel)
        return replace(t, data, place="repo", dest=True)

    def append(self, rel: str, line: str) -> None:
        t = self._target("append", rel)
        append(t, line, place="repo", dest=True)

    def mkdir(self, rel: str) -> Path:
        """An empty directory a project layout asks for (src/, tests/): exist_ok. A new one
        is journaled; an existing one is not a write."""
        t = self._target("mkdir", rel)
        existed = t.is_dir()
        mkdir(t, place="repo", dest=True)
        if not existed:
            _log("mkdir", classify(t), t, None)
        return t

    def rename(self, src_rel: str, dst_rel: str, *, git: bool) -> Path:
        src, dst = self._target("rename", src_rel), self._target("rename", dst_rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if git:
            import subprocess
            subprocess.run(["git", "mv", str(src), str(dst)], cwd=self.root, check=True,
                           capture_output=True)
        else:
            os.replace(src, dst)
        _log("rename", "repo", dst, None, key=str(src), digest=_file_sha(dst))
        return dst


_GLOB_CHARS = frozenset("*?[]")


def repo(root, command: str, *, extra_dirs: dict[str, tuple[str, ...]] | None = None) -> RepoWriter:
    """extra_dirs: directories the repository's own config names (docs-lint deliverables_dir),
    literal and relative; each becomes the rule "<dir>/*" for its operation. A glob
    character, an absolute path or .. is refused: config is data, never a pattern."""
    from pathlib import PurePosixPath

    from h2t_ops.core.repo_writers import REPO_WRITERS
    if command not in REPO_WRITERS:
        raise WriteRefused(f"{command!r} is not in the repo allow-list",
                           hint="add it to h2t_ops/core/repo_writers.py with what it writes")
    rules = dict(REPO_WRITERS[command])
    for op, dirs in (extra_dirs or {}).items():
        for d in dirs:
            rel = PurePosixPath(d)
            if (_GLOB_CHARS & set(d)) or ":" in d or rel.is_absolute() or ".." in rel.parts or not rel.parts:
                raise WriteRefused(f"{d!r} is not a literal directory inside the repository",
                                   hint="name a relative directory without * ? [ ]")
            # Refused above already; escaped anyway, so the rule stays literal.
            rules[op] = (*rules.get(op, ()), f"{glob.escape(rel.as_posix())}/*")
    return RepoWriter(Path(root), command, rules)


@contextlib.contextmanager
def scratch(prefix: str = "h2t-") -> Iterator[Path]:
    d = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)
