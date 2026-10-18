"""Who touched a file (#548 §7.3). Python-level only: C extensions that make their own
syscalls and child processes after Popen are invisible here — the directory permissions of
the sandbox are the guarantee there, and the verdict is «no bypass through Python found».

Also invisible: os.open(name, dir_fd=…) — the "open" audit event carries no dir_fd, so a
relative name is resolved against cwd. The fd-relative os.* events below are resolved."""
from __future__ import annotations

import contextlib
import os
import sys
import threading
import urllib.parse
from pathlib import Path

_DOORS = ("h2t_ops/core/store.py", "h2t_ops/core/secrets.py")
# One active recorder for the whole process: events raised in worker threads (the meetgeek
# webhook ThreadingHTTPServer, executors) must reach it. Only the re-entrancy guard is
# per-thread.
_ACTIVE: list = [None]
_GUARD = threading.local()
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
_UNRESOLVED = "<fd-relative path not resolved>"


def _fd_path(fd: int) -> str | None:
    """The directory an open fd points at: F_GETPATH on macOS, /proc on Linux."""
    try:
        if sys.platform == "darwin":
            import fcntl
            return os.fsdecode(fcntl.fcntl(fd, fcntl.F_GETPATH, b"\0" * 1024).rstrip(b"\0"))
        if sys.platform.startswith("linux"):
            return os.readlink(f"/proc/self/fd/{fd}")
    except OSError:
        return None
    return None


def _join(path, dir_fd) -> str:
    p = os.fsdecode(path)
    if dir_fd in (None, -1) or os.path.isabs(p):
        return p
    base = _fd_path(dir_fd)
    return os.path.join(base, p) if base else _UNRESOLVED


def _stack_has_door() -> bool:
    f = sys._getframe(2)
    while f is not None:
        name = f.f_code.co_filename.replace("\\", "/")
        if name.endswith(_DOORS):
            return True
        f = f.f_back
    return False


def _writer_modules() -> set[str]:
    """Every h2t_ops module on the stack of this write, outside the doors: a connector that
    writes through a helper (core/lake.py) counts as a writer too (plan R27)."""
    out: set[str] = set()
    f = sys._getframe(2)
    while f is not None:
        name = f.f_code.co_filename.replace("\\", "/")
        if "/h2t_ops/" in name and not name.endswith(_DOORS):
            out.add(name.rsplit("/h2t_ops/", 1)[1])
        f = f.f_back
    return out


def _paths(event: str, args: tuple) -> list[tuple[str, bool]]:
    """(path, is_write) pairs an event touches."""
    if event == "open":
        path, mode, flags = args
        if not isinstance(path, (str, bytes, os.PathLike)):
            return []
        write = bool(mode and any(c in str(mode) for c in "wax+")) or bool(flags & _WRITE_FLAGS)
        return [(os.fsdecode(path), write)]
    if event == "os.rename":                       # (src, dst, src_dir_fd, dst_dir_fd)
        return [(_join(args[0], args[2]), True), (_join(args[1], args[3]), True)]
    if event == "os.link":                         # (src, dst, src_dir_fd, dst_dir_fd)
        return [(_join(args[0], args[2]), True), (_join(args[1], args[3]), True)]
    if event == "os.symlink":                      # (src, dst, dir_fd): the link is the write
        return [(_join(args[1], args[2]), True)]
    if event in ("os.remove", "os.rmdir"):         # (path, dir_fd)
        return [(_join(args[0], args[1]), True)] if isinstance(args[0], (str, bytes, os.PathLike)) else []
    if event in ("os.mkdir", "os.chmod"):          # (path, mode, dir_fd)
        return [(_join(args[0], args[2]), True)] if isinstance(args[0], (str, bytes, os.PathLike)) else []
    if event == "shutil.rmtree":                   # (path, dir_fd)
        return [(_join(args[0], args[1]), True)]
    if event in ("shutil.copyfile", "shutil.copytree", "shutil.move"):
        return [(os.fsdecode(args[0]), False), (os.fsdecode(args[1]), True)]
    if event == "sqlite3.connect":
        if not args or args[0] in (":memory:", ""):
            return []
        p = os.fsdecode(args[0])
        if p.startswith("file:"):                  # uri=True: the path, and mode=ro is a read
            u = urllib.parse.urlsplit(p)
            mode = urllib.parse.parse_qs(u.query).get("mode", ["rwc"])[0]
            return [(urllib.parse.unquote(u.path), mode != "ro")]
        return [(p, True)]
    return []


class Recorder:
    def __init__(self, guarded: list[Path], secret_dirs: list[Path], legacy: list[Path],
                 twins: dict[Path, Path | tuple[Path, tuple[str, ...]]], *,
                 confine: bool = False, allow: tuple[Path, ...] = ()):
        """twins: legacy secret file → its one new counterpart (§7.3: reading the old one
        while the new one holds it is red, whoever reads — secrets.py included). A JSON or
        session twin holds it by existing; an env twin, given as (file, keys), only when it
        has a non-empty value for every key the old file supplies — the fallback is per key.
        confine: a write outside every guarded root is a violation too, door or not — the
        sandbox's places are the whole world a command may write (§7.3); allow names the
        few exceptions (os.devnull). The interpreter's own bytecode cache (__pycache__) is
        not a write of the command: a module imported for the first time inside a case
        compiles there, which made the check depend on test order."""
        self.guarded = [Path(os.path.realpath(p)) for p in guarded]
        self.secret_dirs = [Path(os.path.realpath(p)) for p in secret_dirs]
        self.legacy = [Path(os.path.realpath(p)) for p in legacy]
        self.twins = {Path(os.path.realpath(k)): (v if isinstance(v, tuple) else (Path(v), None))
                      for k, v in twins.items()}
        self.confine = confine
        self.allow = [Path(os.path.realpath(p)) for p in allow]
        self.violations: list[str] = []
        self.legacy_writes: list[Path] = []
        self.writers: set[str] = set()
        self.popen: list[list[str]] = []

    def _under(self, real: Path, roots: list[Path]) -> bool:
        return any(real == r or r in real.parents for r in roots)

    @staticmethod
    def _twin_holds(twin: Path, keys: tuple[str, ...] | None) -> bool:
        if not twin.exists():
            return False
        if keys is None:
            return True
        from h2t_ops.core.secrets import parse_env
        values = parse_env(twin.read_text(encoding="utf-8"))   # the hook is off while it runs
        return all(values.get(k) for k in keys)

    def check(self, event: str, args: tuple) -> None:
        if event == "subprocess.Popen":
            self.popen.append([os.fsdecode(a) for a in (args[1] or [])])
            return
        from h2t_ops.core import store
        for raw, write in _paths(event, args):
            if raw == _UNRESOLVED:
                self.violations.append(f"{event} {_UNRESOLVED}")
                continue
            real = Path(os.path.realpath(raw))
            if write:
                self.writers |= _writer_modules()
            if write and self._under(real, self.legacy):
                self.legacy_writes.append(real)
            twin, keys = self.twins.get(real, (None, None))
            if not write and twin is not None and self._twin_holds(twin, keys):
                self.violations.append(f"{event} read {real} while {twin} holds it")
                continue
            secret = self._under(real, self.secret_dirs)
            if write and self.confine and not self._under(real, self.guarded) \
                    and not self._under(real, self.allow) and "__pycache__" not in real.parts:
                self.violations.append(f"{event} write {real} outside every place")
                continue
            if not (write or secret) or not self._under(real, self.guarded):
                continue
            if _stack_has_door() or store.delegated(real):
                continue
            self.violations.append(f"{event} {'write' if write else 'read'} {real}")

    @contextlib.contextmanager
    def active(self):
        _ACTIVE[0] = self
        try:
            yield self
        finally:
            _ACTIVE[0] = None


def _hook(event: str, args: tuple) -> None:
    rec = _ACTIVE[0]
    if rec is None or getattr(_GUARD, "inside", False):
        return
    _GUARD.inside = True
    try:
        rec.check(event, args)
    finally:
        _GUARD.inside = False


sys.addaudithook(_hook)  # cannot be removed; it is inert unless a Recorder is active
