"""GranolaClient — pure API adapter for the Granola public API.

Read verbs only; no sync, no webhook receiver, no local state (sync.py owns
files and cursors). Requests imported lazily; load_secrets() called on init.
API contract: https://docs.granola.ai/api-reference/openapi.json
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from h2t_ops.core.errors import (
    AuthError,
    ConfigError,
    NetworkError,
    NotFoundError,
    ProviderError,
    UsageError,
)
from h2t_ops.core.secrets import load_secrets

# API caps, from the OpenAPI contract. Requesting more is a 400, not a courtesy clamp.
NOTES_PAGE_MAX = 30
TRANSCRIPT_PAGE_MAX = 100
FOLDERS_PAGE_MAX = 30


class _TranscriptTooLarge(Exception):
    """Get Note refused to inline the transcript (413) — page it separately."""


def _raise_for_status(resp: Any, context: str) -> None:
    """Map HTTP status to typed h2t_ops errors. Raises if status >= 400."""
    status = resp.status_code
    if status == 401:
        raise AuthError(f"GRANOLA_API_KEY invalid (401 from {context})")
    if status == 404:
        raise NotFoundError(f"Not found: {context}")
    if status == 413:
        raise _TranscriptTooLarge(context)
    if status == 400:
        raise UsageError(f"Bad request ({context}): {resp.text[:300]}")
    if status == 429:
        raise ProviderError(f"Granola rate limit exceeded ({context})")
    if status >= 500:
        raise ProviderError(f"Granola server error {status} ({context}): {resp.text[:200]}")


class GranolaClient:
    """Granola public API client."""

    def __init__(self) -> None:
        load_secrets()
        api_key = os.environ.get("GRANOLA_API_KEY", "").strip()
        if not api_key:
            raise ConfigError(
                "GRANOLA_API_KEY not set.",
                hint=(
                    "Add GRANOLA_API_KEY to ~/.dor/secrets/secrets.env "
                    "(legacy fallback: ~/.dor/secrets.env) or set in environment. "
                    "Create a key in Granola: Settings -> API."
                ),
            )
        self._api_key = api_key
        self._base_url = os.environ.get(
            "GRANOLA_BASE_URL", "https://public-api.granola.ai"
        ).rstrip("/")
        self._timeout = int(os.environ.get("GRANOLA_TIMEOUT", "30"))

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"}

    def _request(self, method: str, path: str, *,
                 params: Optional[Dict] = None,
                 json_body: Optional[Any] = None) -> Any:
        import requests as _r  # lazy — module-scope import forbidden
        url = f"{self._base_url}{path}" if path.startswith("/") else f"{self._base_url}/{path}"
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
                    f"Granola request failed after 3 attempts: {exc}"
                ) from exc
            if resp.status_code == 429:
                # Granola allows 25 requests per 5s, sustained 5/s; Retry-After is authoritative.
                retry_after = float(resp.headers.get("Retry-After", backoff))
                if attempt < 2:
                    time.sleep(retry_after)
                    backoff *= 2
                    continue
                return resp
            if resp.status_code >= 500 and attempt < 2:
                time.sleep(backoff)
                backoff *= 2
                continue
            return resp
        raise NetworkError(
            f"Granola request failed after 3 attempts: {last_exc or 'server error'}"
        )

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        resp = self._request("GET", path, params=params)
        _raise_for_status(resp, path)
        try:
            return resp.json()
        except ValueError:
            raise ProviderError(f"Malformed JSON from {path}")

    def auth_check(self) -> bool:
        """Returns True if the API key is valid; raises AuthError on 401."""
        resp = self._request("GET", "/v1/notes", params={"page_size": 1})
        if resp.status_code == 200:
            return True
        if resp.status_code == 401:
            raise AuthError("GRANOLA_API_KEY invalid (401)")
        raise ProviderError(f"auth-check: unexpected status {resp.status_code}")

    # ─── Read verbs ───────────────────────────────────────────────────────────

    def list_notes(
        self,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        updated_after: Optional[str] = None,
        folder_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Returns {rows: [...raw...], next_cursor: str|None, has_more: bool}.

        Without `limit` this fetches a single page of NOTES_PAGE_MAX. With a
        limit above the page cap it keeps paging until the limit is reached or
        the provider reports no more notes. Rows stay raw — normalization is
        the commands layer's job.
        """
        base: Dict[str, Any] = {}
        if created_after:
            base["created_after"] = created_after
        if created_before:
            base["created_before"] = created_before
        if updated_after:
            base["updated_after"] = updated_after
        if folder_id:
            base["folder_id"] = folder_id

        rows: List[Dict[str, Any]] = []
        next_cursor = cursor
        has_more = False
        while True:
            remaining = None if limit is None else limit - len(rows)
            page_size = NOTES_PAGE_MAX if remaining is None else min(remaining, NOTES_PAGE_MAX)
            params = {**base, "page_size": page_size}
            if next_cursor:
                params["cursor"] = next_cursor
            data = self._get("/v1/notes", params=params)
            rows.extend(data.get("notes") or [])
            next_cursor = data.get("cursor")
            has_more = bool(data.get("hasMore"))
            if not has_more or not next_cursor:
                break
            if limit is None or len(rows) >= limit:
                break
        if limit is not None and len(rows) > limit:
            # Provider should honour page_size, but never hand back more than asked.
            rows = rows[:limit]
        return {"rows": rows, "next_cursor": next_cursor, "has_more": has_more}

    def get_note(self, note_id: str, include_transcript: bool = False) -> Dict[str, Any]:
        """GET /v1/notes/{id}; on 413 the transcript is paged in separately."""
        params = {"include": "transcript"} if include_transcript else None
        try:
            return self._get(f"/v1/notes/{note_id}", params=params)
        except _TranscriptTooLarge:
            note = self._get(f"/v1/notes/{note_id}")
            paged = self.get_transcript(note_id)
            note["transcript"] = paged["transcript"]
            if paged.get("truncated"):
                note["transcript_truncated"] = True
            return note

    def get_transcript(self, note_id: str) -> Dict[str, Any]:
        """Fetch every transcript page; returns {transcript: [...], truncated: bool}."""
        items: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        max_pages = int(os.environ.get("GRANOLA_MAX_PAGES", "1000"))
        pages = 0
        truncated = False
        while True:
            if pages >= max_pages:
                truncated = True
                break
            params: Dict[str, Any] = {"page_size": TRANSCRIPT_PAGE_MAX}
            if cursor:
                params["cursor"] = cursor
            page = self._get(f"/v1/notes/{note_id}/transcript", params=params)
            items.extend(page.get("transcript") or [])
            cursor = page.get("cursor")
            pages += 1
            if not page.get("hasMore") or not cursor:
                break
        return {"transcript": items, "truncated": truncated}

    def list_folders(self) -> Dict[str, Any]:
        """Fetch every folder page; returns {rows: [...raw...]}."""
        rows: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        max_pages = int(os.environ.get("GRANOLA_MAX_PAGES", "1000"))
        pages = 0
        while pages < max_pages:
            params: Dict[str, Any] = {"page_size": FOLDERS_PAGE_MAX}
            if cursor:
                params["cursor"] = cursor
            page = self._get("/v1/folders", params=params)
            rows.extend(page.get("folders") or [])
            cursor = page.get("cursor")
            pages += 1
            if not page.get("hasMore") or not cursor:
                break
        return {"rows": rows}

    def list_webhook_endpoints(self) -> Dict[str, Any]:
        """GET /v1/webhook-endpoints — read-only; secrets are never returned here."""
        data = self._get("/v1/webhook-endpoints")
        return {"rows": data.get("webhook_endpoints") or []}

    def resolve_folder_id(self, folder: str) -> str:
        """Accept a folder ID or a folder name; return the ID."""
        if folder.startswith("fol_"):
            return folder
        wanted = folder.strip().casefold()
        matches = [f for f in self.list_folders()["rows"]
                   if (f.get("name") or "").strip().casefold() == wanted]
        if len(matches) > 1:
            ids = ", ".join(f"{m.get('id')} ({m.get('name')})" for m in matches)
            raise UsageError(
                f"folder name {folder!r} is ambiguous — pass the ID instead: {ids}"
            )
        if not matches:
            raise NotFoundError(
                f"No folder named {folder!r}.",
                hint="Run `h2t-ops granola folders` to see available folders.",
            )
        return matches[0]["id"]
