"""MeetGeekClient — pure API adapter (parity for #134).

Re-wraps ten verbs from meetgeek_cli.py. No sync, no webhook, no local state.
Requests imported lazily; h2t_ops.core.secrets.load_secrets() called on init.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from h2t_ops.core.errors import (
    AuthError,
    ConfigError,
    NetworkError,
    NotFoundError,
    ProviderError,
    UsageError,
)
from h2t_ops.core.secrets import load_secrets


def _raise_for_status(resp: Any, context: str) -> None:
    """Map HTTP status to typed h2t_ops errors. Raises if status >= 400."""
    status = resp.status_code
    if status == 401:
        raise AuthError(f"MEETGEEK_API_KEY invalid (401 from {context})")
    if status == 404:
        raise NotFoundError(f"Not found: {context}")
    if status == 400:
        raise UsageError(f"Bad request ({context}): {resp.text[:300]}")
    if status == 429:
        raise ProviderError(f"MeetGeek rate limit exceeded ({context})")
    if status >= 500:
        raise ProviderError(f"MeetGeek server error {status} ({context}): {resp.text[:200]}")


class MeetGeekClient:
    """MeetGeek API client — 10 pure-API verbs, no local state."""

    def __init__(self) -> None:
        load_secrets()
        api_key = os.environ.get("MEETGEEK_API_KEY", "").strip()
        if not api_key:
            raise ConfigError(
                "MEETGEEK_API_KEY not set.",
                hint="Add MEETGEEK_API_KEY to ~/.dor/secrets.env or set in environment. "
                     "Registry: ~/.h2t/config/secrets/meetgeek.md",
            )
        self._api_key = api_key
        self._base_url = os.environ.get(
            "MEETGEEK_BASE_URL", "https://api.meetgeek.ai"
        ).rstrip("/")
        self._timeout = int(os.environ.get("MEETGEEK_TIMEOUT", "30"))

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"}

    def _request(self, method: str, path: str, *,
                 params: Optional[Dict] = None,
                 json_body: Optional[Any] = None) -> Any:
        import requests as _r  # lazy — module-scope import forbidden
        url = (
            f"{self._base_url}{path}"
            if path.startswith("/")
            else f"{self._base_url}/{path}"
        )
        backoff = 1.0
        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                resp = _r.request(
                    method, url,
                    headers=self._headers(),
                    params=params,
                    json=json_body,
                    timeout=self._timeout,
                )
            except _r.RequestException as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise NetworkError(
                    f"MeetGeek request failed after 3 attempts: {exc}"
                ) from exc
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", backoff))
                if attempt < 2:
                    time.sleep(retry_after)
                    backoff *= 2
                    continue
                raise NetworkError(f"MeetGeek rate limit — 429 after 3 attempts ({path})")
            if resp.status_code >= 500 and attempt < 2:
                time.sleep(backoff)
                backoff *= 2
                continue
            return resp
        raise NetworkError(
            f"MeetGeek request failed after 3 attempts: {last_exc or 'server error'}"
        )

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        resp = self._request("GET", path, params=params)
        _raise_for_status(resp, path)
        try:
            return resp.json()
        except ValueError:
            raise ProviderError(f"Malformed JSON from {path}")

    # ─── Read verbs ───────────────────────────────────────────────────────────

    def auth_check(self) -> bool:
        """Returns True if API key is valid; raises AuthError on 401."""
        resp = self._request("GET", "/v1/meetings", params={"limit": 1})
        if resp.status_code == 200:
            return True
        if resp.status_code == 401:
            raise AuthError("MEETGEEK_API_KEY invalid (401)")
        raise ProviderError(f"auth-check: unexpected status {resp.status_code}")

    def list_meetings(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Returns {rows: [...raw...], next_cursor: str|None}.

        Rows are raw API items — normalization (meeting_id|id, timestamps)
        is the commands layer's responsibility.
        """
        params: Dict[str, Any] = {}
        if cursor:
            params["cursor"] = cursor
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date
        if limit:
            params["limit"] = limit
        data = self._get("/v1/meetings", params=params)
        if isinstance(data, list):
            rows = data
            next_cursor = None
        else:
            rows = data.get("meetings") or data.get("items") or data.get("data") or []
            pagination = data.get("pagination") or {}
            next_cursor = (
                pagination.get("next_cursor")
                or data.get("next_cursor")
                or data.get("cursor")
            )
        return {"rows": rows, "next_cursor": next_cursor}

    def get_meeting(self, meeting_id: str) -> Dict[str, Any]:
        """/v1/meeting/{id} — note singular endpoint."""
        return self._get(f"/v1/meeting/{meeting_id}")

    def get_transcript(self, meeting_id: str) -> Dict[str, Any]:
        """Fetches all transcript pages; returns {sentences: [...], ...metadata}."""
        sentences = []
        base: Dict[str, Any] = {}
        cursor: Optional[str] = None
        pages = 0
        max_pages = int(os.environ.get("MEETGEEK_MAX_PAGES", "1000"))
        while True:
            if pages >= max_pages:
                break
            params = {"cursor": cursor} if cursor else None
            page = self._get(f"/v1/meetings/{meeting_id}/transcript", params=params)
            if pages == 0:
                base = {
                    k: v for k, v in page.items()
                    if k not in ("sentences", "transcript", "pagination")
                }
            page_sentences = page.get("sentences") or page.get("transcript") or []
            sentences.extend(page_sentences)
            pagination = page.get("pagination") or {}
            cursor = pagination.get("next_cursor") or page.get("next_cursor")
            pages += 1
            if not cursor or not page_sentences:
                break
        return {**base, "sentences": sentences}

    def get_summary(self, meeting_id: str) -> Dict[str, Any]:
        return self._get(f"/v1/meetings/{meeting_id}/summary")

    def get_highlights(self, meeting_id: str) -> Dict[str, Any]:
        return self._get(f"/v1/meetings/{meeting_id}/highlights")

    def get_insights(self, meeting_id: str) -> Dict[str, Any]:
        return self._get(f"/v1/meetings/{meeting_id}/insights")

    def get_teams(self) -> Any:
        return self._get("/v1/teams")

    def get_download_url(self, meeting_id: str) -> Dict[str, Any]:
        """POST /v1/meetings/{id}/download → {meeting_id, download_url}.

        Returns URL only — never writes file to disk.
        T0 confirmed: primary field is download_link; fallback: download_url, url.
        """
        resp = self._request("POST", f"/v1/meetings/{meeting_id}/download")
        _raise_for_status(resp, f"/v1/meetings/{meeting_id}/download")
        try:
            info = resp.json()
        except ValueError:
            raise ProviderError(f"Malformed JSON from /download for {meeting_id}")
        url = (
            info.get("download_link")
            or info.get("download_url")
            or info.get("url")
        )
        if not url:
            raise ProviderError(f"No download URL in response for {meeting_id}: {info!r}")
        return {"meeting_id": meeting_id, "download_url": url}

    # ─── Write verb ───────────────────────────────────────────────────────────

    def submit_url(
        self,
        download_url: str,
        *,
        title: Optional[str] = None,
        language_code: Optional[str] = None,
        template_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /v1/upload — single provider-write verb.

        Named submit_url to distinguish from the upload --from-file pipeline (#149).
        T0 confirmed: API body field is "language" (not "language_code").
        The language_code parameter maps to body key "language".
        """
        if not download_url:
            raise UsageError("submit-url: download_url is required and must be non-empty")
        body: Dict[str, Any] = {"download_url": download_url}
        if title:
            body["title"] = title
        if language_code:
            body["language"] = language_code  # API field is "language", not "language_code"
        if template_name:
            body["template_name"] = template_name
        resp = self._request("POST", "/v1/upload", json_body=body)
        _raise_for_status(resp, "/v1/upload")
        try:
            return resp.json()
        except ValueError:
            return {"message": resp.text[:500]}
