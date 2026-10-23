"""The daily pass: backfill, index refresh, settle, branch status, model summaries, audit_map.

The first SessionStart of a day starts it detached (`maybe_spawn`); `h2t-ops sessions daily`
runs it. Its stamp holds the time of the last run, the backfill cut-off and the audit_map answer.
"""
from __future__ import annotations

import contextlib
import csv
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from h2t_ops.core import paths, store, user_config
from h2t_ops.lifecycle.index import query
from h2t_ops.lifecycle.pulse import backfill, record, status, summary

_DAY_NS = 86400 * 10**9
_STALE_LOCK_S = 2 * 3600
_AUDIT_TIMEOUT_S = 300
TOKEN_ENV = "H2T_PULSE_DAILY_TOKEN"     # owner token of the lock: the lock file holds it, the child gets it


def stamp_path() -> Path:
    return paths.state_dir() / "pulse-daily.json"


def lock_path() -> Path:
    return paths.state_dir() / "pulse-daily.lock"


def _now() -> datetime:
    return datetime.now(UTC)


def read_stamp() -> dict:
    try:
        doc = json.loads(stamp_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _fresh(stamp: dict, now: datetime) -> bool:
    try:
        ran = datetime.fromisoformat(stamp["ran_at"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError):
        return False
    if ran.tzinfo is None:          # a naive time cannot be compared with now: treat as stale
        return False
    return now - ran < timedelta(hours=24)


def _takeover_gate() -> Path:
    return paths.state_dir() / "locks" / "pulse-daily-takeover.lock"


def _take_over(lock: Path, payload: str) -> bool:
    """Replace a lock older than 2 h. Two sessions can see the same stale lock, so the
    check-remove-create runs under one lock: the second one re-reads a fresh lock and yields."""
    with store.locked(_takeover_gate(), place="state"):
        try:
            if time.time() - lock.stat().st_mtime < _STALE_LOCK_S:
                return False
            store.remove(lock, place="state")
            store.create(lock, payload, place="state")
        except (FileNotFoundError, store.AlreadyExists):    # someone else has it
            return False
    return True


def maybe_spawn(now: datetime | None = None) -> bool:
    """Start the daily pass detached when the stamp is older than 24 h. One run at a time:
    the lock is created atomically; a lock younger than 2 h means a run is going."""
    now = now or _now()
    if _fresh(read_stamp(), now):
        return False
    lock = lock_path()
    payload = uuid.uuid4().hex          # owner token: only its holder may remove the lock
    try:
        store.create(lock, payload, place="state")
    except store.AlreadyExists:
        if not _take_over(lock, payload):
            return False
    flags: dict = {"start_new_session": True}
    if sys.platform == "win32":
        flags = {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
    try:
        subprocess.Popen([sys.executable, "-m", "h2t_ops.cli", "sessions", "daily"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         env={**os.environ, TOKEN_ENV: payload}, **flags)
    except BaseException:
        store.remove(lock, place="state")
        raise
    return True


def audit_map() -> dict:
    """Run the external audit_map from `sessions.audit_map` (argv list in user.yaml).
    {} when not configured; {"error": reason} on any failure; never raises."""
    argv = user_config.get("sessions.audit_map")
    if not argv:
        return {}
    if not isinstance(argv, list):
        return {"error": "sessions.audit_map должен быть списком аргументов"}
    try:
        return _audit(argv)
    except Exception as exc:  # noqa: BLE001 - audit_map is a helper line; nothing in it may stop the pass
        return {"error": f"{type(exc).__name__}: {exc}"}


def _audit(argv: list) -> dict:
    out = store.mkdir(paths.state_dir(), place="state") / "audit-map.tsv"
    store.remove(out, place="state")
    try:
        done = subprocess.run([*map(str, argv), "--out", str(out)], capture_output=True,
                              timeout=_AUDIT_TIMEOUT_S, check=False)
    except subprocess.TimeoutExpired:
        return {"error": f"таймаут {_AUDIT_TIMEOUT_S} с"}
    except OSError as exc:
        return {"error": f"не запустился: {exc.strerror or exc}"}
    if done.returncode != 0:
        return {"error": f"код выхода {done.returncode}"}
    try:
        with out.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f, delimiter="	"))
        branches = sum(max(int(r["branch_count"]) - 1, 0) for r in rows)
        stash = sum(int(r["stash_count"]) for r in rows)
    except (OSError, KeyError, ValueError, TypeError, csv.Error):
        return {"error": "нет отчёта audit-map.tsv или в нём нет колонок branch_count, stash_count"}
    if not rows:
        return {"error": "отчёт пуст"}
    return {"branches": branches, "stash": stash, "report": str(out),
            "ran_at": _now().strftime("%Y-%m-%dT%H:%M:%SZ")}


def _own_lock() -> str:
    """Token of the lock this pass owns: the spawner's (env), else a lock created now by a
    manual run; "" when a manual run finds a lock that is not its own (it never touches it)."""
    token = os.environ.get(TOKEN_ENV, "")
    if token:
        return token
    token = uuid.uuid4().hex
    try:
        store.create(lock_path(), token, place="state")
    except store.AlreadyExists:
        return ""
    return token


def _release(token: str) -> None:
    """Remove the lock only while it still holds our token (a takeover may have replaced it)."""
    if not token:
        return
    with contextlib.suppress(OSError), store.locked(_takeover_gate(), place="state"):
        if lock_path().read_text(encoding="utf-8") == token:
            store.remove(lock_path(), place="state")


def run() -> dict:
    """The whole pass; stamps it and releases its own lock whatever happens."""
    token = _own_lock()
    try:
        previous = read_stamp()
        started_ns = time.time_ns()
        since = max(int(previous.get("backfill_since_ns") or 0) - _DAY_NS, 0)
        counts = backfill.run(since_ns=since)
        with query.connect():                    # opening refreshes the index from the new records
            pass
        record.settle_open()
        with query.connect() as conn:            # a second open sees what settle changed
            status.refresh(conn)
            summaries = summary.run(conn)
        result = {"ran_at": _now().strftime("%Y-%m-%dT%H:%M:%SZ"), "backfill_since_ns": started_ns,
                  "audit_map": audit_map()}
        store.replace(stamp_path(), json.dumps(result, ensure_ascii=False), place="state")
        return {**result, "backfill": counts, "summary": summaries}
    finally:
        _release(token)
