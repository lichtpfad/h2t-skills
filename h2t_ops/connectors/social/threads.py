"""Read-only Threads client. GET only.

Every method returns `(result, raw)`; `raw` holds one decoded body per HTTP call, in call order,
so the caller can journal them. Transport, error mapping and token hygiene live in `_graph`.
"""
from __future__ import annotations

import time

from h2t_ops.connectors.social import journal
from h2t_ops.connectors.social._graph import PAGE_SIZE, UNAVAILABLE_CODES, GraphClient

_POST_METRICS = "views,likes,replies,reposts,quotes"


def _metric_value(metric: dict):
    if "total_value" in metric:
        return (metric["total_value"] or {}).get("value")
    return ((metric.get("values") or [{}])[0]).get("value")


class ThreadsClient(GraphClient):
    _provider = "threads"
    _label = "Threads"

    def _resolve(self) -> str:
        token = self._token()
        self._secrets.add(token)
        journal.register_secret(token)
        return token

    def me(self) -> tuple[dict, list[dict]]:
        return self._single("me", self._resolve(), {"fields": "id,username"})

    def posts(self, limit: int) -> tuple[list[dict], list[dict]]:
        return self._paged("me/threads", self._resolve(), {
            "fields": "id,timestamp,media_type,permalink",
            "limit": min(limit, PAGE_SIZE)}, limit)

    def post_insights(self, post_id: str) -> tuple[dict | None, list[dict]]:
        body, raw = self._single(f"{post_id}/insights", self._resolve(),
                                 {"metric": _POST_METRICS}, soft=UNAVAILABLE_CODES)
        if body.get("error"):
            return None, raw
        return {m["name"]: _metric_value(m) for m in body.get("data") or []}, raw

    def profile_insights(self, days: int = 30) -> tuple[dict, list[dict]]:
        token = self._resolve()
        now = int(time.time())
        window, raw = self._single("me/threads_insights", token, {
            "metric": "views,likes,replies", "since": now - days * 86400, "until": now})
        # followers_count is a lifetime total: the API takes no time window for it
        followers, raw2 = self._single("me/threads_insights", token, {"metric": "followers_count"})
        data = (window.get("data") or []) + (followers.get("data") or [])
        return {m["name"]: _metric_value(m) for m in data}, raw + raw2
