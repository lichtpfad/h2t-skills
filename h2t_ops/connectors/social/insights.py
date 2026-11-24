"""Insights process: collect metrics per account through the journal, summarize, record a noop decision."""
from __future__ import annotations

import statistics
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from h2t_ops.connectors.social import journal
from h2t_ops.connectors.social.config import (
    Account,
    facebook_page_metrics,
    load_accounts,
)
from h2t_ops.connectors.social.meta import find_page
from h2t_ops.core import user_config
from h2t_ops.core.errors import ConfigError, NotFoundError, ProviderError, UsageError

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_BANDS = ((0, 10), (10, 13), (13, 16), (16, 19), (19, 22), (22, 24))
_PROCESS = "insights"
_PAGE_DAYS = 28
_ONLINE_DAYS = 29   # Meta keeps online_followers for the last 30 days; stay inside that
SCHEMA_VERSION = "h2t_social_insights/v1"


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
    after = None    # a call made once the per-post fetches are done, so journal order is unchanged
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
        until = int(datetime.now(UTC).timestamp())
        after = lambda: extra.update(online_followers_by_end_time=keep(  # noqa: E731
            "online_followers", client.ig_online_followers(
                account.remote_id, token, until - _ONLINE_DAYS * 86400, until)))
    for m in media:
        for field in ("id", "timestamp"):
            if not m.get(field):
                raise ProviderError(f"{account.id}: post {m.get('id', '?')} has no {field}")
    posts = [{"id": m["id"], "timestamp": m["timestamp"], "permalink": m.get("permalink"),
              "network": account.network, "metrics": fetch(m)} for m in media]
    if after:
        after()
    return posts, extra, ids


def _collect_page(run_id: str, account: Account, client) -> tuple[dict, list[dict], list[str]]:
    """(metric -> daily values, unavailable entries, raw ids) of a Facebook Page, last 28 days."""
    ids: list[str] = []
    pages = journal.keep(run_id, _PROCESS, account.id, "me/accounts", client.pages(), ids)
    page = next((p for p in pages if p.get("page_id") == (account.page_id or account.remote_id)), None)
    if page is None:
        raise ProviderError(f"{account.id}: no page matches this account",
                            hint="run `h2t-ops social accounts discover`")
    until = int(datetime.now(UTC).timestamp())
    since = until - _PAGE_DAYS * 86400
    values: dict[str, list] = {}
    unavailable: list[dict] = []
    for metric in facebook_page_metrics():
        body = journal.keep(run_id, _PROCESS, account.id, f"page_insights/{metric}", client.page_insights(
            page["page_id"], page["page_token"], metric, since, until), ids)
        if body.get("error"):
            unavailable.append({"account": account.id, "group": "page", "metric": metric,
                                "code": body["error"].get("code"), "message": body["error"].get("message")})
        elif body.get("values"):
            values[metric] = body["values"]
    return values, unavailable, ids


def run(account_ids: list[str] | None, limit: int, client_factory=None, trigger: str = "cli", store: bool = False) -> dict:
    if limit < 1:
        raise UsageError(f"--limit must be a positive number, got {limit}")
    tz = _timezone()
    factory = client_factory or _default_factory
    enabled = [a for a in load_accounts() if a.enabled]
    if not enabled:
        raise NotFoundError("no enabled accounts", hint="run `h2t-ops social accounts list`")
    unknown = [i for i in account_ids or [] if i not in {a.id for a in enabled}]
    if unknown:
        raise NotFoundError(f"no enabled account: {', '.join(unknown)}",
                            hint="run `h2t-ops social accounts list`")
    chosen = [a for a in enabled if not account_ids or a.id in account_ids]
    run_id = journal.new_run(_PROCESS, trigger, store=store)
    accounts: dict[str, dict] = {}
    skipped_accounts: dict[str, str] = {}
    unavailable: list[dict] = []
    current = None
    try:
        for account in chosen:
            current = account.id
            if account.network == "facebook":
                page, missing, ids = _collect_page(run_id, account, factory(account.network, account))
                unavailable += missing
                no_data = not page
                journal.record(run_id, 3, process=_PROCESS, account=account.id, source_ids=ids,
                               **({"finding": "no data"} if no_data else {}))
                journal.decide(run_id, _PROCESS, "none", account.id)
                if no_data:
                    codes = ", ".join(sorted({str(u["code"]) for u in missing})) or "none"
                    raise NotFoundError(f"no data for {account.id}: no Page metric returned values "
                                        f"(unavailable codes: {codes})",
                                        hint="check the Page token has read_insights access")
                accounts[account.id] = {"network": "facebook", "page": page}
                journal.record(run_id, 6, process=_PROCESS, account=account.id,
                               schema_version=SCHEMA_VERSION, metrics=len(page))
                continue
            posts, extra, ids = _collect(run_id, account, limit, factory(account.network, account))
            summary = summarize(posts, tz)
            no_data = not summary["posts"]
            journal.record(run_id, 3, process=_PROCESS, account=account.id, source_ids=ids,
                           **({"finding": "no data"} if no_data else {}))
            journal.decide(run_id, _PROCESS, "none", account.id)
            if no_data:
                raise NotFoundError(f"no data for {account.id}: no posts with metrics",
                                    hint="check the account has posts and the token has insights access")
            accounts[account.id] = {"network": account.network, "summary": summary, "posts": posts, **extra}
            journal.record(run_id, 6, process=_PROCESS, account=account.id,
                           schema_version=SCHEMA_VERSION, posts=summary["posts"])
        for account_id, body in accounts.items():   # only after the whole run succeeded; no-op unless stored
            journal.mirror_result(run_id, account_id, body)
        if not accounts:
            reasons = "; ".join(f"{k}: {v}" for k, v in skipped_accounts.items())
            raise NotFoundError(f"no account produced insights ({reasons})",
                                hint="run `h2t-ops social accounts list`")
    except BaseException as exc:
        journal.record_failure(run_id, _PROCESS, exc, current)
        raise
    return {"schema_version": SCHEMA_VERSION, "run_id": run_id, "accounts": accounts,
            "skipped_accounts": skipped_accounts, "unavailable": unavailable}
