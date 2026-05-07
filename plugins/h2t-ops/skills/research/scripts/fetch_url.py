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

try:
    import trafilatura as _trafilatura_module  # type: ignore
    _TRAFILATURA_AVAILABLE = True
except Exception:  # pragma: no cover
    _trafilatura_module = None  # type: ignore
    _TRAFILATURA_AVAILABLE = False

_trafilatura_warned = False


def _reset_trafilatura_warned_for_tests() -> None:
    global _trafilatura_warned
    _trafilatura_warned = False


def _extract_with_optional_uplift(
    html: str, *, base_url: str,
) -> tuple[str | None, str, str, list[dict[str, Any]], str | None, str | None]:
    title, md, txt, links, canonical, lang = _inline_extract(
        html, base_url=base_url,
    )
    global _trafilatura_warned
    import sys as _sys
    if not _TRAFILATURA_AVAILABLE:
        if not _trafilatura_warned:
            print("FETCH_WARN:NO_TRAFILATURA inline parser only", file=_sys.stderr)
            _trafilatura_warned = True
        return title, md, txt, links, canonical, lang
    try:
        uplift_text = _trafilatura_module.extract(html) or ""
    except Exception:
        uplift_text = ""
    if uplift_text and len(uplift_text) > len(txt):
        return title, uplift_text, uplift_text, links, canonical, lang
    return title, md, txt, links, canonical, lang


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
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout_ms / 1000) as resp:
                raw_bytes = resp.read()
                final_url = resp.geturl() or url
                resp_headers = dict(resp.headers.items()) if hasattr(resp.headers, "items") else dict(resp.headers)
                http_status = getattr(resp, "status", 200)
        except urllib.error.HTTPError as e:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            self._raise_http_error(e, url=url, latency_ms=latency_ms)
            raise  # unreachable
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            raise ProviderTransientError(
                f"network: {e}", provider=self.name,
                http_status=None, latency_ms=latency_ms,
            )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        encoding = _detect_encoding(resp_headers, raw_bytes)
        html_text = raw_bytes.decode(encoding, errors="replace")
        title, md, txt, links, canonical, lang = _extract_with_optional_uplift(
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


import os

JINA_ENDPOINT_DEFAULT = "https://r.jina.ai/"


class JinaProvider:
    """Fetch via Jina Reader URL-to-markdown relay."""

    name = "jina"

    def is_configured(self, env: dict[str, str], config: dict[str, Any]) -> bool:
        cfg = (config.get("providers") or {}).get(self.name) or {}
        return bool(cfg.get("enabled", True))

    def fetch(self, url: str, *, timeout_ms: int, user_agent: str) -> ProviderResult:
        endpoint = JINA_ENDPOINT_DEFAULT.rstrip("/") + "/"
        target = endpoint + url
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/markdown",
            "X-Return-Format": "markdown",
        }
        api_key = os.environ.get("JINA_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = urllib.request.Request(target, headers=headers)
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout_ms / 1000) as resp:
                raw = resp.read()
                final_url = resp.geturl() or target
                http_status = getattr(resp, "status", 200)
        except urllib.error.HTTPError as e:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            self._raise_http_error(e, latency_ms=latency_ms)
            raise  # unreachable
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            raise ProviderTransientError(
                f"network: {e}", provider=self.name,
                http_status=None, latency_ms=latency_ms,
            )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        markdown_text = raw.decode("utf-8", errors="replace")
        title = _jina_extract_title(markdown_text)
        body_md = _jina_extract_body(markdown_text)
        body_text = body_md  # markdown ≈ text for Jina output
        return ProviderResult(
            provider=self.name,
            http_status=http_status,
            latency_ms=latency_ms,
            final_url=url,  # logical URL, not the relay
            title=title,
            body_markdown=body_md,
            body_text=body_text,
            body_chars=len(body_text),
            links=[],
            canonical_url=None,
            lang=None,
            raw_html=markdown_text,  # Jina returns markdown; keep for --keep-raw
        )

    def _raise_http_error(self, e: urllib.error.HTTPError, *,
                          latency_ms: int) -> None:
        code = e.code
        if code == 429 or 500 <= code <= 599:
            raise ProviderTransientError(
                f"http {code}", provider=self.name,
                http_status=code, latency_ms=latency_ms,
            )
        raise ProviderPermanentError(
            f"http {code}", provider=self.name,
            http_status=code, latency_ms=latency_ms,
        )


def _jina_extract_title(md: str) -> str | None:
    for line in md.splitlines():
        s = line.strip()
        if s.lower().startswith("title:"):
            return s.split(":", 1)[1].strip()
        if s.startswith("# "):
            return s[2:].strip()
    return None


def _jina_extract_body(md: str) -> str:
    """Drop the Jina header block ('Title:', 'URL Source:', empty lines) and
    return the actual content after 'Markdown Content:' marker."""
    lines = md.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("markdown content:"):
            return "\n".join(lines[i + 1:]).strip()
    # No marker — return the whole thing.
    return md.strip()


class _StubProvider:
    name = "stub"

    def is_configured(self, env: dict[str, str], config: dict[str, Any]) -> bool:
        return False

    def fetch(self, url: str, *, timeout_ms: int, user_agent: str) -> ProviderResult:
        raise ProviderNotConfigured(
            f"{self.name} stub: implementation deferred to follow-up PR.",
            provider=self.name,
        )


class PlaywrightProvider(_StubProvider):
    name = "playwright"


class Crawl4AIProvider(_StubProvider):
    name = "crawl4ai"


class FirecrawlProvider(_StubProvider):
    name = "firecrawl"


class BrowserlessProvider(_StubProvider):
    name = "browserless"


import json
from pathlib import Path

DEFAULT_CONFIG: dict[str, Any] = {
    "providers": {
        "direct": {"enabled": True, "user_agent": DEFAULT_USER_AGENT,
                   "timeout_ms": 15000},
        "jina": {"enabled": True, "endpoint": JINA_ENDPOINT_DEFAULT,
                 "timeout_ms": 20000},
        "playwright": {"enabled": False, "timeout_ms": 30000},
        "crawl4ai": {"enabled": False},
        "firecrawl": {"enabled": False},
        "browserless": {"enabled": False},
    },
    "ladder": {
        "default_order": ["direct", "jina", "playwright", "crawl4ai",
                          "firecrawl", "browserless"],
        "cumulative_timeout_ms": 60000,
        "per_provider_timeout_ms": 15000,
        "min_body_chars": 200,
    },
    "gating": {
        "abort_on_login_required": True,
        "abort_on_paid": True,
    },
}


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in base.items():
        out[k] = dict(v) if isinstance(v, dict) else v
        if isinstance(v, dict):
            out[k] = _deep_merge(v, {})
    for k, v in over.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: Path | str | None) -> dict[str, Any]:
    """Load JSON config from path; return defaults if path missing or None."""
    if path is None:
        return _deep_merge(DEFAULT_CONFIG, {})
    p = Path(path)
    if not p.is_file():
        return _deep_merge(DEFAULT_CONFIG, {})
    user = json.loads(p.read_text(encoding="utf-8"))
    return _deep_merge(DEFAULT_CONFIG, user)


import sys

LADDER_CLASSES: dict[str, type] = {
    "direct": DirectProvider,
    "jina": JinaProvider,
    "playwright": PlaywrightProvider,
    "crawl4ai": Crawl4AIProvider,
    "firecrawl": FirecrawlProvider,
    "browserless": BrowserlessProvider,
}

CUMULATIVE_TIMEOUT_WARN = "FETCH_WARN:CUMULATIVE_TIMEOUT_EXHAUSTED"


def _attempt_record(provider: str, http: int | None, latency_ms: int,
                    error: str | None) -> dict[str, Any]:
    return {"provider": provider, "http": http,
            "latency_ms": latency_ms, "error": error}


def fetch_via_ladder(
    *,
    url: str,
    provider_choice: str,
    config: dict[str, Any],
    user_agent: str,
    keep_raw: bool,
    min_body_chars: int | None = None,
    output_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    """Run the provider ladder for `url`. Returns envelope dict."""
    if min_body_chars is None:
        min_body_chars = int(config["ladder"]["min_body_chars"])
    per_timeout = int(config["ladder"]["per_provider_timeout_ms"])
    cum_timeout = int(config["ladder"]["cumulative_timeout_ms"])

    order: list[str]
    if provider_choice == "auto":
        order = list(config["ladder"]["default_order"])
    else:
        order = [provider_choice]

    attempts: list[dict[str, Any]] = []
    skipped: dict[str, str] = {}
    candidates: list[ProviderResult] = []
    chosen: ProviderResult | None = None
    final_status: str = "FAILED"
    content_type = "unknown"
    content_gate = "none"
    reason_for_failed: str | None = None
    reason_for_degraded: str | None = None
    cumulative_ms = 0

    for name in order:
        if name not in LADDER_CLASSES:
            skipped[name] = "unknown_provider"
            continue
        provider = LADDER_CLASSES[name]()
        if provider_choice == "auto" and not provider.is_configured(
            env=dict(os.environ), config=config,
        ):
            # Distinguish stub vs disabled-in-config.
            if isinstance(provider, _StubProvider):
                skipped[name] = "not_configured_stub"
            else:
                skipped[name] = "disabled_in_config"
            continue
        if cumulative_ms >= cum_timeout:
            skipped[name] = "cumulative_timeout_exhausted"
            print(f"{CUMULATIVE_TIMEOUT_WARN} skipped={name}", file=sys.stderr)
            continue
        try:
            r = provider.fetch(url, timeout_ms=per_timeout, user_agent=user_agent)
        except ProviderHardGate as e:
            attempts.append(_attempt_record(
                name, e.http_status, e.latency_ms, "fetch_gated_" + e.gate,
            ))
            cumulative_ms += e.latency_ms
            content_type = "gated"
            content_gate = e.gate
            reason_for_failed = "content_gate_" + e.gate
            final_status = "FAILED"
            break
        except ProviderPermanentError as e:
            attempts.append(_attempt_record(
                name, e.http_status, e.latency_ms, "fetch_http_4xx_nonretryable",
            ))
            cumulative_ms += e.latency_ms
            continue
        except ProviderTransientError as e:
            attempts.append(_attempt_record(
                name, e.http_status, e.latency_ms,
                "fetch_network_timeout" if e.http_status is None
                else "fetch_http_5xx_retryable",
            ))
            cumulative_ms += e.latency_ms
            continue
        except ProviderNotConfigured:
            skipped[name] = "not_configured_stub"
            continue

        cumulative_ms += r.latency_ms
        # Classify result on the basis of body content.
        ct, gate = _classify_content(
            html=r.raw_html or "",
            body_text=r.body_text,
            final_url=r.final_url or url,
            site=_site_from_url(r.final_url or url),
            min_body_chars=min_body_chars,
        )
        if gate != "none":
            attempts.append(_attempt_record(
                name, r.http_status, r.latency_ms, "fetch_gated_" + gate,
            ))
            content_type = "gated"
            content_gate = gate
            reason_for_failed = "content_gate_" + gate
            final_status = "FAILED"
            break
        if ct == "article":
            attempts.append(_attempt_record(
                name, r.http_status, r.latency_ms, None,
            ))
            chosen = r
            content_type = ct
            final_status = "OK"
            break
        # DEGRADED-class result — record and continue.
        err_label = "fetch_js_shell" if ct == "js_shell" else "fetch_short_body"
        attempts.append(_attempt_record(
            name, r.http_status, r.latency_ms, err_label,
        ))
        candidates.append(r)
        content_type = ct  # last-seen DEGRADED type as fallback

    # Record skip reasons for providers that follow an early break/success.
    attempted_or_skipped = {a["provider"] for a in attempts} | set(skipped.keys())
    for name in order:
        if name in attempted_or_skipped:
            continue
        if name not in LADDER_CLASSES:
            skipped[name] = "unknown_provider"
            continue
        provider = LADDER_CLASSES[name]()
        if not provider.is_configured(env=dict(os.environ), config=config):
            if isinstance(provider, _StubProvider):
                skipped[name] = "not_configured_stub"
            else:
                skipped[name] = "disabled_in_config"
        else:
            skipped[name] = "not_attempted"

    if chosen is None and final_status != "OK" and content_gate == "none":
        # All ran but none returned article. Pick best candidate or FAILED.
        if candidates:
            chosen = max(candidates, key=lambda c: c.body_chars)
            final_status = "DEGRADED"
            reason_for_degraded = (
                "all_providers_degraded_short_body"
                if all(c.body_chars < min_body_chars for c in candidates)
                else "all_providers_degraded_js_shell"
            )
        else:
            final_status = "FAILED"
            reason_for_failed = (
                reason_for_failed or "all_providers_failed"
            )

    # Build envelope.
    if chosen is not None:
        title = chosen.title
        md = chosen.body_markdown
        txt = chosen.body_text
        body_chars = chosen.body_chars
        links = chosen.links
        canonical = chosen.canonical_url
        lang = chosen.lang
        final_url = chosen.final_url
        provider_used = chosen.provider
        site = _site_from_url(chosen.final_url or url)
    else:
        title = None
        md = ""
        txt = ""
        body_chars = 0
        links = []
        canonical = None
        lang = None
        final_url = None
        provider_used = "none"
        site = _site_from_url(url)

    raw_html_path = None  # populated by Task 30

    return build_fetch_envelope(
        status=final_status,
        url=url,
        final_url=final_url,
        provider_used=provider_used,
        content_type=content_type,
        content_gate=content_gate,
        title=title,
        body_markdown=md,
        body_text=txt,
        body_chars=body_chars,
        links=links,
        attempts=attempts,
        providers_skipped=skipped,
        reason_for_failed=reason_for_failed,
        reason_for_degraded=reason_for_degraded,
        raw_html_path=raw_html_path,
        site=site,
        canonical_url=canonical,
        lang=lang,
        detected_reason=None,
        user_agent=user_agent,
    )


import argparse


EXIT_OK = 0
EXIT_ARGS = 1
EXIT_HTTP = 2
EXIT_NETWORK = 3
EXIT_ENV = 4
EXIT_GATED = 5


STUB_PROVIDERS = {"playwright", "crawl4ai", "firecrawl", "browserless"}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fetch_url.py")
    sub = p.add_subparsers(dest="cmd")
    f = sub.add_parser("fetch")
    f.add_argument("--url", required=False)
    f.add_argument("--provider", default="auto",
                   choices=["auto", "direct", "jina", "playwright",
                            "crawl4ai", "firecrawl", "browserless"])
    f.add_argument("--format", default="markdown",
                   choices=["markdown", "text", "html"])
    f.add_argument("--json", action="store_true",
                   help="Print envelope JSON to stdout instead of summary.")
    f.add_argument("--keep-raw", action="store_true",
                   help="Save raw HTML sidecar.")
    f.add_argument("--timeout-ms", type=int, default=15000)
    f.add_argument("--min-body-chars", type=int, default=200)
    f.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    f.add_argument("--output-dir", default="~/.h2t/research")
    f.add_argument("--project", default="default")
    f.add_argument("--config", default=None)
    sub.add_parser("preflight")
    return p


def _die_args(msg: str) -> None:
    print(f"FETCH_ERROR:ARGS {msg}", file=sys.stderr)
    sys.exit(EXIT_ARGS)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd is None:
        _die_args("subcommand required (fetch | preflight)")
    if args.cmd == "fetch":
        return _run_fetch(args)
    if args.cmd == "preflight":
        return _run_preflight(args)
    _die_args(f"unknown subcommand {args.cmd}")
    return EXIT_ARGS  # unreachable


import re as _re

def _slug_from_url(url: str) -> str:
    from urllib.parse import urlparse
    p = urlparse(url)
    host = p.hostname or "url"
    path = (p.path or "").strip("/").replace("/", "-")
    raw = f"{host}-{path}" if path else host
    raw = _re.sub(r"[^a-zA-Z0-9._-]+", "-", raw).strip("-")
    return raw[:80] or "url"


def _output_paths(output_dir: Path, project: str, url: str,
                  ) -> dict[str, Path]:
    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = _slug_from_url(url)
    base = output_dir / f"{project}-fetch-{slug}-{date}"
    return {
        "partial_md": Path(str(base) + ".partial.md"),
        "sources_json": Path(str(base) + ".sources.json"),
        "raw_html": Path(str(base) + ".raw.html"),
    }


def _write_sources_json(path: Path, envelope: dict[str, Any],
                        *, project: str) -> None:
    """Write sidecar per spec §10.4: {meta, envelope, body}."""
    payload = {
        "meta": {
            "tool": "fetch_url.py",
            "tool_version": __version__,
            "project": project,
            "url": envelope["url"],
            "final_url": envelope.get("final_url"),
            "status": envelope["status"],
            "provider_used": envelope.get("provider_used"),
            "timestamp": envelope["meta"]["timestamp"],
        },
        "envelope": envelope,
        "body": {
            "markdown": envelope.get("body_markdown", ""),
            "text_excerpt": (envelope.get("body_text", "") or "")[:5000],
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def _run_fetch(args: argparse.Namespace) -> int:
    if not args.url:
        _die_args("--url is required for `fetch`")
    if args.provider in STUB_PROVIDERS:
        _die_args(
            f"provider={args.provider} not configured (stub in this version)"
        )
    cfg_path = Path(args.config).expanduser() if args.config else None
    config = load_config(cfg_path)
    paths = _output_paths(Path(args.output_dir), args.project, args.url)

    envelope = fetch_via_ladder(
        url=args.url,
        provider_choice=args.provider,
        config=config,
        user_agent=args.user_agent,
        keep_raw=args.keep_raw,
        min_body_chars=args.min_body_chars,
        output_paths=paths,
    )

    _write_sources_json(paths["sources_json"], envelope, project=args.project)

    return _emit_stdout_and_exit(envelope, args)


def _emit_stdout_and_exit(envelope: dict[str, Any],
                          args: argparse.Namespace) -> int:
    return EXIT_OK


def _run_preflight(args: argparse.Namespace) -> int:
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
