"""Shared read-only Graph transport of the Meta and Threads clients. GET only.

A subclass sets `_provider` (secrets file and `api_base` key) and `_label` (used in messages).
`raw` holds one decoded body per HTTP call, in call order. A token value never appears in an
exception, repr or str: errors name the key, and anything taken from a transport error is scrubbed.

requests is imported lazily so registry/help paths stay lightweight.
"""
from __future__ import annotations

import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from h2t_ops.connectors.social.config import api_base
from h2t_ops.core import secrets
from h2t_ops.core.errors import AuthError, NetworkError, ProviderError

_RATE_CODES = {4, 17, 32, 613}
UNAVAILABLE_CODES = {100, 10}
PAGE_SIZE = 100
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


class GraphClient:
    _provider = ""
    _label = ""

    def __init__(self, token_key: str, *, session=None, sleep=time.sleep,
                 retry_after: float = 60.0, timeout: float = 30.0) -> None:
        self._key = token_key
        self._session = session
        self._sleep = sleep
        self._retry_after = retry_after
        self._timeout = timeout
        self._secrets: set[str] = set()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(token_key={self._key!r})"

    # --- auth ---

    def _token(self) -> str:
        token = secrets.get(self._key)
        if not token:
            raise AuthError(f"{self._key} is not set",
                            hint=f"add {self._key} to {secrets.provider_file(self._provider)}")
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
            raise NetworkError(f"{self._label} Graph request failed ({type(exc).__name__})") from None
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
                raise AuthError(f"{self._label} rejected {self._key} (code 190): "
                                "token expired or invalid",
                                hint=f"renew the token and set {self._key}")
            if status == 429 or code in _RATE_CODES:
                if attempt == 0:
                    self._sleep(self._retry_after)
                    continue
                raise ProviderError("rate limited, retry later")
            msg = self._scrub(str(err.get("message", ""))) if isinstance(err, dict) else ""
            raise ProviderError(
                f"{self._label} Graph error (HTTP {status}, code {code}): {msg}".rstrip(": "))
        raise AssertionError("unreachable")

    def _paged(self, path: str, token: str, params: dict, limit: int | None = None):
        """Follow paging.next until the pages end or `limit` rows are collected."""
        raw: list[dict] = []
        rows: list[dict] = []
        url, query = f"{api_base(self._provider)}/{path}", {**params, "access_token": token}
        while url:
            body = self._call(url, query, raw, token)
            rows += body.get("data") or []
            if limit is not None and len(rows) >= limit:
                return rows[:limit], raw
            url, query = (body.get("paging") or {}).get("next"), None
        return rows, raw

    def _single(self, path: str, token: str, params: dict, soft=()):
        raw: list[dict] = []
        body = self._call(f"{api_base(self._provider)}/{path}", {**params, "access_token": token},
                          raw, token, soft)
        return body, raw
