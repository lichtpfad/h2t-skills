"""YouTube transcript provider for the h2t-ops research fetch ladder."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timezone  # noqa: F401
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi

ENVELOPE_VERSION = "1"


def is_youtube_url(url: str) -> bool:
    """Return True if url points to a YouTube video."""
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().lstrip("www.")
    return hostname in ("youtube.com", "youtu.be")


def _extract_video_id(url: str) -> str:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().lstrip("www.")
    if hostname == "youtu.be":
        return parsed.path.lstrip("/").split("?")[0]
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "shorts":
        return parts[1]
    raise ValueError(f"Cannot extract video_id from URL: {url}")


def _get_oembed(video_id: str) -> dict[str, Any]:
    oembed_url = (
        f"https://www.youtube.com/oembed"
        f"?url=https://www.youtube.com/watch?v={video_id}&format=json"
    )
    req = urllib.request.Request(
        oembed_url,
        headers={"User-Agent": "h2t-ops/research (youtube provider)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}


def _get_transcript(api: Any, video_id: str) -> tuple[list[Any], str]:
    """Return (segments, language_code). Priority: ru → en → any."""
    for lang in ("ru", "en"):
        try:
            segs = list(api.fetch(video_id, languages=[lang]))
            return segs, lang
        except Exception:
            continue
    # Fallback: any available
    segs = list(api.fetch(video_id))
    return segs, "unknown"


def fetch_youtube(
    url: str,
    *,
    output_dir: Path | None = None,
    project: str = "default",
) -> tuple[dict[str, Any], int]:
    """Fetch YouTube transcript and return a fetch-ladder-compatible envelope."""
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    t0 = time.monotonic()

    try:
        video_id = _extract_video_id(url)
    except ValueError as exc:
        return {
            "status": "FAILED",
            "provider_used": "youtube_transcript",
            "body_text": "",
            "body_chars": 0,
            "provenance": {"text_source": "youtube_transcript", "error": str(exc)},
            "telemetry": {"error": str(exc), "total_latency_ms": 0},
            "meta": {"envelope_version": ENVELOPE_VERSION, "timestamp": timestamp},
        }, 2

    meta = _get_oembed(video_id)

    try:
        api = YouTubeTranscriptApi()
        segments, language = _get_transcript(api, video_id)
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {
            "status": "FAILED",
            "provider_used": "youtube_transcript",
            "body_text": "",
            "body_chars": 0,
            "provenance": {
                "text_source": "youtube_transcript",
                "video_id": video_id,
                "author_name": meta.get("author_name", ""),
                "title": meta.get("title", ""),
                "error": str(exc),
            },
            "telemetry": {"error": str(exc), "total_latency_ms": latency_ms},
            "meta": {"envelope_version": ENVELOPE_VERSION, "timestamp": timestamp},
        }, 1

    body_text = " ".join(seg.text for seg in segments).strip()
    latency_ms = int((time.monotonic() - t0) * 1000)

    return {
        "status": "OK",
        "url": url,
        "final_url": url,
        "provider_used": "youtube_transcript",
        "content_type": "transcript",
        "content_gate": "none",
        "title": meta.get("title", ""),
        "body_markdown": body_text,
        "body_text": body_text,
        "body_chars": len(body_text),
        "links": [],
        "provenance": {
            "text_source": "youtube_transcript",
            "video_id": video_id,
            "author_name": meta.get("author_name", ""),
            "title": meta.get("title", ""),
            "language": language,
            "transcript_segments": len(segments),
        },
        "telemetry": {
            "attempts": [{"engine": "youtube_transcript", "latency_ms": latency_ms, "error": None}],
            "total_latency_ms": latency_ms,
        },
        "meta": {
            "primary_engine": "youtube_transcript",
            "envelope_version": ENVELOPE_VERSION,
            "timestamp": timestamp,
        },
    }, 0
