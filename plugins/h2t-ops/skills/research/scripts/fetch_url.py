#!/usr/bin/env python3
"""fetch_url.py — provider ladder CLI for h2t-ops:research skill.

Spec: docs/superpowers/specs/2026-05-07-research-fetch-url-ladder.md
Issue: lichtpfad/h2t-skills#103
"""
from __future__ import annotations

__version__ = "0.0.1"

from datetime import datetime, timezone
from typing import Any

ENVELOPE_VERSION = "1"
FETCH_ENVELOPE_VERSION = "1"
PRIMARY_ENGINE = "fetch_ladder"


def build_fetch_envelope(
    *,
    status: str,
    url: str,
    final_url: str | None,
    provider_used: str,
    content_type: str,
    content_gate: str,
    title: str | None,
    body_markdown: str,
    body_text: str,
    body_chars: int,
    links: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    providers_skipped: dict[str, str],
    reason_for_failed: str | None,
    reason_for_degraded: str | None,
    raw_html_path: str | None,
    site: str | None,
    canonical_url: str | None,
    lang: str | None,
    detected_reason: str | None,
    user_agent: str,
) -> dict[str, Any]:
    """Assemble the fetch envelope per spec §4.1."""
    total_latency_ms = sum(a.get("latency_ms", 0) for a in attempts)
    return {
        "status": status,
        "url": url,
        "final_url": final_url,
        "provider_used": provider_used,
        "content_type": content_type,
        "content_gate": content_gate,
        "title": title,
        "body_markdown": body_markdown,
        "body_text": body_text,
        "body_chars": body_chars,
        "links": links,
        "metadata": {
            "canonical_url": canonical_url,
            "site": site,
            "lang": lang,
            "detected_reason": detected_reason,
            "site_adapter": None,
            "raw_html_path": raw_html_path,
        },
        "telemetry": {
            "attempts": attempts,
            "reason_for_degraded": reason_for_degraded,
            "reason_for_failed": reason_for_failed,
            "total_latency_ms": total_latency_ms,
            "providers_skipped": sorted(providers_skipped.keys()),
            "providers_skipped_reason": dict(providers_skipped),
        },
        "meta": {
            "primary_engine": PRIMARY_ENGINE,
            "envelope_version": ENVELOPE_VERSION,
            "fetch_envelope_version": FETCH_ENVELOPE_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "user_agent": user_agent,
        },
    }


from dataclasses import dataclass, field


class ProviderTransientError(Exception):
    """Retryable across providers: 5xx, 429, network timeout, URLError."""

    def __init__(self, message: str, *, provider: str, http_status: int | None,
                 latency_ms: int):
        super().__init__(message)
        self.provider = provider
        self.http_status = http_status
        self.latency_ms = latency_ms


class ProviderPermanentError(Exception):
    """Non-retryable for THIS provider; ladder may try next: 4xx, malformed."""

    def __init__(self, message: str, *, provider: str, http_status: int | None,
                 latency_ms: int):
        super().__init__(message)
        self.provider = provider
        self.http_status = http_status
        self.latency_ms = latency_ms


class ProviderHardGate(Exception):
    """Bypass forbidden — ladder STOPS, does not try further providers."""

    def __init__(self, message: str, *, provider: str, gate: str, latency_ms: int,
                 http_status: int | None = None):
        super().__init__(message)
        self.provider = provider
        self.gate = gate  # login_required | paid
        self.http_status = http_status
        self.latency_ms = latency_ms


class ProviderNotConfigured(Exception):
    """Provider exists but not enabled. Ladder skips silently."""

    def __init__(self, message: str, *, provider: str):
        super().__init__(message)
        self.provider = provider


@dataclass
class ProviderResult:
    provider: str
    http_status: int | None
    latency_ms: int
    final_url: str | None
    title: str | None
    body_markdown: str
    body_text: str
    body_chars: int
    links: list[dict[str, Any]]
    canonical_url: str | None
    lang: str | None
    raw_html: str | None
