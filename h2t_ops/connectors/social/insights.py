"""Insights process: collect metrics per account through the journal, summarize, record a noop decision."""
from __future__ import annotations

import json
import statistics
from datetime import datetime
from zoneinfo import ZoneInfo

from h2t_ops.connectors.social import journal
from h2t_ops.connectors.social.config import Account, load_accounts
from h2t_ops.core import paths, store, user_config
from h2t_ops.connectors.social.meta import find_page
from h2t_ops.core.errors import ConfigError, ProviderError, UsageError

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_BANDS = ((0, 10), (10, 13), (13, 16), (16, 19), (19, 22), (22, 24))
_PROCESS = "insights"


def _metric(post: dict):
    return (post.get("metrics") or {}).get("views" if post.get("network") == "threads" else "reach")


def _group(keys, values: dict[str, list], overall: float) -> dict:
    return {k: {"n": len(values[k]), "median": statistics.median(values[k]),
                "ratio": round(statistics.median(values[k]) / overall, 2) if overall else None}
            if k in values else {"n": 0, "median": None, "ratio": None}
            for k in keys}


def summarize(posts: list[dict], tz: str) -> dict:
    zone = ZoneInfo(tz)
    used, skipped = [], 0
    for p in posts:
        value = _metric(p)
        if value is None:
            skipped += 1
            continue
        used.append((datetime.fromisoformat(p["timestamp"]).astimezone(zone), value, p))
    overall = statistics.median(v for _, v, _ in used) if used else None
    days: dict[str, list] = {}
    bands: dict[str, list] = {}
    for when, value, _ in used:
        days.setdefault(_WEEKDAYS[when.weekday()], []).append(value)
        lo, hi = next(b for b in _BANDS if b[0] <= when.hour < b[1])
        bands.setdefault(f"{lo:02d}-{hi:02d}", []).append(value)
    top = sorted(used, key=lambda t: t[1], reverse=True)[:5]
    return {"posts": len(used), "skipped": skipped, "median_reach": overall,
            "by_weekday": _group(_WEEKDAYS, days, overall),
            "by_hour_band": _group([f"{lo:02d}-{hi:02d}" for lo, hi in _BANDS], bands, overall),
            "top": [{"reach": v, "permalink": p.get("permalink")} for _, v, p in top]}


def _default_factory(network: str, account: Account):
    if network == "threads":
        from h2t_ops.connectors.social.threads import ThreadsClient
        return ThreadsClient(account.token_key)
    from h2t_ops.connectors.social.meta import MetaClient
    return MetaClient()


def _timezone() -> str:
    tz = user_config.get("timezone")
    if not tz:
        raise ConfigError("no timezone configured", hint="set timezone in user.yaml")
    return str(tz)


def _collect(run_id: str, account: Account, limit: int, client) -> tuple[list[dict], dict, list[str]]:
    """(posts for summarize, extra report keys, raw ids). Every body is journaled."""
    ids: list[str] = []

    def keep(endpoint: str, value_raw):
        return journal.keep(run_id, _PROCESS, account.id, endpoint, value_raw, ids)

    extra: dict = {}
    if account.network == "threads":
        media = keep("posts", client.posts(limit))
        fetch = lambda m: keep("post_insights", client.post_insights(m["id"]))  # noqa: E731
    else:
        pages = keep("me/accounts", client.pages())
        page = find_page(pages, account)
        if page is None:
            raise ProviderError(f"{account.id}: no page matches this account",
                                hint="run `h2t-ops social accounts discover`")
        token = page["page_token"]
        media = keep("media", client.ig_media(account.remote_id, token, limit))
        fetch = lambda m: keep("media_insights", client.ig_media_insights(m["id"], token))  # noqa: E731
    posts = [{"id": m["id"], "timestamp": m["timestamp"], "permalink": m.get("permalink"),
              "network": account.network, "metrics": fetch(m)} for m in media]
    if account.network != "threads":
        extra["online_followers_hour_as_reported"] = keep(
            "online_followers", client.ig_online_followers(account.remote_id, token))
    return posts, extra, ids


def run(account_ids: list[str] | None, limit: int, client_factory=None, trigger: str = "cli") -> dict:
    if limit < 1:
        raise UsageError(f"--limit must be a positive number, got {limit}")
    tz = _timezone()
    factory = client_factory or _default_factory
    chosen = [a for a in load_accounts() if a.enabled and (not account_ids or a.id in account_ids)]
    run_id = journal.new_run(_PROCESS, trigger)
    reports: dict[str, dict] = {}
    skipped_accounts: dict[str, str] = {}
    today = datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d")
    current = None
    try:
        for account in chosen:
            current = account.id
            if account.network == "facebook":
                skipped_accounts[account.id] = "Facebook Page insights are not supported yet"
                continue
            posts, extra, ids = _collect(run_id, account, limit, factory(account.network, account))
            summary = summarize(posts, tz)
            no_data = not summary["posts"]
            journal.record(run_id, 3, process=_PROCESS, account=account.id, source_ids=ids,
                           **({"finding": "no data"} if no_data else {}))
            journal.decide(run_id, _PROCESS, "none", account.id)
            if no_data:
                raise ProviderError(f"no data for {account.id}: no posts with metrics",
                                    hint="check the account has posts and the token has insights access")
            report = {**summary, **extra}
            target = (paths.data_dir() / "social" / "insights" / account.id.replace(":", "_")
                      / f"{today}.json")
            store.replace(target, json.dumps(report, ensure_ascii=False, indent=2), place="data")
            journal.record(run_id, 6, process=_PROCESS, account=account.id, report=str(target))
            reports[account.id] = report
    except BaseException as exc:
        journal.record_failure(run_id, _PROCESS, exc, current)
        raise
    return {"run_id": run_id, "reports": reports, "skipped_accounts": skipped_accounts}
