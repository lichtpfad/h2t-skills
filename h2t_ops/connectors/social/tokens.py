"""Threads long-lived token refresh.

Expiry dates live in a state file, never in a secrets file: a `THREADS_TOKEN_*_EXPIRES` key
would be read as an account. The file holds key names and ISO dates only.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from h2t_ops.connectors.social import journal
from h2t_ops.connectors.social.config import secret_key
from h2t_ops.core import paths, secrets, store
from h2t_ops.core.errors import ConfigError, NotFoundError

THRESHOLD_DAYS = 7
PROCESS = "tokens"


def expiry_path() -> Path:
    return paths.state_dir() / "social" / "token-expiry.json"


def _read_expiry() -> dict[str, str | None]:
    path = expiry_path()
    if not path.exists():
        return {}
    bad = ConfigError(f"{path} is not a valid expiry file (key names and timezone-aware ISO dates)",
                      hint="fix or delete the file; the next refresh records fresh expiry dates")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise bad
        for value in data.values():
            if value is not None and datetime.fromisoformat(value).tzinfo is None:
                raise bad
    except (ValueError, TypeError) as exc:    # JSONDecodeError and a bad date are ValueError
        raise bad from exc
    return data


def refresh(now: datetime | None = None, client_factory=None) -> dict:
    """Refresh every Threads token that expires within THRESHOLD_DAYS or has no recorded expiry."""
    from h2t_ops.connectors.social.threads import ThreadsClient

    now = now or datetime.now(UTC)
    factory = client_factory or ThreadsClient
    keys = secrets.keys_with_prefix(secret_key("threads_token_prefix"))
    if not keys:
        raise NotFoundError("no Threads tokens found",
                            hint=f"set {secret_key('threads_token_prefix')}<NAME> in the threads secrets file")
    expiry = _read_expiry()
    due = [k for k in keys
           if not (expiry.get(k) and datetime.fromisoformat(expiry[k]) - now > timedelta(days=THRESHOLD_DAYS))]
    pinned = [k for k in due if secrets.source(k) == "env"]
    if pinned:
        # the environment overrides the shared file, so a refreshed value written there would never be read
        raise ConfigError(
            f"Threads token key(s) set in the process environment: {', '.join(pinned)}",
            hint="remove it from the environment; the refreshed value is written to the shared "
                 "secrets threads.env")
    run_id = journal.new_run(PROCESS, "cli")
    out: dict = {"refreshed": [], "skipped": []}
    try:
        values = dict(secrets.shared_env_values().get("threads.env", {}))
        for key in keys:
            known = expiry.get(key)
            if known and datetime.fromisoformat(known) - now > timedelta(days=THRESHOLD_DAYS):
                out["skipped"].append({"key": key, "expires_at": known})
                journal.record(run_id, 6, process=PROCESS, key=key, expires_at=known, action="skipped")
                continue
            result = journal.keep(run_id, PROCESS, key, "refresh_access_token", factory(key).refresh())
            values[key] = result["access_token"]
            # persist the token first: a later failure must not lose a token the API has already rotated
            secrets.write_env("threads", values)
            try:
                expires_at = (now + timedelta(seconds=int(result["expires_in"]))).isoformat()
                note = None
            except (KeyError, TypeError, ValueError):
                expires_at, note = None, "expiry unknown: the API gave no usable expires_in; refreshed again next run"
            expiry[key] = expires_at
            store.replace(expiry_path(), json.dumps(expiry, indent=2), place="state")
            entry = {"key": key, "expires_at": expires_at, **({"note": note} if note else {})}
            out["refreshed"].append(entry)
            journal.record(run_id, 6, process=PROCESS, key=key, expires_at=expires_at, action="refreshed")
    except BaseException as exc:
        journal.record_failure(run_id, PROCESS, exc)
        raise
    return out
