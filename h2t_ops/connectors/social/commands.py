"""social CLI adapter. argparse only at module scope; clients and yaml imported in the handlers.

Every command that touches a network opens a journal run first; every HTTP body goes through
journal.write_raw. This and insights.py are the only modules that construct a client.
"""
from __future__ import annotations

import re
from typing import Any

PROVIDER = "social"
_META_KEY = "META_USER_TOKEN"


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("social", help="Instagram, Facebook and Threads analytics (read-only)")
    cmds = p.add_subparsers(dest="social_cmd", required=True)

    def add_fmt(sp):
        sp.add_argument("--json", dest="as_json", action="store_true",
                        help="raw machine-readable envelope")
        sp.add_argument("--format", dest="fmt", choices=["md", "human"], default="human")

    ac = cmds.add_parser("accounts", help="Discover or list the accounts in accounts.yaml")
    acs = ac.add_subparsers(dest="accounts_cmd", required=True)
    dp = acs.add_parser("discover", help="Find accounts from the Meta and Threads tokens")
    dp.add_argument("--write", action="store_true",
                    help="merge into accounts.yaml (existing enabled/project are kept)")
    add_fmt(dp)
    add_fmt(acs.add_parser("list", help="Show accounts.yaml"))

    cp = cmds.add_parser("check", help="Smoke test: profile and last 3 posts per enabled account")
    cp.add_argument("account_id", nargs="?", default=None)
    add_fmt(cp)

    rp = cmds.add_parser("run", help="Run a process")
    rps = rp.add_subparsers(dest="run_cmd", required=True)
    ip = rps.add_parser("insights", help="Collect metrics, summarize, journal the run")
    ip.add_argument("--account", action="append", dest="accounts", default=None, metavar="ID")
    ip.add_argument("--limit", type=int, default=120)
    add_fmt(ip)

    jp = cmds.add_parser("journal", help="Show journal records")
    jp.add_argument("--run", dest="run_id", default=None)
    jp.add_argument("--last", type=int, default=20)
    add_fmt(jp)

    p.set_defaults(_handler=run)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower())


def _record_raw(run_id: str, process: str, account: str, endpoint: str, value_raw):
    from h2t_ops.connectors.social import journal

    value, raw = value_raw
    for body in raw:
        journal.write_raw(run_id, process, account, endpoint, body)
    return value


def _journaled(process: str, work):
    """Open a run, call work(run_id) -> (result, ids); close with a step-6 outcome either way."""
    from h2t_ops.connectors.social import journal

    run_id = journal.new_run(process, "cli")
    try:
        result = work(run_id)
    except BaseException as exc:
        journal.record(run_id, 6, process=process, result={"error": f"{type(exc).__name__}: {exc}"})
        raise
    journal.record(run_id, 6, process=process, accounts=sorted(
        r["id"] for r in (result if isinstance(result, list) else result["accounts"])))
    return result


def _discovered(run_id: str) -> tuple[list[dict], list[str]]:
    from h2t_ops.connectors.social.meta import MetaClient
    from h2t_ops.connectors.social.threads import ThreadsClient
    from h2t_ops.core import secrets
    from h2t_ops.core.errors import ProviderError

    rows: list[dict] = []
    notes: list[str] = []
    if secrets.get(_META_KEY):
        pages = _record_raw(run_id, "accounts", "*", "me/accounts", MetaClient().pages())
        for pg in pages:
            if pg.get("ig_id"):
                rows.append({"network": "instagram", "handle": pg["ig_username"], "remote_id": pg["ig_id"],
                             "page_id": pg["page_id"], "token_key": _META_KEY})
            rows.append({"network": "facebook", "handle": _slug(pg["name"]), "remote_id": pg["page_id"],
                         "page_id": pg["page_id"], "token_key": _META_KEY})
    else:
        notes.append(f"{_META_KEY} is not set: Instagram and Facebook skipped")
    for key in secrets.keys_with_prefix("THREADS_TOKEN_"):
        me = _record_raw(run_id, "accounts", key, "me", ThreadsClient(key).me())
        rows.append({"network": "threads", "handle": me["username"], "remote_id": me["id"],
                     "token_key": key})
    if not rows:
        raise ProviderError("no accounts found", hint="set META_USER_TOKEN or THREADS_TOKEN_*")
    for r in rows:
        r["id"] = f"{r['network']}:{r['handle']}"
    return rows, notes


_KEPT = ("network", "handle", "remote_id", "page_id", "token_key", "enabled", "project")


def _existing(path) -> dict:
    """The current file as a plain doc, validated first (token scan, field checks) by config."""
    import yaml

    from h2t_ops.connectors.social.config import load_accounts

    if not path.exists():
        return {}
    load_accounts()   # raises ConfigError on a token or an invalid entry
    doc = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    out = {"accounts": [{k: e[k] for k in _KEPT if k in e} for e in doc.get("accounts") or []]}
    if "api" in doc:
        out = {"api": doc["api"], **out}
    return out


def _merge(existing: dict, rows: list[dict]) -> dict:
    """Existing entries keep enabled/project; new ones are disabled. Unseen entries stay."""
    by_id = {f"{e['network']}:{e['handle']}": e for e in existing.get("accounts") or []}
    for r in rows:
        entry = {k: v for k, v in r.items() if k != "id" and v is not None}
        old = by_id.get(r["id"])
        entry["enabled"] = old.get("enabled", True) if old else False
        if old and "project" in old:
            entry["project"] = old["project"]
        by_id[r["id"]] = entry
    return {**existing, "accounts": list(by_id.values())}


def _discover(write: bool) -> dict:
    import yaml

    from h2t_ops.connectors.social.config import accounts_path
    from h2t_ops.core import store

    path = accounts_path()
    existing = _existing(path)   # refused before a run opens or a request is sent
    found = _journaled("accounts", lambda run_id: dict(zip(("accounts", "notes"), _discovered(run_id))))
    text = yaml.safe_dump(_merge(existing, found["accounts"]), sort_keys=False, allow_unicode=True)
    if write:
        store.replace(path, text, place="config")
    return {"written": write, "path": str(path), "yaml": text, "notes": found["notes"]}


def _list() -> list[dict]:
    from h2t_ops.connectors.social.config import load_accounts

    return [{"id": a.id, "enabled": a.enabled, "project": a.project, "token_key": a.token_key}
            for a in load_accounts()]


def _check(account_id: str | None) -> list[dict]:
    from h2t_ops.connectors.social.config import load_accounts
    from h2t_ops.connectors.social.meta import MetaClient
    from h2t_ops.connectors.social.threads import ThreadsClient
    from h2t_ops.core.errors import NotFoundError, ProviderError

    chosen = [a for a in load_accounts() if a.enabled and (account_id is None or a.id == account_id)]
    if not chosen:
        raise NotFoundError(f"no enabled account {account_id}" if account_id else "no enabled accounts",
                            hint="`h2t-ops social accounts list`")

    def work(run_id: str) -> list[dict]:
        meta, pages, out = None, None, []
        for a in chosen:
            row = {"id": a.id}
            if a.network == "threads":
                client = ThreadsClient(a.token_key)
                row["profile"] = _record_raw(run_id, "check", a.id, "me", client.me())
                row["posts"] = len(_record_raw(run_id, "check", a.id, "posts", client.posts(3)))
            else:
                meta = meta or MetaClient()
                pages = pages if pages is not None else _record_raw(
                    run_id, "check", a.id, "me/accounts", meta.pages())
                page = next((p for p in pages if p["page_id"] == a.page_id or p["ig_id"] == a.remote_id), None)
                if page is None:
                    raise ProviderError(f"{a.id}: no page matches this account",
                                        hint="run `h2t-ops social accounts discover`")
                if a.network == "facebook":
                    row["profile"] = {"name": page["name"], "page_id": page["page_id"]}
                    row["note"] = "Facebook: profile only; post reading is not built"
                else:
                    row["profile"] = _record_raw(run_id, "check", a.id, "profile",
                                                 meta.ig_profile(a.remote_id, page["page_token"]))
                    row["posts"] = len(_record_raw(run_id, "check", a.id, "media",
                                                   meta.ig_media(a.remote_id, page["page_token"], 3)))
            out.append(row)
        return out

    return _journaled("check", work)


def _journal(run_id: str | None, last: int) -> list[dict]:
    import json

    from h2t_ops.connectors.social.journal import journal_path
    from h2t_ops.core.errors import ProviderError

    path = journal_path()
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    recs = [json.loads(line) for line in lines if line.strip()]
    if run_id:
        recs = [r for r in recs if r.get("run_id") == run_id]
    if not recs:
        raise ProviderError(f"no journal records in {path}" + (f" for run {run_id}" if run_id else ""),
                            hint="run `h2t-ops social check` or `run insights` first")
    return recs[-last:] if last > 0 else recs


def run(args: Any) -> Any:
    """Dispatch a social subcommand. Returns result or raises core.errors."""
    from h2t_ops.core.errors import UsageError

    cmd = args.social_cmd
    if cmd == "accounts":
        return _discover(args.write) if args.accounts_cmd == "discover" else _list()
    if cmd == "check":
        return _check(args.account_id)
    if cmd == "run":
        from h2t_ops.connectors.social import insights

        return insights.run(args.accounts, args.limit)
    if cmd == "journal":
        return _journal(args.run_id, args.last)
    raise UsageError(f"unknown social subcommand: {cmd!r}")
