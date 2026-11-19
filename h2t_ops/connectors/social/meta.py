"""Read-only Meta Graph client: Instagram and Facebook Page data. GET only.

Every method returns `(result, raw)`; `raw` holds one decoded body per HTTP call, in call order,
so the caller can journal them. Transport, error mapping and token hygiene live in `_graph`.
"""
from __future__ import annotations

from h2t_ops.connectors.social import journal
from h2t_ops.connectors.social._graph import PAGE_SIZE, UNAVAILABLE_CODES, GraphClient


def find_page(pages: list[dict], account):
    """The row of `MetaClient.pages()` behind an account: by its Instagram id or its Page id."""
    return next((p for p in pages if p.get("ig_id") == account.remote_id
                 or (account.page_id and p.get("page_id") == account.page_id)), None)


class MetaClient(GraphClient):
    _provider = "meta"
    _label = "Meta"

    def __init__(self, user_token_key: str = "META_USER_TOKEN", **kw) -> None:
        super().__init__(user_token_key, **kw)

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
