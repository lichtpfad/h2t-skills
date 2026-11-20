"""Read-only Meta Graph client: Instagram and Facebook Page data. GET only.

Every method returns `(result, raw)`; `raw` holds one decoded body per HTTP call, in call order,
so the caller can journal them. Transport, error mapping and token hygiene live in `_graph`.
"""
from __future__ import annotations

from datetime import datetime

from h2t_ops.connectors.social import journal
from h2t_ops.connectors.social._graph import PAGE_SIZE, UNAVAILABLE_CODES, GraphClient
from h2t_ops.connectors.social.config import secret_key


def find_page(pages: list[dict], account):
    """The row of `MetaClient.pages()` behind an account: by its Instagram id or its Page id."""
    return next((p for p in pages if p.get("ig_id") == account.remote_id
                 or (account.page_id and p.get("page_id") == account.page_id)), None)


class MetaClient(GraphClient):
    _provider = "meta"
    _label = "Meta"

    def __init__(self, user_token_key: str | None = None, **kw) -> None:
        super().__init__(user_token_key or secret_key("meta_user_token"), **kw)

    def _user_token(self) -> str:
        return self._token()

    # --- reads ---

    def pages(self) -> tuple[list[dict], list[dict]]:
        user_token = self._user_token()
        self._secrets.add(user_token)
        journal.register_secret(user_token)
        data, raw = self._paged("me/accounts", user_token, {
            "fields": "id,name,access_token,instagram_business_account{id,username}"})
        rows = []
        for p in data:
            ig = p.get("instagram_business_account") or {}
            token = p.get("access_token")
            if token:
                self._secrets.add(token)
                journal.register_secret(token)
            rows.append({"page_id": p.get("id"), "name": p.get("name"), "page_token": token,
                         "ig_id": ig.get("id"), "ig_username": ig.get("username")})
        return rows, raw

    def ig_profile(self, ig_id: str, page_token: str) -> tuple[dict, list[dict]]:
        return self._single(ig_id, page_token, {"fields": "username,followers_count,media_count"})

    def ig_media(self, ig_id: str, page_token: str, limit: int) -> tuple[list[dict], list[dict]]:
        return self._paged(f"{ig_id}/media", page_token, {
            "fields": "id,timestamp,media_product_type,media_type,like_count,comments_count,permalink",
            "limit": min(limit, PAGE_SIZE)}, limit)

    def ig_media_insights(self, media_id: str, page_token: str) -> tuple[dict | None, list[dict]]:
        body, raw = self._single(f"{media_id}/insights", page_token,
                                 {"metric": "reach,views,total_interactions"},
                                 soft=UNAVAILABLE_CODES)
        if body.get("error"):
            return None, raw
        return {m["name"]: (m.get("values") or [{}])[0].get("value")
                for m in body.get("data") or []}, raw

    def ig_online_followers(self, ig_id: str, page_token: str,
                            days: int = 29) -> tuple[dict[int, float], list[dict]]:
        body, raw = self._single(f"{ig_id}/insights", page_token,
                                 {"metric": "online_followers", "period": "lifetime"})
        sums: dict[int, float] = {}
        counts: dict[int, int] = {}
        for metric in body.get("data") or []:
            for day in (metric.get("values") or [])[-days:]:
                for hour, n in (day.get("value") or {}).items():
                    sums[int(hour)] = sums.get(int(hour), 0) + n
                    counts[int(hour)] = counts.get(int(hour), 0) + 1
        return {h: sums[h] / counts[h] for h in sums}, raw

    def page_insights(self, page_id: str, page_token: str, metric: str,
                      since: int, until: int) -> tuple[dict, list[dict]]:
        """One daily Page metric over [since, until] (unix seconds).

        `({"values": [{"date", "value"}, ...]}, raw)`, or `({"error": {"code", "message"}}, raw)`
        when Meta refuses the metric (code 100, 10)."""
        body, raw = self._single(f"{page_id}/insights", page_token,
                                 {"metric": metric, "period": "day", "since": since, "until": until},
                                 soft=UNAVAILABLE_CODES)
        err = body.get("error")
        if err:
            return {"error": {"code": err.get("code"),
                              "message": self._scrub(str(err.get("message", "")))}}, raw
        values = [{"date": datetime.strptime(v["end_time"][:10], "%Y-%m-%d").date().isoformat(),
                   "value": v.get("value")}
                  for m in body.get("data") or [] for v in m.get("values") or []
                  if v.get("end_time")]
        return {"values": values}, raw
