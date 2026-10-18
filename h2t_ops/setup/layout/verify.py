"""Layout 1, phase `verify` (#548 §8 п. 6, plan R25, R37, R38).

Three checks, all against what the journal recorded before the writes: the set of secret
values, the byte copies by hash, the transformed copies by their rule. Problems name keys,
paths and sha256[:12], never a value. Secret files are read through core.secrets only.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from h2t_ops.core import google_auth, secrets
from h2t_ops.setup.layout import secrets_phase
from h2t_ops.setup.layout.engine import PhaseFailed


def pairs(env: dict[str, str]) -> set[tuple[str, str]]:
    """An empty value is no value (the skeleton's KEY=): it is not a pair."""
    return {(k, hashlib.sha256(v.encode()).hexdigest()) for k, v in env.items() if v}


def _new_pairs() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for vals in secrets.shared_env_values().values():    # {} when there is no shared dir
        out |= pairs(vals)
    return out


def baseline() -> set[tuple[str, str]]:
    """Taken BEFORE any write: every old source under translated names, plus existing new
    files and their .from- copies."""
    out: set[tuple[str, str]] = set()
    for _, _, vals in secrets.migration_sources():
        out |= pairs(vals)
    for _, vals in secrets_phase.translated_extras():  # notion token, telegram api_id/hash
        out |= pairs(vals)
    return out | _new_pairs()


def verify_secrets(journal) -> list[str]:
    """Both sets come from the journal written before any write — never recomputed from the
    files the migration has just written (plan_env() would see them as "existing" winners and
    compare them with themselves). A new user has no secrets: both sets are empty."""
    rows = journal.entries()
    before = {(r["key"], r["sha256"]) for r in rows if r["op"] == "baseline"}
    after = _new_pairs()
    problems = [f"lost {k} (sha256 {h[:12]})" for k, h in sorted(before - after)]
    problems += [f"appeared {k} (sha256 {h[:12]})" for k, h in sorted(after - before)]
    shared = secrets.shared_env_values()
    for r in (r for r in rows if r["op"] == "winner"):
        if r["target"] not in shared:
            problems.append(f"{r['target']}: missing, {r['key']} expected")
            continue
        got = shared[r["target"]]
        if hashlib.sha256(got.get(r["key"], "").encode()).hexdigest() != r["sha256"]:
            problems.append(f"{r['target']}: {r['key']} is not the senior value")
    return problems


def _sha(path: Path, secret: bool) -> str | None:
    if not path.is_file():
        return None
    data = secrets.read_secret_bytes(path) if secret else path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def verify_copies(journal) -> list[str]:
    """Byte copies (Google client, telegram session and auth-state, evals json and spool,
    cursors, registry, data, foreign env files): the journal row's hash, the target's and the
    source's agree. Secret files are read through core.secrets (R38)."""
    problems = []
    for r in (r for r in journal.entries()
              if r["op"] == "created" and r.get("source_path") and not r.get("rule")):
        secret = r["place"] in ("secrets.shared", "secrets.local")
        for label, p in (("copy", Path(r["path"])), ("source", Path(r["source_path"]))):
            if _sha(p, secret) != r["sha256"]:
                problems.append(f"{label} {p} does not match its journal hash")
    return problems


_DROPPED = ("token", "access_token", "expiry", "expiry_date", "id_token")


def _field_hashes(d: dict) -> dict[str, str]:
    return {k: hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest() for k, v in d.items()}


def _secret_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        doc = json.loads(secrets.read_secret_bytes(path).decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def verify_transformed(journal) -> list[str]:
    """Transformed copies by rule (§8 п. 6, R37): the Google token keeps every durable field
    of its source, by hash, and none of the dropped ones. "activity-filter": the legacy part
    of the target is the filtered source — every kept row in it, no dropped row (the file
    may hold live rows too, merged or appended). "session-body": the body after the
    frontmatter is the source, byte for byte, and migrated_from carries its hash."""
    problems = []
    rows = journal.entries()
    # lazy: phases imports secrets_phase, which imports this module
    from h2t_ops.setup.layout import phases
    for r in (r for r in rows if r["op"] in ("created", "replaced")
              and r.get("rule") in ("activity-filter", "session-body")):
        src, dst = Path(r["source_path"]), Path(r["path"])
        got = dst.read_bytes() if dst.is_file() else None
        raw = src.read_bytes() if src.is_file() else None
        if r["rule"] == "activity-filter":
            if got is None or raw is None or not phases.activity_holds(raw, got):
                problems.append(f"{r['path']}: is not the filtered {r['source_path']}")
        elif got is None or raw is None or not phases.session_body_holds(raw, got, r["source_path"]):
            problems.append(f"{r['path']}: its body is not {r['source_path']}")
    for r in (r for r in rows if r["op"] == "created" and r.get("rule") == "google-durable"):
        raw = _secret_json(Path(r["source_path"]))
        dst = _secret_json(Path(r["path"]))
        if raw is None or dst is None:
            which = r["source_path"] if raw is None else r["path"]
            problems.append(f"{which}: missing or not a JSON object")
            continue
        src = google_auth.durable_token(raw)
        if any(k in dst for k in _DROPPED):
            problems.append(f"{r['path']}: holds a short-lived field")
        if _field_hashes(src) != _field_hashes({k: dst[k] for k in src if k in dst}):
            problems.append(f"{r['path']}: a durable field differs from {r['source_path']}")
    return problems


def phase_verify(ctx) -> None:
    problems = verify_secrets(ctx.journal) + verify_copies(ctx.journal) + verify_transformed(ctx.journal)
    if problems:
        raise PhaseFailed("; ".join(problems[:5]),
                          hint=f"nothing was removed; see {ctx.journal.file}")
