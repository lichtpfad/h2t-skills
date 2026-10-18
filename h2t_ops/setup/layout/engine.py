"""Layout 1: the phases, their order, resume and the one rule for writing (#548 §8, §7.5).

Runs in the interpreter that launched it (plan R13). Old places are read, never changed:
everything is copied, and the only writes into them are MOVED-TO.txt markers. Every file
the migration publishes has its journal rows first, so a kill anywhere is resumed from the
first unfinished phase and rolled back file by file.
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from h2t_ops.core import paths, store
from h2t_ops.core.errors import ConfigError, H2TError
from h2t_ops.setup.layout import journal as journal_mod
from h2t_ops.setup.layout.journal import Journal

PHASES: tuple[str, ...] = ("snapshot", "secrets", "sessions", "telegram", "evals", "activity",
                           "cursors", "registry", "data", "config_backups", "paths_yaml", "index",
                           "verify", "markers")

_NOT_COPIED = {"downloads", "lake.dor"}   # inbox and lake stay where they are (R2)


class PhaseFailed(H2TError):
    """A phase stops with a hint; the engine puts it in report.failed and stops."""
    kind = "config"


@dataclass
class PhaseContext:
    journal: Journal
    machine: str
    machine_explicit: bool
    report: object
    baseline: set[tuple[str, str]] | None = None


# --- writing -------------------------------------------------------------------------------

def journaled_create(journal: Journal, target: Path, data: bytes, *, place: str, source: str,
                     source_path: Path | None = None, rule: str | None = None,
                     keys: tuple[str, ...] = (), compat: bool = False) -> Path:
    """intent (fsynced) -> store.create -> created (R49)."""
    sha = store.sha256(data)
    journal.intent(target, place, source, sha, source_path, rule)
    store.create(target, data, place=place, keys=keys, compat=compat)
    journal.created(target, place, source, sha, source_path, rule)
    return Path(target)


def _record_sources(journal: Journal, olds, new: Path) -> None:
    for old in olds:
        if old is not None:
            journal.source(Path(old), new)


def _destination(target: Path, sha: str, place: str, label: str) -> tuple[Path, bool]:
    """Where `data` belongs, and whether it is already there."""
    have = journal_mod.current_sha(target, place)
    if have is None or have == sha:
        return target, have is not None
    for candidate in store.unique_name(target.with_name(f"{target.name}.from-{label}")):
        have = journal_mod.current_sha(candidate, place)
        if have is None or have == sha:
            return candidate, have is not None
    raise AssertionError("unreachable")


def put(journal: Journal, target: Path, data: bytes, *, place: str, source: str,
        from_name: str | None = None, source_path: Path | None = None,
        rule: str | None = None, keys: tuple[str, ...] = (),
        sources: tuple[Path, ...] = ()) -> Path:
    """The same hash is the same file; a different one keeps both: the copy is
    <name>.from-<source> beside the target (§8), and on a second clash with yet another
    hash <stem>-2.from-<source> (store.unique_name). Returns the file that holds `data`.
    from_name: the source label in the copy's name, when it differs from `source`.
    source_path: the one old file of a byte copy or a transform (verified, R25); sources:
    every other old file the data was read from (a merge). Each gets a `source` row, also
    when the file is already there, so MOVED-TO.txt reaches its directory."""
    target = Path(target)
    sha = store.sha256(data)
    dest, there = _destination(target, sha, place, from_name or source)
    _record_sources(journal, (source_path, *sources), dest)
    if not there:
        journaled_create(journal, dest, data, place=place, source=source,
                         source_path=source_path, rule=rule, keys=keys)
    return dest


def put_union(journal: Journal, target: Path, data: bytes, *, place: str,
              keys: tuple[str, ...] = (), sources: tuple[Path, ...] = ()) -> Path:
    """Replace a file the migration extends (keys added to an existing provider file): its
    previous bytes go to the rollback directory and the journal before the write.
    sources: the old files the added keys came from (`source` rows, as in put)."""
    target = Path(target)
    _record_sources(journal, sources, target)
    stamp = store.stamp(target)
    prev = journal_mod.current_bytes(target, place)
    if prev is None:
        return journaled_create(journal, target, data, place=place, source="migration", keys=keys)
    if prev == data:
        return target
    journal.replaced(target, place, prev, store.sha256(data), keys=keys)
    store.replace(target, data, place=place, keys=keys, expect=stamp)
    return target


def quiet_sqlite_bytes(src: Path, *, read: Callable[[Path], bytes] = Path.read_bytes) -> bytes:
    """A database copied as bytes must be at rest (R25): no journal beside it, and the same
    size and mtime before and after the read. Otherwise the copy could be torn."""
    src = Path(src)
    if src.suffix == ".session":
        who = "Telegram"
    elif "evals" in src.name:
        who = "the evals process (a Claude session with evals on)"
    else:
        who = f"the program that has {src.name} open"
    hint = f"close {who} and run `h2t-setup layout migrate` again"
    for side in ("-wal", "-journal", "-shm"):
        if src.with_name(src.name + side).exists():
            raise ConfigError(f"{src} has {src.name}{side} beside it: the database is in use",
                              hint=hint)
    before = os.stat(src)
    data = read(src)
    after = os.stat(src)
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ConfigError(f"{src} changed while it was being read", hint=hint)
    return data


# --- the phases this module owns (R24) -----------------------------------------------------

def _size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    total = 0
    for d, _dirs, names in os.walk(p):
        for n in names:
            try:
                total += os.lstat(os.path.join(d, n)).st_size
            except OSError:
                continue
    return total


def _existing(p: Path) -> Path:
    while not p.exists() and p.parent != p:
        p = p.parent
    return p


def phase_snapshot(ctx: PhaseContext) -> None:
    """Free space and the machine name (§5, §8 step 1, R4)."""
    need = 2 * sum(_size(paths.legacy(n)) for n in paths.LEGACY if n not in _NOT_COPIED)
    free = shutil.disk_usage(_existing(paths.root().parent)).free
    if need and free <= need:
        raise PhaseFailed(f"{free} bytes free next to {paths.root()}, the copy needs {need}",
                          hint="free some space and run `h2t-setup layout migrate` again")
    name = ctx.machine
    from h2t_ops.setup import legacy
    if not ctx.machine_explicit:
        # Outside Claude Code the pinned name is not in the environment (R4): a hostname
        # that happens to match another machine's folder would migrate that folder.
        pinned = legacy.pinned_machine_name()
        if pinned and pinned != name:
            raise PhaseFailed(
                f"Claude settings pin H2T_MACHINE_NAME={pinned}, this process sees {name!r}",
                hint=f"run it inside Claude Code, or: h2t-setup layout migrate --machine {pinned}")
        folders = sorted({p.name for key in ("sessions.h2t", "sessions.dor")
                          for root in [paths.legacy(key)] if root.is_dir()
                          for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")})
        if folders and name not in folders:
            raise PhaseFailed(
                f"this machine is {name!r}, and the session folders are {', '.join(folders)}",
                hint="name the machine: h2t-setup layout migrate --machine <name>; "
                     f"the folders: {', '.join(folders)}")
    else:
        got = legacy.ensure_machine_name(name=name)
        if got["status"] == "unchanged" and got.get("value") != name:
            raise PhaseFailed(
                f"Claude settings pin H2T_MACHINE_NAME={got['value']}, not {name}",
                hint=f"Claude settings pin `{got['value']}` ({got['path']}); change it there "
                     "or run without --machine")
        if got["status"] == "error":
            raise PhaseFailed(f"could not pin H2T_MACHINE_NAME: {got['error']}",
                              hint=f"fix {got['path']} and run `h2t-setup layout migrate` again")
    ctx.journal.machine(name)


def phase_config_backups(ctx: PhaseContext) -> None:
    """config/*.yaml.bak* -> state/backups/<name>.<mtime>, then out of config/ (R14)."""
    cfg = paths.config_dir()
    if not cfg.is_dir():
        return
    for f in sorted(cfg.glob("*.yaml.bak*")):
        if not f.is_file():
            continue
        data = f.read_bytes()
        when = time.strftime("%Y%m%d-%H%M%S", time.localtime(f.stat().st_mtime))
        # No source_path: the source leaves config/ below, so a hash check against it would
        # fail; the removed row holds its bytes.
        put(ctx.journal, paths.backups_dir() / f"{f.name}.{when}", data, place="state",
            source="config", sources=(f,))
        with store.migrating():
            ctx.journal.removed(f, "config", prev=data)
            store.remove(f, place="config")


def _inside(a: Path, b: Path) -> bool:
    return a == b or b in a.parents


def _moved_from(journal: Journal) -> dict[Path, set[str]]:
    """Old directory -> the new directories its files were copied to. A source inside a
    place the user declared (lake: ~/.dor/lake, R2) is that place, not an old one."""
    roots = sorted(((r, Path(os.path.realpath(r))) for r in paths.legacy_roots()),
                   key=lambda kv: len(kv[1].parts), reverse=True)
    out: dict[Path, set[str]] = {}
    for row in journal.entries():
        if row["op"] != "source":
            continue
        src = Path(row["old"])
        if store.classify(src) != "legacy":
            continue
        real = Path(os.path.realpath(src))
        for root, real_root in roots:
            if _inside(real, real_root):
                out.setdefault(root, set()).add(str(Path(row["new"]).parent))
                break
    return out


def phase_markers(ctx: PhaseContext) -> None:
    """MOVED-TO.txt in every old directory something was copied from, then layout.json (R44)."""
    today = datetime.date.today().isoformat()
    with store.migrating():
        for root, targets in sorted(_moved_from(ctx.journal).items()):
            marker = root / "MOVED-TO.txt"
            if marker.exists() or store.classify(root) != "legacy":
                continue
            text = (f"h2t 4.0 copied this directory's files on {today} (layout 1).\n"
                    "Nothing here was changed or removed; the package no longer reads it after 4.0.x.\n"
                    "The new places:\n" + "".join(f"  {t}\n" for t in sorted(targets)))
            try:
                journaled_create(ctx.journal, marker, text.encode("utf-8"), place="legacy",
                                 source="migration", compat=True)
            except store.AlreadyExists:
                continue
    f = paths.layout_file()
    doc = {"layout": 1, "machine": ctx.machine,
           "migrated_at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "journal": ctx.journal.run_id}
    data = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
    prev = journal_mod.current_bytes(f, "layout")
    if prev is None:
        journaled_create(ctx.journal, f, data, place="layout", source="migration")
        return
    if _read_layout(prev).get("journal") == ctx.journal.run_id:
        return                          # this run wrote it before a kill
    stamp = store.stamp(f)
    ctx.journal.replaced(f, "layout", prev, store.sha256(data))
    store.replace(f, data, place="layout", expect=stamp)


def _phase_funcs() -> dict[str, Callable[[PhaseContext], None]]:
    """The explicit table (R24); Tasks 22-23 add their phases here."""
    return {
        "snapshot": phase_snapshot,
        "config_backups": phase_config_backups,
        "markers": phase_markers,
    }


# --- the run -------------------------------------------------------------------------------

def _read_layout(data: bytes | None) -> dict:
    try:
        doc = json.loads(data) if data else {}
    except ValueError:
        return {}
    return doc if isinstance(doc, dict) else {}


def _remedy(exc: BaseException) -> str:
    if isinstance(exc, H2TError):
        return "\n".join(s for s in (str(exc), exc.hint) if s)
    return f"{type(exc).__name__}: {exc}"


def migrate(report, *, machine: str | None = None,
            funcs: dict[str, Callable] | None = None) -> None:
    table = _phase_funcs() if funcs is None else funcs
    missing = [p for p in PHASES if p not in table]
    if missing:
        for p in missing:
            report.failed.append((f"layout 1: {p} is not implemented",
                                  "this build has no function for the phase; nothing was written"))
        return
    with journal_mod.exclusive():       # ConfigError (exit 3) if another one holds it
        _run(report, machine, table)


def _run(report, machine: str | None, table: dict[str, Callable]) -> None:
    explicit = machine is not None
    pending = [j for j in Journal.all() if j.rollback_pending()]
    if pending:
        # Its files are half restored; a new run would build on them and leave the rest of
        # that journal unreachable by rollback.
        raise ConfigError(f"the rollback of {pending[-1].run_id} did not finish",
                          hint="finish it first: h2t-setup layout rollback --sync-paused",
                          details={"reason": "rollback_pending", "journal": str(pending[-1].dir)})
    journal_mod.prune()
    latest = Journal.latest()
    if latest is not None and latest.resumable():
        journal = latest
        for path in journal.reconcile():
            report.notes.append(f"layout 1: {path} changed after an interrupted write; left as is")
        recorded = journal.recorded_machine()
        if recorded and machine is not None and machine != recorded:
            report.failed.append((
                "layout 1: snapshot",
                f"the interrupted migration {journal.run_id} runs for {recorded!r}, not {machine!r}\n"
                "run `h2t-setup layout migrate` without --machine to finish it"))
            return
        machine = machine or recorded
    else:
        if _read_layout(journal_mod.current_bytes(paths.layout_file(), "layout")).get("layout") == 1:
            report.notes.append("layout 1: already")
            return
        journal = Journal(journal_mod.new_run_id())
    ctx = PhaseContext(journal=journal, machine=machine or paths.machine_name(),
                       machine_explicit=explicit, report=report)
    done = journal.done_phases()
    for phase in PHASES:
        if phase in done:
            continue
        try:
            table[phase](ctx)
        except Exception as exc:        # a kill (KeyboardInterrupt) is not caught: resume
            report.failed.append((f"layout 1: {phase}", _remedy(exc)))
            return
        journal.phase_done(phase)
    report.done.append("layout 1")
    report.notes.append(f"layout 1: journal {journal.dir}")
