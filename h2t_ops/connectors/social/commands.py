"""social CLI adapter. argparse only at module scope; clients and yaml imported in the handlers.

Every command that touches a network opens a journal run first; every HTTP body goes through
journal.write_raw. This module, insights.py and tokens.py are the modules that construct a client.
"""
from __future__ import annotations

import re
from typing import Any

PROVIDER = "social"


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("social", help="Instagram and Threads insights, Facebook Page check (read-only Graph reads; local schedule and token upkeep)")
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
    ip.add_argument("--trigger", choices=("cli", "schedule"), default="cli")
    ip.add_argument("--store", action="store_true", help="also mirror the run into SQLite")
    add_fmt(ip)

    jp = cmds.add_parser("journal", help="Show journal records")
    jp.add_argument("--run", dest="run_id", default=None)
    jp.add_argument("--last", type=int, default=20)
    add_fmt(jp)

    sp = cmds.add_parser("schedule", help="Register a process in Windows Task Scheduler")
    sps = sp.add_subparsers(dest="schedule_cmd", required=True)
    sa = sps.add_parser("add", help="Run the process daily at HH:MM")
    sa.add_argument("process")
    sa.add_argument("--daily", required=True, metavar="HH:MM")
    add_fmt(sa)
    sr = sps.add_parser("remove", help="Remove the scheduled task")
    sr.add_argument("process")
    add_fmt(sr)

    tp = cmds.add_parser("tokens", help="Threads token upkeep")
    tps = tp.add_subparsers(dest="tokens_cmd", required=True)
    add_fmt(tps.add_parser("refresh", help="Refresh Threads tokens that expire within 7 days"))

    p.set_defaults(_handler=run)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


def _journaled(process: str, work):
    """Open a run, call work(run_id) -> (result, ids); close with a step-6 outcome either way."""
    from h2t_ops.connectors.social import journal

    run_id = journal.new_run(process, "cli")
    try:
        result = work(run_id)
    except BaseException as exc:
        journal.record_failure(run_id, process, exc)
        raise
    journal.record(run_id, 6, process=process, accounts=sorted(
        r["id"] for r in (result if isinstance(result, list) else result["accounts"])))
    return result


def _discovered(run_id: str) -> tuple[list[dict], list[str]]:
    from h2t_ops.connectors.social import journal
    from h2t_ops.connectors.social.config import secret_key
    from h2t_ops.connectors.social.meta import MetaClient
    from h2t_ops.connectors.social.threads import ThreadsClient
    from h2t_ops.core import secrets
    from h2t_ops.core.errors import ConfigError, ProviderError

    meta_key = secret_key("meta_user_token")
    prefix = secret_key("threads_token_prefix")
    rows: list[dict] = []
    notes: list[str] = []
    if secrets.get(meta_key):
        pages = journal.keep(run_id, "accounts", "*", "me/accounts", MetaClient().pages())
        for pg in pages:
            if pg.get("ig_id"):
                rows.append({"network": "instagram", "handle": pg["ig_username"], "remote_id": pg["ig_id"],
                             "page_id": pg["page_id"], "token_key": meta_key})
            rows.append({"network": "facebook", "handle": _slug(pg["name"]), "remote_id": pg["page_id"],
                         "page_id": pg["page_id"], "token_key": meta_key})
    else:
        notes.append(f"{meta_key} is not set: Instagram and Facebook skipped")
    threads_keys = secrets.keys_with_prefix(prefix)
    for key in threads_keys:
        me = journal.keep(run_id, "accounts", key, "me", ThreadsClient(key).me())
        rows.append({"network": "threads", "handle": me["username"], "remote_id": me["id"],
                     "token_key": key})
    if not rows:
        error = ConfigError if not (secrets.get(meta_key) or threads_keys) else ProviderError
        raise error("no accounts found", hint=f"set {meta_key} or {prefix}*")
    handles = [r["handle"] for r in rows if r["network"] == "facebook"]
    for r in rows:
        if r["network"] == "facebook" and handles.count(r["handle"]) > 1:
            r["handle"] += f"_{r['page_id']}"
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


def _discover_table(result: dict) -> str:
    import yaml

    rows = [(f"{a['network']}:{a['handle']}", str(a.get("enabled")), str(a.get("token_key")))
            for a in yaml.safe_load(result["yaml"])["accounts"]]
    rows.insert(0, ("id", "enabled", "token_key"))
    widths = [max(len(r[i]) for r in rows) for i in range(3)]
    lines = ["  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows]
    lines += result["notes"]
    lines.append(f"written: {result['path']}" if result["written"]
                 else f"not written: pass --write to save {result['path']}")
    return "\n".join(lines)


def _list() -> list[dict]:
    from h2t_ops.connectors.social.config import load_accounts

    return [{"id": a.id, "enabled": a.enabled, "project": a.project, "token_key": a.token_key}
            for a in load_accounts()]


def _check(account_id: str | None) -> list[dict]:
    from h2t_ops.connectors.social import journal
    from h2t_ops.connectors.social.config import load_accounts
    from h2t_ops.connectors.social.meta import MetaClient, find_page
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
                row["profile"] = journal.keep(run_id, "check", a.id, "me", client.me())
                row["posts"] = len(journal.keep(run_id, "check", a.id, "posts", client.posts(3)))
            else:
                meta = meta or MetaClient()
                pages = pages if pages is not None else journal.keep(
                    run_id, "check", a.id, "me/accounts", meta.pages())
                page = find_page(pages, a)
                if page is None:
                    raise ProviderError(f"{a.id}: no page matches this account",
                                        hint="run `h2t-ops social accounts discover`")
                if a.network == "facebook":
                    row["profile"] = {"name": page["name"], "page_id": page["page_id"]}
                    row["note"] = "Facebook: profile only; post reading is not built"
                else:
                    row["profile"] = journal.keep(run_id, "check", a.id, "profile",
                                                  meta.ig_profile(a.remote_id, page["page_token"]))
                    row["posts"] = len(journal.keep(run_id, "check", a.id, "media",
                                                    meta.ig_media(a.remote_id, page["page_token"], 3)))
            out.append(row)
        return out

    return _journaled("check", work)


def _journal(run_id: str | None, last: int) -> list[dict]:
    import json

    from h2t_ops.connectors.social.journal import journal_path
    from h2t_ops.core.errors import NotFoundError

    path = journal_path()
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    recs = [json.loads(line) for line in lines if line.strip()]
    if run_id:
        recs = [r for r in recs if r.get("run_id") == run_id]
    if not recs:
        raise NotFoundError(f"no journal records in {path}" + (f" for run {run_id}" if run_id else ""),
                            hint="run `h2t-ops social check` or `run insights` first")
    return recs[-last:] if last > 0 else recs


def run(args: Any) -> Any:
    """Dispatch a social subcommand. Returns result or raises core.errors."""
    from h2t_ops.core.errors import UsageError

    cmd = args.social_cmd
    if cmd == "accounts":
        if args.accounts_cmd != "discover":
            return _list()
        result = _discover(args.write)
        return result if args.as_json or args.fmt != "human" else _discover_table(result)
    if cmd == "check":
        return _check(args.account_id)
    if cmd == "run":
        from h2t_ops.connectors.social import insights

        return insights.run(args.accounts, args.limit, trigger=args.trigger, store=args.store)
    if cmd == "schedule":
        from h2t_ops.connectors.social import schedule

        if args.schedule_cmd == "add":
            return schedule.add(args.process, args.daily)
        return schedule.remove(args.process)
    if cmd == "tokens":
        from h2t_ops.connectors.social import tokens

        return tokens.refresh()
    if cmd == "journal":
        return _journal(args.run_id, args.last)
    raise UsageError(f"unknown social subcommand: {cmd!r}")
