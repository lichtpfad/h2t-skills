"""The door core: the journal (provenance), the raw zone and the rule check (governance).

Append-only JSONL, written only through store.append. No token value is ever written.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from h2t_ops.connectors.social.config import load_accounts, load_rules, secret_key
from h2t_ops.core import paths, secrets, store
from h2t_ops.core.errors import ConfigError, UsageError

REDACT_FIELDS = ("access_token", "page_token", "token")
_FIXED_SECRETS = ("meta_user_token", "meta_app_secret")   # names in config; key names resolve there
_runtime_secrets: set[str] = set()
_stored_runs: set[str] = set()   # runs opened with store=True: their records are also mirrored to SQLite


class SecretInRecord(ConfigError):
    """A line about to be written contains a secret value. The value is never in the message."""


def journal_path() -> Path:
    return paths.data_dir() / "social" / "journal.jsonl"


def raw_path(process: str, day: str) -> Path:
    return paths.data_dir() / "social" / "raw" / process / f"{day}.jsonl"


def register_secret(value: str) -> None:
    if value:
        _runtime_secrets.add(value)


def _now() -> datetime:
    return datetime.now(UTC)


def _redact(node):
    if isinstance(node, dict):
        return {k: _redact(v) for k, v in node.items() if k not in REDACT_FIELDS}
    if isinstance(node, list):
        return [_redact(v) for v in node]
    return node


def _secret_values() -> list[tuple[str, str]]:
    # journaling must not depend on a valid accounts.yaml: each part falls back on its own
    try:
        keys = [secret_key(n) for n in _FIXED_SECRETS]
    except ConfigError:
        keys = [secret_key(n, overrides=False) for n in _FIXED_SECRETS]
    try:
        keys += [a.token_key for a in load_accounts()]
    except ConfigError:
        pass
    out = [(k, v) for k in keys if (v := secrets.get(k))]
    return out + [("a registered runtime secret", v) for v in _runtime_secrets]


def check_no_secret(text: str, what: str) -> None:
    """Raise SecretInRecord if `text` (serialized JSON) holds a secret value. Names the secret, never the value."""
    for name, value in _secret_values():
        if value in text or json.dumps(value, ensure_ascii=False)[1:-1] in text:   # raw and JSON-escaped
            raise SecretInRecord(f"{what} contains the value of {name}; not written",
                                 hint="remove the value from the record")


def _append(path: Path, rec: dict) -> None:
    line = json.dumps(rec, ensure_ascii=False)
    check_no_secret(line, f"record {rec.get('id')}")
    store.append(path, line, place="data")


def record(run_id: str, step: int, **fields) -> dict:
    if step == 5 and not fields.get("source_ids"):
        raise ValueError("a step-5 record must name at least one source id")
    rec = {"id": uuid.uuid4().hex, "ts": _now().isoformat(), "run_id": run_id, "process": None,
           "step": step, "channel": None, "account": None, "action": None, "source_ids": [],
           "context_refs": [], "rule_id": None, "decision": None, "approved_by": None,
           "task_id": None, **fields}
    rec["result"] = {"remote_id": None, "url": None, "error": None, **(fields.get("result") or {})}
    _append(journal_path(), rec)
    if run_id in _stored_runs:
        from h2t_ops.connectors.social import db

        db.put_journal(rec)
    return rec


def new_run(process: str, trigger: str, store: bool = False) -> str:
    run_id = uuid.uuid4().hex
    if store:
        _stored_runs.add(run_id)
    record(run_id, 1, process=process, trigger=trigger)
    return run_id


def write_raw(run_id: str, process: str, account_id: str, endpoint: str, payload: dict) -> str:
    now = _now()
    rid = uuid.uuid4().hex
    raw = {"id": rid, "ts": now.isoformat(), "run_id": run_id, "process": process,
           "account": account_id, "endpoint": endpoint, "payload": _redact(payload)}
    _append(raw_path(process, now.strftime("%Y-%m-%d")), raw)
    if run_id in _stored_runs:
        from h2t_ops.connectors.social import db

        db.put_raw(raw)
    record(run_id, 2, process=process, account=account_id, endpoint=endpoint, source_ids=[rid])
    return rid


def keep(run_id: str, process: str, account_id: str, endpoint: str, value_raw, ids: list | None = None):
    """Journal every raw body of a client call `(value, raw)`; return the value. Ids go into `ids`."""
    value, raw = value_raw
    for body in raw:
        rid = write_raw(run_id, process, account_id, endpoint, body)
        if ids is not None:
            ids.append(rid)
    return value


def record_failure(run_id: str, process: str, exc: BaseException, account_id: str | None = None) -> None:
    """Journal the bodies an error carried, then the step-6 failure outcome."""
    keep(run_id, process, account_id, "error", (None, getattr(exc, "raw", [])))
    record(run_id, 6, process=process, account=account_id,
           result={"error": f"{type(exc).__name__}: {exc}"})


def decide(run_id: str, process: str, action: str, account_id: str, kind: str = "*") -> str:
    if action == "none":
        record(run_id, 4, process=process, action=action, account=account_id, rule_id=None,
               decision="noop")
        return "noop"
    best, best_rank = None, None
    for r in load_rules():
        if r.process not in (process, "*") or r.action != action:
            continue
        if r.account not in (account_id, "*") or r.kind not in (kind, "*"):
            continue
        rank = (r.account == account_id, r.kind == kind)
        if best_rank is None or rank > best_rank:
            best, best_rank = r, rank
    verdict = best.verdict if best else "ask"
    record(run_id, 4, process=process, action=action, account=account_id,
           rule_id=best.id if best else None, decision=verdict)
    return verdict


def require_allowed(record: dict) -> None:
    if record.get("step") != 4:
        raise UsageError("not a decision record: an action needs a step-4 record")
    decision = record.get("decision")
    if decision == "auto" or (decision == "ask" and record.get("approved_by")):
        return
    raise UsageError(f"action not allowed: decision is {decision!r}",
                     hint="`ask` needs approval; `deny` is final")
