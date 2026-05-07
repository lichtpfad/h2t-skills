#!/usr/bin/env python3
"""exa_search.py — Exa API wrapper for h2t-ops:research skill.

See docs/superpowers/specs/2026-04-18-research-skill-architecture-design.md
"""
from __future__ import annotations

__version__ = "0.1.1"

import argparse
import importlib.util
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, NoReturn


def _load_h2t_secrets():
    """Dynamically import h2t_secrets from h2t-core plugin.

    Cross-plugin path resolution:
      1. relative path from this file: ../../../../../h2t-core/scripts/h2t_secrets.py
         (parents: [0]=scripts, [1]=research, [2]=skills, [3]=h2t-ops, [4]=plugins)
      2. fallback: $H2T_PLUGIN_ROOT/h2t-core/scripts/h2t_secrets.py
      3. else: fail-loud with FileNotFoundError listing tried paths.
    """
    here = Path(__file__).resolve()
    relative = here.parents[4] / "h2t-core" / "scripts" / "h2t_secrets.py"
    candidates = [relative]
    plugin_root = os.environ.get("H2T_PLUGIN_ROOT")
    if plugin_root:
        candidates.append(Path(plugin_root) / "h2t-core" / "scripts" / "h2t_secrets.py")

    for candidate in candidates:
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("h2t_secrets", candidate)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError(
        f"h2t_secrets module not found. Tried: {[str(c) for c in candidates]}. "
        f"Set H2T_PLUGIN_ROOT or restore plugins/h2t-core/scripts/h2t_secrets.py."
    )


# Cached at first main() call so tests can monkeypatch this directly.
_h2t_secrets_bootstrap = None


# Module globals
SCRIPT_DIR = Path(__file__).resolve().parent
SYSTEMPROMPTS_DIR = SCRIPT_DIR.parent / "systemprompts"

# Mode → Exa API params (spec §5.2).
# highlight_chars = default maxCharacters for contents.highlights.
MODE_CONFIG: dict[str, dict[str, Any]] = {
    "fast":       {"type": "fast", "category": None,             "highlight_chars": 2000, "num_results": 10},
    "generic":    {"type": "auto", "category": None,             "highlight_chars": 4000, "num_results": 10},
    "news":       {"type": "auto", "category": "news",           "highlight_chars": 3000, "num_results": 10},
    "academic":   {"type": "auto", "category": "research paper", "highlight_chars": 4000, "num_results": 8},
    "competitor": {"type": "auto", "category": "company",        "highlight_chars": 4000, "num_results": 10},
    "people":     {"type": "auto", "category": "people",         "highlight_chars": 3000, "num_results": 10},
    "deep":       {"type": "deep", "category": None,             "highlight_chars": 5000, "num_results": 10},
}

# Category-specific param incompatibilities (spec §5.7).
# Each listed param causes HTTP 400 from Exa when combined with that category.
CATEGORY_BLOCKS: dict[str, set[str]] = {
    "company":          {"start_date", "end_date", "include_domains", "exclude_domains"},
    "people":           {"start_date", "end_date", "include_text", "exclude_text", "exclude_domains"},
    "financial report": {"exclude_text"},
}


def die(code: int, stderr_msg: str) -> NoReturn:
    """Write structured error to stderr and exit. Spec §5.4."""
    print(stderr_msg, file=sys.stderr)
    sys.exit(code)


def validate_args(args: argparse.Namespace) -> None:
    """Fail-fast validation per spec §5.7 to prevent HTTP 400 from Exa."""
    cfg = MODE_CONFIG[args.mode]
    category = cfg["category"]

    if category in CATEGORY_BLOCKS:
        blocked = CATEGORY_BLOCKS[category]
        attempted: dict[str, Any] = {
            "start_date": args.start_date,
            "end_date": args.end_date,
            "include_domains": args.include_domains,
            "exclude_domains": args.exclude_domains,
            "include_text": args.include_text,
            "exclude_text": args.exclude_text,
        }
        conflicts = [k for k in blocked if attempted.get(k)]
        if conflicts:
            first = conflicts[0].replace("_", "-")
            die(
                1,
                f"EXA_ERROR:ARGS mode={args.mode} (category={category}) "
                f"incompatible with --{first}. "
                f"Blocked params for this category: {sorted(blocked)}. "
                f"Switch to --mode news or generic to use these filters.",
            )

    # Universal: include_text / exclude_text are single-item only (spec §5.7).
    for name in ("include_text", "exclude_text"):
        val = getattr(args, name, None)
        if isinstance(val, list) and len(val) > 1:
            die(
                1,
                f"EXA_ERROR:ARGS --{name.replace('_', '-')} supports only "
                f"single-item arrays; got {len(val)} items. Split into separate calls.",
            )


def load_system_prompt(mode: str) -> tuple[str, dict[str, Any]]:
    """Read systemprompts/{mode}.md. Returns (body_text, output_schema_or_empty).

    YAML frontmatter recognised keys: mode, exa_type, exa_category, output_schema.
    output_schema must be a single-line JSON object OR a JSON block quoted with `|`.
    Body = systemPrompt for Exa API.
    """
    path = SYSTEMPROMPTS_DIR / f"{mode}.md"
    if not path.is_file():
        die(1, f"EXA_ERROR:ARGS systemprompt file missing: {path}")
    raw = path.read_text(encoding="utf-8")
    schema: dict[str, Any] = {}
    body = raw
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end > 0:
            fm = raw[4:end]
            body = raw[end + 5:].lstrip()
            for line in fm.splitlines():
                stripped = line.strip()
                if stripped.startswith("output_schema:"):
                    val = stripped.split(":", 1)[1].strip()
                    if val.startswith("{"):
                        try:
                            schema = json.loads(val)
                        except json.JSONDecodeError:
                            pass
    return body.strip(), schema


def build_body(
    args: argparse.Namespace,
    system_prompt: str,
    output_schema: dict[str, Any],
) -> dict[str, Any]:
    """Compose Exa /search request body (spec §5.2 + §5.8)."""
    cfg = MODE_CONFIG[args.mode]
    body: dict[str, Any] = {
        "query": args.query,
        "type": cfg["type"],
        "numResults": args.num_results or cfg["num_results"],
        "contents": {"highlights": {"maxCharacters": cfg["highlight_chars"]}},
    }
    if cfg["category"]:
        body["category"] = cfg["category"]
    if system_prompt:
        body["systemPrompt"] = system_prompt
    if output_schema:
        body["outputSchema"] = output_schema
        body["structuredOutput"] = True
    if args.additional_queries:
        body["additionalQueries"] = list(args.additional_queries)
    if args.start_date:
        body["startPublishedDate"] = args.start_date
    if args.end_date:
        body["endPublishedDate"] = args.end_date
    if args.include_domains:
        body["includeDomains"] = list(args.include_domains)
    if args.exclude_domains:
        body["excludeDomains"] = list(args.exclude_domains)
    if args.include_text:
        body["includeText"] = list(args.include_text)
    if args.exclude_text:
        body["excludeText"] = list(args.exclude_text)
    if args.country:
        body["userLocation"] = args.country
    if args.full_text:
        body["contents"]["text"] = {"maxCharacters": 15000}
    if args.mode == "deep" and output_schema:
        body["contents"]["highlights"] = {"maxCharacters": 1}
    return body


EXA_API = "https://api.exa.ai"


class ExaTransientError(Exception):
    """Retryable: HTTP 5xx, 429, URLError, timeout."""

    def __init__(self, message: str, *, http_status: int | None, latency_ms: int, body: Any = None):
        super().__init__(message)
        self.http_status = http_status
        self.latency_ms = latency_ms
        self.body = body


class ExaPermanentError(Exception):
    """Non-retryable: HTTP 4xx (other than 429)."""

    def __init__(self, message: str, *, http_status: int, latency_ms: int, body: Any = None):
        super().__init__(message)
        self.http_status = http_status
        self.latency_ms = latency_ms
        self.body = body


class ExaMalformedResponseError(Exception):
    """HTTP 2xx but body is not valid JSON or missing required fields."""

    def __init__(self, message: str, *, latency_ms: int):
        super().__init__(message)
        self.latency_ms = latency_ms


JITTER_MAX_SECONDS = 0.5


def sleep_with_jitter(base_seconds: float) -> None:
    """Sleep for base_seconds + uniform(0, JITTER_MAX_SECONDS) jitter.

    Extracted as a module-level function so tests can monkeypatch it
    without touching real time.sleep, and so retry loop calls are
    homogeneous and easy to count in tests.
    """
    time.sleep(base_seconds + random.uniform(0.0, JITTER_MAX_SECONDS))


ENVELOPE_VERSION = "1"


def build_envelope(
    *,
    status: str,
    results: list[Any],
    attempts: list[dict[str, Any]],
    meta: dict[str, Any],
    total_cost_usd: float,
    reason_for_fallback: str | None = None,
    fallback_engine_used: str | None = None,
) -> dict[str, Any]:
    """Assemble the provider envelope per spec §3."""
    total_latency_ms = sum(a["latency_ms"] for a in attempts)
    return {
        "status": status,
        "primary_engine": "exa",
        "fallback_engine_used": fallback_engine_used,
        "results": results,
        "telemetry": {
            "attempts": attempts,
            "reason_for_fallback": reason_for_fallback,
            "total_latency_ms": total_latency_ms,
            "total_cost_usd": total_cost_usd,
        },
        "meta": {**meta, "envelope_version": ENVELOPE_VERSION},
    }


RETRY_BACKOFF_SECONDS: dict[str, float] = {
    "exa_5xx_retryable":   2.0,  # also covers 429
    "exa_network_timeout": 1.5,
    "exa_empty_results":   1.0,
}
RETRY_BUDGET_SECONDS = 10.0


def _classify_attempt_from_call(
    body: dict[str, Any],
    api_key: str,
) -> tuple[dict[str, Any], int | None, dict[str, Any] | None]:
    """One call_exa wrapped to produce (attempt_record, http_status, response_body).

    attempt_record always contains: engine, endpoint, http (or None), latency_ms, error.
    On success: error=None and response_body is the parsed Exa response.
    On any handled exception: response_body is None.
    """
    try:
        status, data, latency = call_exa("/search", body, api_key)
        results = data.get("results")
        if results is None:
            return (
                {"engine": "exa", "endpoint": "/search", "http": status,
                 "latency_ms": latency, "error": "exa_malformed_json"},
                None, None,
            )
        if len(results) == 0:
            return (
                {"engine": "exa", "endpoint": "/search", "http": status,
                 "latency_ms": latency, "error": "exa_empty_results"},
                status, data,
            )
        return (
            {"engine": "exa", "endpoint": "/search", "http": status,
             "latency_ms": latency, "error": None},
            status, data,
        )
    except ExaPermanentError as e:
        return (
            {"engine": "exa", "endpoint": "/search", "http": e.http_status,
             "latency_ms": e.latency_ms, "error": "exa_4xx_nonretryable"},
            None, None,
        )
    except ExaTransientError as e:
        if e.http_status is None:
            label = "exa_network_timeout"
        else:
            label = "exa_5xx_retryable"
        return (
            {"engine": "exa", "endpoint": "/search", "http": e.http_status,
             "latency_ms": e.latency_ms, "error": label},
            None, None,
        )
    except ExaMalformedResponseError as e:
        return (
            {"engine": "exa", "endpoint": "/search", "http": None,
             "latency_ms": e.latency_ms, "error": "exa_malformed_json"},
            None, None,
        )


def _exit_code_for_failure(error_label: str) -> int:
    if error_label == "exa_network_timeout":
        return 3
    return 2


def search_with_retry(
    *,
    body: dict[str, Any],
    api_key: str,
    retry: bool,
    mode: str = "generic",
) -> tuple[dict[str, Any], int]:
    """Run /search with optional 1-retry loop. Returns (envelope, exit_code).

    Retryable error labels: exa_5xx_retryable, exa_network_timeout, exa_empty_results.
    Non-retryable: exa_4xx_nonretryable, exa_malformed_json.
    Hard cap: cumulative sleep <= RETRY_BUDGET_SECONDS.
    """
    attempts: list[dict[str, Any]] = []
    last_data: dict[str, Any] | None = None
    cumulative_sleep = 0.0
    max_attempts = 2 if retry else 1

    for i in range(max_attempts):
        attempt, _status, data = _classify_attempt_from_call(body, api_key)
        attempts.append(attempt)
        if data is not None:
            last_data = data
        error = attempt["error"]

        # Success on this attempt
        if error is None:
            break
        # Non-retryable
        if error in ("exa_4xx_nonretryable", "exa_malformed_json"):
            break
        # No more attempts left
        if i == max_attempts - 1:
            break
        # Backoff before next attempt
        backoff = RETRY_BACKOFF_SECONDS.get(error, 1.0)
        if cumulative_sleep + backoff > RETRY_BUDGET_SECONDS:
            print(
                f"EXA_WARN:RETRY_BUDGET_EXHAUSTED skipped backoff={backoff}s "
                f"after cumulative={cumulative_sleep}s",
                file=sys.stderr,
            )
            break
        sleep_with_jitter(backoff)
        cumulative_sleep += backoff

    # Determine final status + exit
    last_error = attempts[-1]["error"]
    if last_error is None:
        status_label = "OK"
        exit_code = 0
        results = (last_data or {}).get("results", [])
        cost = float((last_data or {}).get("costDollars", {}).get("total", 0.0))
        reason = None
    elif last_error == "exa_empty_results":
        status_label = "DEGRADED"
        exit_code = 0
        results = []
        cost = float((last_data or {}).get("costDollars", {}).get("total", 0.0))
        reason = "exa_empty_results"
    else:
        status_label = "FAILED"
        exit_code = _exit_code_for_failure(last_error)
        results = []
        cost = 0.0
        reason = None

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    envelope = build_envelope(
        status=status_label,
        results=results,
        attempts=attempts,
        meta={
            "query": body.get("query", ""),
            "mode": mode,
            "num_results_requested": body.get("numResults", 0),
            "num_results_returned": len(results),
            "timestamp": timestamp,
        },
        total_cost_usd=cost,
        reason_for_fallback=reason,
    )
    return envelope, exit_code


def call_exa(
    endpoint: str,
    body: dict[str, Any],
    api_key: str,
    timeout: int = 60,
) -> tuple[int, dict[str, Any], int]:
    """POST to Exa. Returns (http_status, response_json, latency_ms) on 2xx with valid JSON.

    Raises:
      - ExaTransientError on HTTP 5xx, 429, URLError, timeout (retryable upstream).
      - ExaPermanentError on HTTP 4xx other than 429 (caller decides exit).
      - ExaMalformedResponseError on HTTP 2xx with non-JSON body.

    No die() inside this function — all exit decisions live at CLI top level.
    """
    req = urllib.request.Request(
        f"{EXA_API}{endpoint}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"exa_search.py/{__version__} (h2t-ops:research)",
        },
        method="POST",
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = int((time.monotonic() - start) * 1000)
            raw = resp.read().decode("utf-8")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ExaMalformedResponseError(
                    f"non-JSON body from Exa (first 120 chars): {raw[:120]!r}",
                    latency_ms=latency,
                ) from e
            return resp.status, data, latency
    except urllib.error.HTTPError as e:
        latency = int((time.monotonic() - start) * 1000)
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = {"error": "non_json_error_response"}
        if e.code == 429 or 500 <= e.code < 600:
            raise ExaTransientError(
                f"http {e.code}", http_status=e.code, latency_ms=latency, body=err_body,
            ) from e
        raise ExaPermanentError(
            f"http {e.code}", http_status=e.code, latency_ms=latency, body=err_body,
        ) from e
    except urllib.error.URLError as e:
        latency = int((time.monotonic() - start) * 1000)
        raise ExaTransientError(
            f"{e.reason}", http_status=None, latency_ms=latency,
        ) from e


def preflight() -> None:
    """Step 0: env + connectivity probe (spec §4 Step 0).

    Any HTTP response from api.exa.ai (even 4xx) means the server is reachable;
    only URLError (DNS, TCP, timeout) counts as a network failure. Auth errors
    are for the actual search call to surface, not preflight.
    """
    if not os.environ.get("EXA_API_KEY"):
        die(4, "EXA_ERROR:ENV EXA_API_KEY missing; obtain at https://dashboard.exa.ai/api-keys")
    req = urllib.request.Request(
        f"{EXA_API}/",
        method="GET",
        headers={"User-Agent": f"exa_search.py/{__version__} (h2t-ops:research)"},
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError:
        # Server responded with 4xx/5xx — connectivity is fine, auth-only issue.
        pass
    except urllib.error.URLError as e:
        die(4, f"EXA_ERROR:NETWORK cannot reach {EXA_API}: {e.reason}")
    print("OK")


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 50) -> str:
    """Lowercase, collapse non-alnum → hyphen, trim, cap length."""
    s = _SLUG_RE.sub("-", text.lower()).strip("-")
    return s[:max_len]


def output_paths(
    output_dir: Path, project: str, topic: str, date: str
) -> dict[str, Path]:
    """Per spec §8: persistence filenames."""
    output_dir.mkdir(parents=True, exist_ok=True)
    base = f"{slugify(project)}-{slugify(topic)}-{date}"
    return {
        "partial_md": output_dir / f"{base}.partial.md",
        "final_md": output_dir / f"{base}.md",
        "sources_json": output_dir / f"{base}.sources.json",
    }


def render_stdout_summary(
    data: dict[str, Any],
    *,
    query: str,
    mode: str,
    latency_ms: int,
    partial_path: Path,
    json_path: Path,
) -> None:
    """Compact markdown summary printed to stdout (spec §5.5)."""
    results = data.get("results", [])
    cost = data.get("costDollars", {}).get("total", 0)
    print(f"## Exa Search: {query!r}")
    print(f"**Mode:** {mode} | **Results:** {len(results)} | **Cost:** ${cost:.3f} | **Latency:** {latency_ms}ms")
    print()
    for i, r in enumerate(results, 1):
        title = r.get("title", "(no title)")
        url = r.get("url", "")
        highlights = r.get("highlights") or []
        snippet = highlights[0][:260] if highlights else ""
        print(f"{i}. [{title}]({url})")
        if snippet:
            print(f"   {snippet}")
    print()
    print(f"Saved: {partial_path.name}")
    print(f"JSON:  {json_path.name}")


def write_sources_json(
    path: Path,
    meta: dict[str, Any],
    response: dict[str, Any],
) -> None:
    """Raw Exa API response + metadata sidecar."""
    path.write_text(
        json.dumps({"meta": meta, "response": response}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_partial_md(
    path: Path,
    *,
    meta: dict[str, Any],
    telemetry_rows: list[dict[str, Any]],
) -> None:
    """Per spec §8.3: script writes technical Meta + Telemetry; agent finishes to final .md."""
    total_cost = sum(r["cost_usd"] for r in telemetry_rows)
    total_latency = sum(r["latency_ms"] for r in telemetry_rows)
    total_results = sum(r["results"] for r in telemetry_rows)
    errors = sum(1 for r in telemetry_rows if r["http"] >= 400)
    exa_calls = sum(1 for r in telemetry_rows if "exa_search.py" in r["tool"])
    total_calls = len(telemetry_rows)

    lines: list[str] = []
    lines.append(f"# Research: {meta['query']}\n")
    lines.append("## Meta\n")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| **Date** | {meta['date']} |")
    lines.append(f"| **Project** | {meta['project']} |")
    lines.append(f"| **Query** | {meta['query']} |")
    lines.append(f"| **Mode** | {meta['mode']} |")
    lines.append(f"| **Depth** | {meta['depth']} |")
    lines.append(f"| **Engine** | Exa (via scripts/exa_search.py) |")
    lines.append(f"| **Status** | {meta['status']} |")
    lines.append(f"| **Cache hit** | {meta['cache_hit']} |\n")
    lines.append("## Telemetry\n")
    lines.append("| # | Tool | Args | HTTP | Latency | Cost | Results |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in telemetry_rows:
        lines.append(
            f"| {r['num']} | `{r['tool']}` | `{r['args']}` | "
            f"{r['http']} | {r['latency_ms']}ms | ${r['cost_usd']:.3f} | {r['results']} |"
        )
    lines.append(
        f"| **Totals** | | | **{errors} errors** | "
        f"**{total_latency}ms** | **${total_cost:.3f}** | **{total_results} items** |\n"
    )
    lines.append(
        f"> **Integrity check:** {exa_calls}/{total_calls} calls used Exa API. "
        f"0 fallbacks to WebSearch.\n"
    )
    lines.append("## Sources\n\n*(agent fills in from .sources.json)*\n")
    lines.append("## Key Findings\n\n*(agent fills in — requires URL + verbatim quote + confidence per spec §4 Step 5)*\n")
    lines.append("## Grounding Notes\n\n*(agent fills in)*\n")
    lines.append("## Limitations\n\n*(agent fills in)*\n")
    lines.append("## Follow-up Suggestions\n\n*(agent fills in)*\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def post_telemetry(event: dict[str, Any], buffer_path: Path) -> str:
    """Fail-graceful telemetry (spec §9.2).
    Returns one of: 'sent', 'buffered', 'awaiting_endpoint', 'disabled'.

    Contract:
      - H2T_EVALS_DISABLE=1            -> 'disabled' (explicit opt-out)
      - H2T_EVALS_URL unset            -> 'awaiting_endpoint' (MVP default)
      - URL set, HTTP 2xx              -> 'sent'
      - URL set, URLError/HTTPError    -> 'buffered' (local JSONL append)
    """
    if os.environ.get("H2T_EVALS_DISABLE") == "1":
        return "disabled"
    evals_url = os.environ.get("H2T_EVALS_URL")
    if not evals_url:
        return "awaiting_endpoint"
    token = os.environ.get("H2T_EVALS_TOKEN", "")
    req = urllib.request.Request(
        f"{evals_url.rstrip('/')}/api/telemetry/research",
        data=json.dumps(event).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}" if token else "",
            "User-Agent": f"exa_search.py/{__version__} (h2t-ops:research)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if 200 <= resp.status < 300:
                return "sent"
    except urllib.error.URLError:
        pass
    except urllib.error.HTTPError:
        pass
    # Fallback: buffer locally
    buffer_path.parent.mkdir(parents=True, exist_ok=True)
    with buffer_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    return "buffered"


MODES = list(MODE_CONFIG.keys())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="exa_search",
        description="Exa API wrapper (preflight / search / crawl).",
    )
    parser.add_argument("--version", action="version", version=f"exa_search {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=False)

    sub.add_parser("preflight", help="Check env + connectivity.")

    s = sub.add_parser("search", help="Run Exa /search.")
    s.add_argument("--query", required=True)
    s.add_argument("--mode", choices=MODES, default="generic")
    s.add_argument("--depth", choices=["shallow", "standard", "deep"], default="standard")
    s.add_argument("--num-results", type=int, default=None, dest="num_results")
    s.add_argument("--additional-queries", default=None,
                   help="Comma-separated list (2-3 recommended for mode=deep).",
                   dest="additional_queries_raw")
    s.add_argument("--start-date", default=None, dest="start_date")
    s.add_argument("--end-date", default=None, dest="end_date")
    s.add_argument("--include-domains", default=None, dest="include_domains_raw")
    s.add_argument("--exclude-domains", default=None, dest="exclude_domains_raw")
    s.add_argument("--include-text", default=None, dest="include_text_raw")
    s.add_argument("--exclude-text", default=None, dest="exclude_text_raw")
    s.add_argument("--country", default=None)
    s.add_argument("--full-text", action="store_true", dest="full_text")
    s.add_argument("--output-dir", default=str(Path.home() / ".h2t" / "research"),
                   dest="output_dir")
    s.add_argument("--project", default="default")
    s.add_argument("--envelope", action="store_true",
                   help="Print JSON envelope to stdout instead of markdown summary.")
    s.add_argument("--no-retry", action="store_true", dest="no_retry",
                   help="Disable retry policy (for tests/debug).")

    c = sub.add_parser("crawl", help="Run Exa /contents on one URL.")
    c.add_argument("--url", required=True)
    c.add_argument("--output-dir", default=str(Path.home() / ".h2t" / "research"),
                   dest="output_dir")
    c.add_argument("--project", default="default")

    return parser


def _split_csv(raw: str | None) -> list[str] | None:
    return [x.strip() for x in raw.split(",") if x.strip()] if raw else None


def main(argv: list[str] | None = None) -> int:
    # Windows stdout defaults to cp1252; Exa highlights may contain emoji/CJK.
    # Reconfigure to UTF-8 with lossy fallback so rendering never crashes.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    # Load secrets from ~/.dor/secrets/secrets.env if available.
    # Shell-exported env vars take precedence (non-overriding merge).
    global _h2t_secrets_bootstrap
    if _h2t_secrets_bootstrap is None:
        try:
            _h2t_secrets_bootstrap = _load_h2t_secrets().bootstrap
        except FileNotFoundError as e:
            die(4, f"EXA_ERROR:ENV {e}")
    try:
        _h2t_secrets_bootstrap()
    except FileNotFoundError as e:
        die(4, f"EXA_ERROR:ENV {e}")
    except (ValueError, OSError) as e:
        die(4, f"EXA_ERROR:ENV malformed secrets.env: {e}")

    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "preflight":
        preflight()
        return 0
    if args.cmd == "search":
        args.additional_queries = _split_csv(args.additional_queries_raw)
        args.include_domains = _split_csv(args.include_domains_raw)
        args.exclude_domains = _split_csv(args.exclude_domains_raw)
        args.include_text = _split_csv(args.include_text_raw)
        args.exclude_text = _split_csv(args.exclude_text_raw)
        return _run_search(args)
    if args.cmd == "crawl":
        return _run_crawl(args)
    parser.print_help()
    return 0


def _emit_failed_stderr(envelope: dict[str, Any]) -> str:
    """Compose the EXA_ERROR:* message for stderr from envelope.

    Returns the message; caller prints. Pure for testability.
    """
    last = envelope["telemetry"]["attempts"][-1]
    error = last["error"]
    if error == "exa_4xx_nonretryable":
        return f"EXA_ERROR:API http={last['http']}"
    if error == "exa_5xx_retryable":
        return f"EXA_ERROR:API http={last['http']} (after retries)"
    if error == "exa_network_timeout":
        return f"EXA_ERROR:NETWORK after {last['latency_ms']}ms (after retries)"
    if error == "exa_malformed_json":
        return "EXA_ERROR:MALFORMED non-JSON or missing 'results' field"
    return f"EXA_ERROR:UNKNOWN {error}"


def _run_search(args: argparse.Namespace) -> int:
    validate_args(args)
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        die(4, "EXA_ERROR:ENV EXA_API_KEY missing")
    system_prompt, schema = load_system_prompt(args.mode)
    body = build_body(args, system_prompt, schema)

    envelope, exit_code = search_with_retry(
        body=body, api_key=api_key, retry=not args.no_retry, mode=args.mode,
    )

    # Persist sidecar (always — OK, DEGRADED, FAILED all get .sources.json).
    out_dir = Path(args.output_dir)
    paths = output_paths(out_dir, args.project, args.query,
                         datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    response_for_writers = {
        "results": envelope["results"],
        "costDollars": {"total": envelope["telemetry"]["total_cost_usd"]},
    }
    meta = {
        "query": args.query,
        "mode": args.mode,
        "depth": args.depth,
        "project": args.project,
        "date": envelope["meta"]["timestamp"],
        "status": ("completed" if envelope["status"] == "OK"
                   else ("partial" if envelope["status"] == "DEGRADED" else "failed")),
        "cache_hit": False,
        "envelope": envelope,
    }
    write_sources_json(paths["sources_json"], meta, response_for_writers)

    # .partial.md only for OK/DEGRADED — FAILED has no synthesizable content.
    if envelope["status"] != "FAILED":
        cat = MODE_CONFIG[args.mode]["category"]
        tel_args = f"type={MODE_CONFIG[args.mode]['type']}"
        if cat:
            tel_args += f",category={cat}"
        tel_args += f",numResults={body['numResults']}"
        telemetry_rows = [{
            "num": i + 1,
            "tool": "exa_search.py search",
            "args": tel_args,
            "http": a["http"] or 0,
            "latency_ms": a["latency_ms"],
            "cost_usd": (envelope["telemetry"]["total_cost_usd"] if a["error"] is None else 0.0),
            "results": (len(envelope["results"]) if a["error"] is None else 0),
        } for i, a in enumerate(envelope["telemetry"]["attempts"])]
        write_partial_md(paths["partial_md"], meta=meta, telemetry_rows=telemetry_rows)

    # FAILED: always emit EXA_ERROR:* to stderr (back-compat fail-loud).
    if envelope["status"] == "FAILED":
        print(_emit_failed_stderr(envelope), file=sys.stderr)

    # Stdout policy:
    #   --envelope: print JSON envelope (OK, DEGRADED, FAILED — all of them).
    #   default + OK/DEGRADED: markdown summary.
    #   default + FAILED: nothing on stdout (stderr already has EXA_ERROR:*).
    if args.envelope:
        print(json.dumps(envelope, indent=2, ensure_ascii=False))
    elif envelope["status"] != "FAILED":
        render_stdout_summary(
            response_for_writers,
            query=args.query,
            mode=args.mode,
            latency_ms=envelope["telemetry"]["total_latency_ms"],
            partial_path=paths["partial_md"],
            json_path=paths["sources_json"],
        )

    # Telemetry (fire-and-forget, unchanged shape).
    post_telemetry(
        event={
            "session_id": os.environ.get("H2T_SESSION_ID", ""),
            "engine": "exa",
            "endpoint": "/search",
            "mode": args.mode,
            "exa_type": body["type"],
            "exa_category": body.get("category"),
            "query_hash": sha256(args.query.encode("utf-8")).hexdigest()[:16],
            "num_results_requested": body["numResults"],
            "num_results_returned": len(envelope["results"]),
            "cost_usd": envelope["telemetry"]["total_cost_usd"],
            "latency_ms": envelope["telemetry"]["total_latency_ms"],
            "http_status": envelope["telemetry"]["attempts"][-1]["http"] or 0,
            "exit_code": exit_code,
            "timestamp": envelope["meta"]["timestamp"],
        },
        buffer_path=out_dir / ".pending_telemetry.jsonl",
    )

    if exit_code != 0:
        sys.exit(exit_code)
    return exit_code


def _run_crawl(args: argparse.Namespace) -> int:
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        die(4, "EXA_ERROR:ENV EXA_API_KEY missing")
    body = {"urls": [args.url], "text": {"maxCharacters": 15000}}
    try:
        status, data, latency_ms = call_exa("/contents", body, api_key)
    except ExaPermanentError as e:
        die(2, f"EXA_ERROR:API http={e.http_status} body={json.dumps(e.body)[:300]!r}")
    except ExaTransientError as e:
        if e.http_status is None:
            die(3, f"EXA_ERROR:NETWORK {e} after {e.latency_ms}ms")
        die(2, f"EXA_ERROR:API http={e.http_status}")
    except ExaMalformedResponseError as e:
        die(2, f"EXA_ERROR:MALFORMED {e}")

    out_dir = Path(args.output_dir)
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    topic = f"crawl-{args.url}"
    paths = output_paths(out_dir, args.project, topic, date)

    cost = float(data.get("costDollars", {}).get("total", 0))
    n_results = len(data.get("results", []))
    status_label = "OK" if n_results > 0 else "DEGRADED"
    envelope = build_envelope(
        status=status_label,
        results=data.get("results", []),
        attempts=[{"engine": "exa", "endpoint": "/contents", "http": status,
                   "latency_ms": latency_ms,
                   "error": None if n_results > 0 else "exa_empty_results"}],
        meta={
            "query": f"crawl({args.url})", "mode": "crawl",
            "num_results_requested": 1, "num_results_returned": n_results,
            "timestamp": timestamp,
        },
        total_cost_usd=cost,
        reason_for_fallback=None if n_results > 0 else "exa_empty_results",
    )

    meta = {
        "query": f"crawl({args.url})",
        "mode": "crawl",
        "depth": "n/a",
        "project": args.project,
        "date": timestamp,
        "status": "completed" if n_results > 0 else "partial",
        "cache_hit": False,
        "envelope": envelope,
    }
    write_sources_json(paths["sources_json"], meta, data)
    render_stdout_summary(
        data,
        query=f"crawl({args.url})",
        mode="crawl",
        latency_ms=latency_ms,
        partial_path=paths["partial_md"],
        json_path=paths["sources_json"],
    )
    post_telemetry(
        event={
            "session_id": os.environ.get("H2T_SESSION_ID", ""),
            "engine": "exa",
            "endpoint": "/contents",
            "mode": "crawl",
            "cost_usd": cost,
            "latency_ms": latency_ms,
            "http_status": status,
            "exit_code": 0,
            "timestamp": timestamp,
        },
        buffer_path=out_dir / ".pending_telemetry.jsonl",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
