"""Read-only Meta Graph client: Instagram and Facebook Page data. GET only.

Every method returns `(result, raw)`; `raw` holds one decoded body per HTTP call, in call order,
so the caller can journal them. A token value never appears in an exception, repr or str:
errors name the key, and anything taken from a transport error is scrubbed.

requests is imported lazily so registry/help paths stay lightweight.
"""
from __future__ import annotations

import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from h2t_ops.connectors.social import journal
from h2t_ops.connectors.social.config import api_base
from h2t_ops.core import secrets
from h2t_ops.core.errors import AuthError, NetworkError, ProviderError

_RATE_CODES = {4, 17, 32, 613}
_UNAVAILABLE_CODES = {100, 10}
_PAGE_SIZE = 100
_SECRET_PARAMS = ("access_token", "appsecret_proof", "client_secret", "token")


def _clean(node):
    """A copy of a decoded body with token query params removed from every URL string in it."""
    if isinstance(node, dict):
        return {k: _clean(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_clean(v) for v in node]
    if isinstance(node, str) and node.startswith(("http://", "https://")) and "?" in node:
        parts = urlsplit(node)
        keep = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                if k not in _SECRET_PARAMS]
        return urlunsplit(parts._replace(query=urlencode(keep)))
    return node


class MetaClient:
    def __init__(self, user_token_key: str = "META_USER_TOKEN", *, session=None,
                 sleep=time.sleep, retry_after: float = 60.0, timeout: float = 30.0) -> None:
        self._key = user_token_key
        self._session = session
        self._sleep = sleep
        self._retry_after = retry_after
        self._timeout = timeout
        self._secrets: set[str] = set()

    def __repr__(self) -> str:
        return f"MetaClient(user_token_key={self._key!r})"

    # --- auth ---

    def _user_token(self) -> str:
        token = secrets.get(self._key)
        if not token:
            raise AuthError(f"{self._key} is not set",
                            hint=f"add {self._key} to {secrets.provider_file('meta')}")
        return token

    def _scrub(self, text: str) -> str:
        for value in self._secrets:
            text = text.replace(value, "***")
        return text

    # --- transport ---

    def _http(self):
        if self._session is None:
            import requests  # lazy — module-scope import forbidden
            self._session = requests.Session()
        return self._session

    def _get_once(self, url: str, params: dict | None):
        import requests
        try:
            resp = self._http().get(url, params=params, timeout=self._timeout)
        except requests.RequestException as exc:
            # the message of a requests error embeds the URL, and the URL carries the token
            raise NetworkError(f"Meta Graph request failed ({type(exc).__name__})") from None
        try:
            body = resp.json()
        except ValueError:
            body = None
        return resp.status_code, body

    def _call(self, url: str, params: dict | None, raw: list[dict], token: str, soft=()) -> dict:
        """One GET with a single retry on a rate limit. Appends every body to `raw`."""
        self._secrets.add(token)
        for attempt in (0, 1):
            status, body = self._get_once(url, params)
            if isinstance(body, dict):
                raw.append(_clean(body))
            err = body.get("error") if isinstance(body, dict) else None
            code = err.get("code") if isinstance(err, dict) else None
            if status < 400 and not err:
                return body if isinstance(body, dict) else {}
            if code in soft:
                return body
            if code == 190:
                raise AuthError(f"Meta rejected {self._key} (code 190): token expired or invalid",
                                hint=f"renew the token and set {self._key}")
            if status == 429 or code in _RATE_CODES:
                if attempt == 0:
                    self._sleep(self._retry_after)
                    continue
                raise ProviderError("rate limited, retry later")
            msg = self._scrub(str(err.get("message", ""))) if isinstance(err, dict) else ""
            raise ProviderError(f"Meta Graph error (HTTP {status}, code {code}): {msg}".rstrip(": "))
        raise AssertionError("unreachable")

    def _paged(self, path: str, token: str, params: dict, limit: int | None = None):
        """Follow paging.next until the pages end or `limit` rows are collected."""
        raw: list[dict] = []
        rows: list[dict] = []
        url, query = f"{api_base('meta')}/{path}", {**params, "access_token": token}
        while url:
            body = self._call(url, query, raw, token)
            rows += body.get("data") or []
            if limit is not None and len(rows) >= limit:
                return rows[:limit], raw
            url, query = (body.get("paging") or {}).get("next"), None
        return rows, raw

    def _single(self, path: str, token: str, params: dict, soft=()):
        raw: list[dict] = []
        body = self._call(f"{api_base('meta')}/{path}", {**params, "access_token": token}, raw,
                          token, soft)
        return body, raw

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
            "limit": min(limit, _PAGE_SIZE)}, limit)

    def ig_media_insights(self, media_id: str, page_token: str) -> tuple[dict | None, list[dict]]:
        body, raw = self._single(f"{media_id}/insights", page_token,
                                 {"metric": "reach,views,total_interactions"},
                                 soft=_UNAVAILABLE_CODES)
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
