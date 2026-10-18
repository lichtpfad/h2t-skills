"""`h2t-setup layout rollback --sync-paused` (#548 §7.5, plan R8, R44, R49).

Reads the latest migration journal backwards. A file is removed only while it still has
the hash it was written with, a replaced or removed file comes back from the bytes saved
before the change, and anything changed since is listed, not touched. Run again after an
interruption, it reaches the same end: what is already undone is recognised by its hash.
The only site of store.remove(journal=True) in the package (plan R1).
"""
from __future__ import annotations

from pathlib import Path

from h2t_ops.core import store
from h2t_ops.core.errors import NotFoundError, UsageError
from h2t_ops.setup.layout.journal import Journal, current_sha, exclusive

PAUSE = ("pause the sync of ~/.h2t/records/ and ~/.h2t/secrets/shared/ first: a rollback "
         "removes files, and with sync running the removals reach your other machines")


def rollback(*, sync_paused: bool) -> dict:
    if not sync_paused:
        raise UsageError(f"h2t-setup layout rollback: {PAUSE}",
                         hint="pause it, then run `h2t-setup layout rollback --sync-paused`")
    with exclusive():                   # ConfigError (exit 3) if a migrate or rollback runs
        # An interrupted rollback first: newer journals may exist, but its files are the
        # half-restored ones (migrate refuses to run past it).
        pending = [j for j in Journal.all() if j.rollback_pending()]
        journal = pending[-1] if pending else Journal.latest()
        if journal is None:
            raise NotFoundError("no migration journal under run/rollback/",
                                hint="nothing to roll back: `h2t-setup layout migrate` has not run here")
        out: dict = {"journal": str(journal.dir), "removed": [], "restored": [], "kept": []}
        rows = journal.entries()
        created = {r["path"] for r in rows if r["op"] == "created"}
        journal.rolling_back()
        with store.migrating():         # MOVED-TO.txt in the old directories (R1)
            for row in reversed(rows):
                op = row["op"]
                if op == "intent" and row["path"] in created:
                    continue
                if op in ("created", "intent"):
                    _undo_create(row, out)
                elif op == "replaced":
                    _undo_replace(row, journal, out)
                elif op == "removed":
                    _undo_remove(row, journal, out)
        journal.rollback_done()
    return out


def _undo_create(row: dict, out: dict) -> None:
    path = Path(row["path"])
    now = current_sha(path, row["place"])
    if now is None:
        return
    if now == row["sha256"]:
        store.remove(path, place=row["place"], journal=True)
        out["removed"].append(str(path))
    else:
        out["kept"].append(str(path))


def _undo_replace(row: dict, journal: Journal, out: dict) -> None:
    path = Path(row["path"])
    now = current_sha(path, row["place"])
    if now == row["prev_sha"]:
        return                          # already returned by an interrupted rollback
    if now == row["new_sha"]:
        store.replace(path, journal.prev_bytes(row["prev"]), place=row["place"])
        out["restored"].append(str(path))
    else:
        out["kept"].append(str(path))


def _undo_remove(row: dict, journal: Journal, out: dict) -> None:
    path = Path(row["path"])
    now = current_sha(path, row["place"])
    if now == row["prev_sha"]:
        return
    if now is None:
        store.create(path, journal.prev_bytes(row["prev"]), place=row["place"])
        out["restored"].append(str(path))
    else:
        out["kept"].append(str(path))
