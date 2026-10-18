"""Layout 1, the phases after `secrets` (#548 §8 п. 3–5; plan R2, R9, R15, R22, R25).

Each reads its old place and writes through engine.put, so a file already there with the
same hash is the same file and a different one keeps both. Byte copies carry source_path
(verify_copies checks them by hash); transformed copies carry a rule (verify_transformed).
"""
from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

import yaml

from h2t_ops.core import paths, secrets, store
from h2t_ops.core.errors import ConfigError
from h2t_ops.lifecycle import session_record
from h2t_ops.setup.layout import engine, secrets_phase
from h2t_ops.setup.layout import journal as journal_mod

# The suite's fixture values that leaked into the author's spool (#441, conftest.py docstring).
# tests/core/test_session_identity_roundtrip.py, tests/core/test_handoff_identity_from_cwd.py
PYTEST_SESSION_IDS = frozenset({
    "personal-os-h2t-skills-topic-2026-08-22", "personal-os-h2t-skills-new-2026-08-22",
    "personal-os-dor-core-topic-2026-08-22", "dev-docgraph-topic-2026-08-22",
    "some-session-2026-08-23",
})
PYTEST_PROJECTS = frozenset({"explicit-id", "derived-id", "unmapped-checkout"})

_SESSIONS = "records.sessions"
_RETRY = "run `h2t-setup layout migrate` again"


# --- sessions ------------------------------------------------------------------------------

def _header(text: str, name: str) -> str | None:
    m = re.search(rf"^\s*-?\s*\*\*{name}:\*\*\s*(.*?)\s*$", text, re.M)
    return m.group(1) if m and m.group(1) else None


def _latest(leaf: Path, stem: str) -> dict:
    """The fields latest.json gives a session — only the session it names."""
    try:
        doc = json.loads((leaf / "latest.json").read_bytes().decode("utf-8-sig"))
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict) or doc.get("session_id") != stem:
        return {}
    return {new: doc[old] for old, new in (("summary_short", "done"), ("next_actions", "remains"),
                                           ("updated_at", "updated_at"), ("artifacts", "artifacts"))
            if doc.get(old) not in (None, "", [])}


def session_meta(src: Path, raw: bytes, *, machine: str, project: str) -> dict:
    """The frontmatter of a 3.x md: its directory, latest.json, its header, its mtime."""
    text = raw.decode("utf-8", errors="replace")
    meta: dict = {"session_id": src.stem, "machine": machine, "project": project}
    for field, name in (("domain", "Domain"), ("date", "Date")):
        value = _header(text, name)
        if value:
            meta[field] = value
    meta.update(_latest(src.parent, src.stem))
    if "updated_at" not in meta:
        if "date" in meta:
            meta["updated_at"] = f"{meta['date']}T00:00:00Z"
        else:
            when = datetime.datetime.fromtimestamp(src.stat().st_mtime, datetime.UTC)
            meta["updated_at"] = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    meta["migrated_from"] = f"{src}@{store.sha256(raw)}"
    return meta


def _body_sha(path: Path) -> str | None:
    data = journal_mod.current_bytes(path, _SESSIONS)
    if data is None:
        return None
    try:
        return store.sha256(session_record.parse(data)[1])
    except ValueError:
        return None


def _same_body(target: Path, body_sha: str) -> Path | None:
    """The record, or one of its .from- copies, whose body is this one. The assembled files
    differ whenever migrated_from does, so bodies are what tell the same session apart."""
    copy = re.compile(re.escape(target.name) + r"(-\d+)?\.from-")
    found = [target] if target.is_file() else []
    if target.parent.is_dir():
        found += sorted(p for p in target.parent.iterdir() if copy.match(p.name))
    return next((p for p in found if _body_sha(p) == body_sha), None)


def _session_sources(machine: str):
    for label, key in (("h2t", "sessions.h2t"), ("dor", "sessions.dor")):
        base = paths.legacy(key) / machine          # other machines' come by sync (§8 п. 3)
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*.md")):
            if f.is_file():
                rel = f.relative_to(base).parts
                yield label, f, rel[0] if len(rel) > 1 else None


def phase_sessions(ctx) -> None:
    for label, src, project in _session_sources(ctx.machine):
        raw = src.read_bytes()
        project = project or _header(raw.decode("utf-8", errors="replace"), "Project") or "unknown"
        target = session_record.session_path(ctx.machine, project, src.stem)
        held = _same_body(target, store.sha256(raw))
        if held is not None:
            # The same session in both old directories: nothing is written, the old file
            # still points at the record that holds it (MOVED-TO.txt).
            ctx.journal.source(src, held, place=_SESSIONS,
                               sha256=journal_mod.current_sha(held, _SESSIONS))
            continue
        data = session_record.render(session_meta(src, raw, machine=ctx.machine, project=project), raw)
        engine.put(ctx.journal, target, data, place=_SESSIONS, source=label, source_path=src,
                   rule="session-body")


def session_body_holds(src_raw: bytes, target_raw: bytes, source_path: str) -> bool:
    """Rule "session-body": the body after the frontmatter is the source, byte for byte,
    and migrated_from names the source and its hash."""
    try:
        meta, body = session_record.parse(target_raw)
    except ValueError:
        return False
    return body == src_raw and meta.get("migrated_from") == f"{source_path}@{store.sha256(src_raw)}"


# --- telegram, cursors, registry, data: byte copies ----------------------------------------

def _copy(ctx, src: Path, target: Path, *, place: str, source: str) -> None:
    engine.put(ctx.journal, target, src.read_bytes(), place=place, source=source, source_path=src)


def phase_telegram(ctx) -> None:
    """Only the marker: the session and auth state went with the secrets (§8 п. 2)."""
    src = paths.legacy("telegram") / "dialogs_bootstrapped"
    if src.is_file():
        _copy(ctx, src, paths.state_dir() / "telegram" / src.name, place="state", source="telegram")


def phase_cursors(ctx) -> None:
    for provider in ("granola", "meetgeek"):
        src = paths.legacy("lake.dor") / "_cursors" / f"{provider}.json"
        if src.is_file():
            _copy(ctx, src, paths.state_dir() / "cursors" / src.name, place="state", source="dor")


def phase_registry(ctx) -> None:
    src = paths.legacy("registry.dor")
    if src.is_file():
        _copy(ctx, src, paths.records("imports") / "dor-registry.jsonl", place="records.imports",
              source="dor")


def phase_data(ctx) -> None:
    """research and creative profiles (R9), every file under them."""
    for key, dest in (("research", paths.data_dir() / "research"),
                      ("creative", paths.data_dir() / "creative" / "profiles")):
        base = paths.legacy(key)
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*")):
            if f.is_file() and f.name != "MOVED-TO.txt":
                _copy(ctx, f, dest / f.relative_to(base), place="data", source="h2t")


# --- evals ---------------------------------------------------------------------------------

_EVALS_WHO = "the evals process (a Claude session with evals on)"


def evals_spool_source() -> Path:
    """The spool 3.x evals wrote (eval/session.py:299-303): the variable from the
    environment, then the same key in the secret files, ~/.dor/secrets.env first (R22)."""
    for value in paths.old_env_by_use("evals-spool-source").values():
        return value
    names = [n for n, u in paths.OLD_ENV.items() if u == "evals-spool-source"]
    for _, _, vals in secrets_phase.evals_ladder(secrets.migration_sources()):
        for name in names:
            if vals.get(name):
                return paths.expand_user_dest(vals[name])
    return paths.legacy("evals") / ".h2t_evals_spool.db"


def _read_spool(p: Path) -> bytes:
    return Path(p).read_bytes()


def phase_evals(ctx) -> None:
    # The spool is read first: one in use stops the phase with nothing written (R25).
    spool = evals_spool_source()
    data = engine.quiet_sqlite_bytes(spool, read=_read_spool, who=_EVALS_WHO) \
        if spool.is_file() else None
    base = paths.legacy("evals")
    if base.is_dir():
        for skill in sorted(p for p in base.iterdir() if p.is_dir()):
            for f in sorted((skill / "sessions").glob("*.json")):
                if f.is_file():
                    _copy(ctx, f, paths.records("evals", ctx.machine) / skill.name / f.name,
                          place="records.evals", source="evals")
    if data is not None:
        engine.put(ctx.journal, paths.evals_spool(), data, place="state", source="evals",
                   source_path=spool)


# --- activity ------------------------------------------------------------------------------

def _lines(raw: bytes) -> list[bytes]:
    return [ln if ln.endswith(b"\n") else ln + b"\n" for ln in raw.splitlines(keepends=True)]


def _row_key(line: bytes) -> bytes:
    """A row without its line ending: a CRLF row from a 3.x spool written on Windows and the
    LF one store.append writes are the same row. Only comparisons use this; bytes are kept."""
    return line.rstrip(b"\r\n")


def _is_test_row(line: bytes) -> bool:
    try:
        row = json.loads(line)
    except ValueError:
        return False
    return isinstance(row, dict) and (row.get("session_id") in PYTEST_SESSION_IDS
                                      or row.get("project") in PYTEST_PROJECTS)


def filter_activity(raw: bytes) -> tuple[bytes, int]:
    """The spool without the rows the suite left (R15), and how many were dropped. Each kept
    line ends with a newline; nothing else changes."""
    lines = _lines(raw)
    kept = [ln for ln in lines if not _is_test_row(ln)]
    return b"".join(kept), len(lines) - len(kept)


def merge_activity(live: bytes, filtered: bytes) -> bytes:
    """The legacy rows the live file lacks (by exact line), then the live file unchanged: rows
    a 4.0 session appended are never rewritten, only preceded by the older ones."""
    have = {_row_key(ln) for ln in _lines(live)}
    add = [ln for ln in _lines(filtered) if _row_key(ln) not in have]
    if live and not live.endswith(b"\n"):
        live += b"\n"
    return b"".join(add) + live


def activity_holds(src_raw: bytes, target_raw: bytes) -> bool:
    """Rule "activity-filter" on a file that may hold live rows too: every row the filter
    keeps is in the target, and no row it drops is. Rows a session appends later neither
    add nor remove a legacy row, so they do not read as a mismatch."""
    kept, _ = filter_activity(src_raw)
    keep = {_row_key(ln) for ln in _lines(kept)}
    dropped = {_row_key(ln) for ln in _lines(src_raw)} - keep
    have = {_row_key(ln) for ln in _lines(target_raw)}
    return keep <= have and not (dropped & have)


def phase_activity(ctx) -> None:
    src = paths.legacy("activity") / "spool.jsonl"
    if not src.is_file():
        return
    raw = src.read_bytes()
    filtered, skipped = filter_activity(raw)
    target, place = paths.activity_file(ctx.machine), "records.activity"
    # A live session appends to this file: its append waits on the lock held here from the
    # read to the publication, then lands in the merged file (store.merging).
    with store.merging(target, place=place):
        stamp = store.stamp(target)
        live = journal_mod.current_bytes(target, place)
        if live is None:
            engine.put(ctx.journal, target, filtered, place=place, source="activity",
                       source_path=src, rule="activity-filter")
        else:
            data = merge_activity(live, filtered)
            ctx.journal.source(src, target, place=place, sha256=store.sha256(data))
            if data != live:
                ctx.journal.replaced(target, place, live, store.sha256(data), source_path=src,
                                     rule="activity-filter")
                try:
                    store.replace(target, data, place=place, expect=stamp)
                except store.Changed as exc:   # a writer that bypassed store
                    raise ConfigError(f"{target} changed while the migration merged into it",
                                      hint=f"wait for the running sessions to settle and {_RETRY}") from exc
    if skipped:
        ctx.report.notes.append(f"layout 1: activity: {skipped} test rows skipped")


# --- paths.yaml, index ---------------------------------------------------------------------

def phase_paths_yaml(ctx) -> None:
    """Only what exists (R2), and no file when nothing does; vault is never written here
    (R12). A file already there, the user's own, is left alone. Places under home are
    written as ~/… (§6): config/ syncs, and an expanded /Users/<name>/… is not even an
    absolute path on the Windows machines it reaches."""
    f = paths.paths_yaml()
    if f.exists():
        return
    places: dict[str, str] = {}
    lake = next(iter(paths.old_env_by_use("lake").values()), None)
    if lake is None and paths.legacy("lake.dor").exists():
        lake = paths.legacy("lake.dor")
    if lake is not None:
        places["lake"] = paths.home_form(lake)
    if paths.legacy("downloads").exists():
        places["inbox"] = paths.home_form(paths.legacy("downloads"))
    if not places:
        return          # nothing to declare: an empty file would block the write once a lake appears
    doc = {"version": 1, "places": places}
    paths.validate_config(doc, source=f)
    try:
        engine.journaled_create(ctx.journal, f, yaml.safe_dump(doc, sort_keys=False).encode("utf-8"),
                                place="config", source="migration")
    except store.AlreadyExists:
        return
    paths.paths_config()


def _eligible_sessions() -> tuple[int, int]:
    """(md the index should hold, md it should list as problems) under
    records/sessions/*/*/: every machine's, the ones already there included."""
    from h2t_ops.lifecycle.index import build
    ok = bad = 0
    base = paths.records("sessions")
    for leaf in build._leaves(base):
        for f in sorted(leaf.iterdir()):
            if f.suffix != ".md" or ".from-" in f.name or not f.is_file():
                continue
            try:                    # as the index: unreadable is a problem, not a stop
                meta, _ = session_record.parse(f.read_bytes())
            except (ValueError, OSError):
                bad += 1
                continue
            if all(meta.get(k) for k in build.REQUIRED):
                ok += 1
            else:
                bad += 1
    return ok, bad


def phase_index(ctx) -> None:
    from h2t_ops.lifecycle import index
    index.rebuild()
    want_ok, want_bad = _eligible_sessions()
    base = str(paths.records("sessions"))
    with index.connect(refresh=False) as conn:
        got_ok = conn.execute("SELECT count(*) FROM sessions").fetchone()[0]
        got_bad = sum(1 for (p,) in conn.execute("SELECT path FROM problems")
                      if p.startswith(base))
    if (got_ok, got_bad) != (want_ok, want_bad):
        raise engine.PhaseFailed(
            f"the index holds {got_ok} sessions and {got_bad} problems; "
            f"records/sessions has {want_ok} readable md and {want_bad} unreadable",
            hint=f"h2t-ops index rebuild, then {_RETRY}")
    if want_bad:
        ctx.report.notes.append(f"layout 1: index: {want_bad} session md unreadable, "
                                "see h2t-ops index query")
