"""Author/channel resolution cascade for research workflows.

Resolution order:
  1. Exa people search — extract YouTube URLs from results
  2. Handle guesses + YouTube oEmbed validation
  3. AllTD uploader page check
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

_YOUTUBE_URL_RE = re.compile(
    r"https?://(?:www\.)?youtube\.com/@?[\w.-]+|https?://youtu\.be/[\w.-]+"
)


def _exa_people_search(
    name: str,
    keywords: list[str] | None,
    api_key: str,
) -> str | None:
    """Search Exa people mode. Return first YouTube URL found, or None."""
    from h2t_ops.connectors.research.exa import call_exa

    kw_str = " ".join(keywords) if keywords else ""
    query = f"{name} {kw_str} YouTube".strip()
    body = {
        "query": query,
        "type": "auto",
        "category": "people",
        "numResults": 5,
        "contents": {"highlights": {"maxCharacters": 2000}},
    }
    from h2t_ops.core.errors import AuthError, NetworkError
    from h2t_ops.core.errors import ProviderError as _ProviderError
    try:
        _status, data, _latency = call_exa("/search", body, api_key)
    except (AuthError, NetworkError, _ProviderError):
        raise  # Propagate typed errors — callers must distinguish from not_found
    except Exception:
        return None

    for result in data.get("results", []):
        url = result.get("url", "")
        if "youtube.com" in url or "youtu.be" in url:
            return url
        for hl in (result.get("highlights") or []):
            m = _YOUTUBE_URL_RE.search(hl)
            if m:
                return m.group(0)
    return None


def _oembed_channel_validate(handle: str) -> dict[str, Any]:
    """Try YouTube oEmbed for a channel handle. Returns {} on failure."""
    probe_url = f"https://www.youtube.com/@{handle}"
    req = urllib.request.Request(
        f"https://www.youtube.com/oembed?url={probe_url}&format=json",
        headers={"User-Agent": "h2t-ops/research"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}


def _alltd_uploader_check(name: str) -> str | None:
    """Check if alltd.org/uploader/<handle>/ exists. Returns URL if found, else None."""
    handle = name.lower().replace(" ", "")
    url = f"https://alltd.org/uploader/{handle}/"
    req = urllib.request.Request(url, headers={"User-Agent": "h2t-ops/research"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return url
    except Exception:
        pass
    return None


def resolve_author(
    name: str,
    *,
    api_key: str,
    hint: str | None = None,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Resolve an author name to a channel URL using a cascade strategy.

    Returns a dict with keys: name, channel_url, author_confirmed,
    resolution_path, confidence.

    confidence: "confirmed" | "likely" | "not_found" | "error"
    Exit 0 in all cases except "error" — not_found is an honest result.
    """
    resolution_path: list[str] = []

    from h2t_ops.core.errors import AuthError, NetworkError
    from h2t_ops.core.errors import ProviderError as _ProviderError
    # Step 1: Exa people search
    try:
        exa_url = _exa_people_search(name, keywords, api_key)
    except (AuthError, NetworkError, _ProviderError) as exc:
        return {
            "name": name,
            "channel_url": None,
            "author_confirmed": None,
            "resolution_path": [f"exa_people: provider error — {type(exc).__name__}: {exc}"],
            "confidence": "error",
        }
    if exa_url:
        resolution_path.append(f"exa_people: found {exa_url}")
        return {
            "name": name,
            "channel_url": exa_url,
            "author_confirmed": name,
            "resolution_path": resolution_path,
            "confidence": "confirmed",
        }
    resolution_path.append("exa_people: no YouTube URL in results")

    # Step 2: Handle guesses + oEmbed
    handle_candidates = [name, name.lower(), name.replace(" ", ""), name.replace(" ", "").lower()]
    for handle in dict.fromkeys(handle_candidates):  # deduplicate preserving order
        meta = _oembed_channel_validate(handle)
        if meta.get("author_name"):
            channel_url = f"https://youtube.com/@{handle}"
            resolution_path.append(f"handle_guess @{handle}: oembed confirmed ({meta['author_name']})")
            return {
                "name": name,
                "channel_url": channel_url,
                "author_confirmed": meta["author_name"],
                "resolution_path": resolution_path,
                "confidence": "confirmed",
            }
        resolution_path.append(f"handle_guess @{handle}: oembed not confirmed")

    # Step 3: AllTD uploader page
    alltd_url = _alltd_uploader_check(name)
    if alltd_url:
        resolution_path.append(f"alltd_uploader: found {alltd_url}")
        return {
            "name": name,
            "channel_url": alltd_url,
            "author_confirmed": None,
            "resolution_path": resolution_path,
            "confidence": "likely",
        }
    resolution_path.append("alltd_uploader: not found")

    resolution_path.append("all_strategies: not_found")
    return {
        "name": name,
        "channel_url": None,
        "author_confirmed": None,
        "resolution_path": resolution_path,
        "confidence": "not_found",
    }
