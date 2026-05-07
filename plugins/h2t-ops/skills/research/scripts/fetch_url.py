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


from html.parser import HTMLParser
from urllib.parse import urljoin


class _InlineExtractor(HTMLParser):
    """Minimal stdlib HTML extractor.

    Strategy:
    - Drop content inside <script>, <style>, <noscript>, <head>, <nav>,
      <header>, <footer>, <aside>, <form>.
    - Prefer body inside <article> if present; else <main>; else everything.
    - Emit a stream of (kind, text) tokens that the caller turns into
      markdown + plain text.
    """

    SKIP_TAGS = {"script", "style", "noscript", "nav", "header", "footer",
                 "aside", "form", "iframe"}
    BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br",
                  "div", "tr", "blockquote", "pre"}
    HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_article = False
        self._has_article = False
        self.title: str | None = None
        self._in_title = False
        self._capture_outside_article = True
        self._tokens: list[tuple[str, str]] = []
        self._current_text: list[str] = []
        self._current_link: dict[str, Any] | None = None
        self.links: list[dict[str, Any]] = []
        self.canonical_url: str | None = None
        self.lang: str | None = None
        self._in_head = False

    # ---- helpers ----

    def _emit_block(self, tag: str) -> None:
        if not self._current_text:
            return
        text = "".join(self._current_text).strip()
        self._current_text = []
        if not text:
            return
        kind = "h" + tag[1] if tag in self.HEADING_TAGS else "p"
        self._tokens.append((kind, text))

    def _capturing(self) -> bool:
        if self._skip_depth > 0:
            return False
        if self._has_article:
            return self._in_article
        return self._capture_outside_article

    # ---- parser hooks ----

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang") or self.lang
            return
        if tag == "head":
            self._in_head = True
            return
        if tag == "title" and self._in_head:
            self._in_title = True
            return
        if tag == "link" and self._in_head and a.get("rel") == "canonical":
            self.canonical_url = a.get("href")
            return
        if tag == "article":
            self._has_article = True
            self._in_article = True
            return
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if not self._capturing():
            return
        if tag in self.BLOCK_TAGS or tag in self.HEADING_TAGS:
            self._emit_block(tag)
            self._pending_block = tag
        if tag == "a":
            href = a.get("href") or ""
            self._current_link = {"href": href, "text": ""}

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self._in_head = False
            return
        if tag == "title":
            self._in_title = False
            return
        if tag == "article":
            self._in_article = False
            self._emit_block("p")
            return
        if tag in self.SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if not self._capturing():
            return
        if tag == "a" and self._current_link is not None:
            text = self._current_link["text"].strip()
            href = self._current_link["href"]
            if href:
                self.links.append({"href": href, "text": text, "rel": ""})
            self._current_link = None
        if tag in self.BLOCK_TAGS or tag in self.HEADING_TAGS:
            block_kind = getattr(self, "_pending_block", "p")
            self._emit_block(block_kind)

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title = (self.title or "") + data
            return
        if not self._capturing():
            return
        if self._current_link is not None:
            self._current_link["text"] += data
        self._current_text.append(data)

    def finish(self) -> None:
        self._emit_block("p")
        if self.title is not None:
            self.title = self.title.strip()


def _tokens_to_markdown_and_text(tokens: list[tuple[str, str]]) -> tuple[str, str]:
    md_lines: list[str] = []
    text_lines: list[str] = []
    for kind, text in tokens:
        if kind.startswith("h"):
            level = int(kind[1])
            md_lines.append(f"{'#' * level} {text}")
        else:
            md_lines.append(text)
        text_lines.append(text)
        md_lines.append("")
        text_lines.append("")
    md = "\n".join(md_lines).strip()
    txt = "\n".join(text_lines).strip()
    return md, txt


def _inline_extract(
    html: str, *, base_url: str,
) -> tuple[str | None, str, str, list[dict[str, Any]], str | None, str | None]:
    """Return (title, body_markdown, body_text, links, canonical_url, lang)."""
    p = _InlineExtractor()
    p.feed(html)
    p.finish()
    md, txt = _tokens_to_markdown_and_text(p._tokens)
    # Resolve relative hrefs.
    for link in p.links:
        if link["href"]:
            link["href"] = urljoin(base_url, link["href"])
    return p.title, md, txt, p.links, p.canonical_url, p.lang


import time
import urllib.error
import urllib.request

DEFAULT_USER_AGENT = (
    "h2t-research-fetch/0.0.1 (+https://github.com/lichtpfad/h2t-skills)"
)


def _site_from_url(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).hostname or ""


class DirectProvider:
    """stdlib urllib.request fetcher with inline extraction."""

    name = "direct"

    def is_configured(self, env: dict[str, str], config: dict[str, Any]) -> bool:
        # Direct is always available.
        return True

    def fetch(self, url: str, *, timeout_ms: int, user_agent: str) -> ProviderResult:
        req = urllib.request.Request(url, headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en,*;q=0.5",
        })
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout_ms / 1000) as resp:
                raw_bytes = resp.read()
                final_url = resp.geturl() or url
                resp_headers = dict(resp.headers.items()) if hasattr(resp.headers, "items") else dict(resp.headers)
                http_status = getattr(resp, "status", 200)
        except urllib.error.HTTPError as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            self._raise_http_error(e, url=url, latency_ms=latency_ms)
            raise  # unreachable
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            raise ProviderTransientError(
                f"network: {e}", provider=self.name,
                http_status=None, latency_ms=latency_ms,
            )
        latency_ms = int((time.monotonic() - t0) * 1000)
        encoding = _detect_encoding(resp_headers, raw_bytes)
        html_text = raw_bytes.decode(encoding, errors="replace")
        title, md, txt, links, canonical, lang = _inline_extract(
            html_text, base_url=final_url,
        )
        site = _site_from_url(final_url)
        # Hard-gate short-circuit on the basis of body content (200 + gated DOM):
        if _detect_login_wall(html=html_text, final_url=final_url):
            raise ProviderHardGate(
                "login wall in body", provider=self.name,
                gate="login_required", http_status=http_status, latency_ms=latency_ms,
            )
        if _detect_paywall(html=html_text, site=site):
            raise ProviderHardGate(
                "paywall in body", provider=self.name,
                gate="paid", http_status=http_status, latency_ms=latency_ms,
            )
        return ProviderResult(
            provider=self.name,
            http_status=http_status,
            latency_ms=latency_ms,
            final_url=final_url,
            title=title,
            body_markdown=md,
            body_text=txt,
            body_chars=len(txt),
            links=links,
            canonical_url=canonical,
            lang=lang,
            raw_html=html_text,
        )

    def _raise_http_error(self, e: urllib.error.HTTPError, *, url: str,
                          latency_ms: int) -> None:
        code = e.code
        # Auth-gated: 401 with WWW-Authenticate, OR 403 with explicit auth signal.
        hdrs = {}
        try:
            if hasattr(e, "headers") and e.headers is not None:
                hdrs = {k.lower(): v for k, v in e.headers.items()}
        except Exception:
            hdrs = {}
        if code == 401 and "www-authenticate" in hdrs:
            raise ProviderHardGate(
                "auth required", provider=self.name,
                gate="login_required", http_status=code, latency_ms=latency_ms,
            )
        if code == 429 or 500 <= code <= 599:
            raise ProviderTransientError(
                f"http {code}", provider=self.name,
                http_status=code, latency_ms=latency_ms,
            )
        raise ProviderPermanentError(
            f"http {code}", provider=self.name,
            http_status=code, latency_ms=latency_ms,
        )


def _detect_encoding(headers: dict[str, str], body: bytes) -> str:
    ct = headers.get("Content-Type", "") or headers.get("content-type", "")
    if "charset=" in ct.lower():
        return ct.lower().split("charset=", 1)[1].split(";")[0].strip() or "utf-8"
    return "utf-8"


import re

_SCRIPT_TAG_RE = re.compile(r"<script\b[^>]*>", re.IGNORECASE)


def _detect_js_shell(*, html: str, body_text: str) -> bool:
    """Heuristic: SPA skeleton — short body + many script tags."""
    if len(body_text) >= 200:
        return False
    return len(_SCRIPT_TAG_RE.findall(html)) >= 5


LOGIN_DOM_TOKENS = (
    'class="login-required"',
    'data-auth="required"',
    'id="login-form"',
)

_LOGIN_FORM_ACTION_RE = re.compile(
    r'<form\b[^>]*action=["\'](/(?:login|signin|auth)[^"\']*)["\']',
    re.IGNORECASE,
)
_META_REFRESH_LOGIN_RE = re.compile(
    r'<meta\b[^>]*http-equiv=["\']refresh["\'][^>]*url=([^"\'>\s]+)',
    re.IGNORECASE,
)


def _detect_login_wall(*, html: str, final_url: str) -> bool:
    if any(tok in html for tok in LOGIN_DOM_TOKENS):
        return True
    if _LOGIN_FORM_ACTION_RE.search(html):
        return True
    m = _META_REFRESH_LOGIN_RE.search(html)
    if m:
        target = m.group(1).lower()
        if "/login" in target or "/signin" in target or "/auth" in target:
            return True
    if final_url:
        path = final_url.lower()
        if "/login" in path or "/signin" in path:
            return True
    return False


PAYWALL_DOM_TOKENS = (
    'data-paid="true"',
    'class="paywall-active"',
    'class="article-paywall"',
    'itemtype="https://schema.org/Paywall"',
)

KNOWN_PAYWALLED_DOMAINS: set[str] = set()  # populated in follow-up


def _detect_paywall(*, html: str, site: str) -> bool:
    if site and site.lower() in KNOWN_PAYWALLED_DOMAINS:
        return True
    return any(tok in html for tok in PAYWALL_DOM_TOKENS)


def _classify_content(
    *, html: str, body_text: str, final_url: str, site: str,
    min_body_chars: int,
) -> tuple[str, str]:
    """Return (content_type, content_gate)."""
    if _detect_login_wall(html=html, final_url=final_url):
        return "gated", "login_required"
    if _detect_paywall(html=html, site=site):
        return "gated", "paid"
    if _detect_js_shell(html=html, body_text=body_text):
        return "js_shell", "none"
    if len(body_text) < min_body_chars:
        return "short_body", "none"
    # Listing heuristic: many <li><a> relative to text — punt for PR#1.
    return "article", "none"
