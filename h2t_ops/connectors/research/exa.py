"""Exa provider core for h2t_ops research connectors."""
from __future__ import annotations

__version__ = "0.1.2"

import json
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from h2t_ops.core.errors import AuthError, ConfigError, NetworkError, ProviderError, UsageError


SCRIPT_DIR = Path(__file__).resolve().parent
SYSTEMPROMPTS_DIR = SCRIPT_DIR / "systemprompts"

MODE_CONFIG: dict[str, dict[str, Any]] = {
    "fast": {"type": "fast", "category": None, "highlight_chars": 2000, "num_results": 10},
    "generic": {"type": "auto", "category": None, "highlight_chars": 4000, "num_results": 10},
    "news": {"type": "auto", "category": "news", "highlight_chars": 3000, "num_results": 10},
    "academic": {
        "type": "auto",
        "category": "research paper",
        "highlight_chars": 4000,
        "num_results": 8,
    },
    "competitor": {
        "type": "auto",
        "category": "company",
        "highlight_chars": 4000,
        "num_results": 10,
    },
    "people": {"type": "auto", "category": "people", "highlight_chars": 3000, "num_results": 10},
    "deep": {"type": "deep", "category": None, "highlight_chars": 5000, "num_results": 10},
}

CATEGORY_BLOCKS: dict[str, set[str]] = {
    "company": {"start_date", "end_date", "include_domains", "exclude_domains"},
    "people": {"start_date", "end_date", "include_text", "exclude_text", "exclude_domains"},
    "financial report": {"exclude_text"},
}

MODES = list(MODE_CONFIG.keys())
_EXA_API = "https://api.exa.ai"

RESEARCH_MODELS = ("exa-research-fast", "exa-research", "exa-research-pro")
RESEARCH_DEFAULT_MODEL = "exa-research-fast"
RESEARCH_POLL_INTERVAL_SECONDS = 2.0
RESEARCH_TIMEOUT_SECONDS = 180.0
RESEARCH_POLL_BACKOFF_FACTOR = 1.5
RESEARCH_POLL_INTERVAL_CAP_SECONDS = 30.0


def validate_args(args: Any) -> None:
    """Fail-fast validation to prevent known Exa HTTP 400 combinations."""
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
        conflicts = [key for key in blocked if attempted.get(key)]
        if conflicts:
            first = conflicts[0].replace("_", "-")
            raise UsageError(
                f"EXA_ERROR:ARGS mode={args.mode} (category={category}) "
                f"incompatible with --{first}. "
                f"Blocked params for this category: {sorted(blocked)}. "
                f"Switch to --mode news or generic to use these filters."
            )

    for name in ("include_text", "exclude_text"):
        val = getattr(args, name, None)
        if isinstance(val, list) and len(val) > 1:
            raise UsageError(
                f"EXA_ERROR:ARGS --{name.replace('_', '-')} supports only "
                f"single-item arrays; got {len(val)} items. Split into separate calls."
            )


class ExaTransientError(Exception):
    """Retryable: HTTP 5xx, 429, URLError, timeout."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None,
        latency_ms: int,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.latency_ms = latency_ms
        self.body = body


class ExaPermanentError(Exception):
    """Non-retryable: HTTP 4xx other than 429."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int,
        latency_ms: int,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.latency_ms = latency_ms
        self.body = body


class ExaMalformedResponseError(Exception):
    """HTTP 2xx but body is not valid JSON or is missing required fields."""

    def __init__(self, message: str, *, latency_ms: int) -> None:
        super().__init__(message)
        self.latency_ms = latency_ms


_JITTER_MAX_SECONDS = 0.5


def sleep_with_jitter(base_seconds: float) -> None:
    """Sleep for base_seconds plus bounded random jitter."""
    time.sleep(base_seconds + random.uniform(0.0, _JITTER_MAX_SECONDS))


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
    """Assemble the provider envelope."""
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
    "exa_5xx_retryable": 2.0,
    "exa_network_timeout": 1.5,
    "exa_empty_results": 1.0,
}
RETRY_BUDGET_SECONDS = 10.0


def _classify_attempt_from_call(
    body: dict[str, Any],
    api_key: str,
) -> tuple[dict[str, Any], int | None, dict[str, Any] | None]:
    """Run one Exa call and normalize success/errors into an attempt record."""
    try:
        status, data, latency = call_exa("/search", body, api_key)
        if not isinstance(data, dict):
            return (
                {
                    "engine": "exa",
                    "endpoint": "/search",
                    "http": status,
                    "latency_ms": latency,
                    "error": "exa_malformed_json",
                },
                None,
                None,
            )
        results = data.get("results")
        if not isinstance(results, list):
            return (
                {
                    "engine": "exa",
                    "endpoint": "/search",
                    "http": status,
                    "latency_ms": latency,
                    "error": "exa_malformed_json",
                },
                None,
                None,
            )
        if len(results) == 0:
            return (
                {
                    "engine": "exa",
                    "endpoint": "/search",
                    "http": status,
                    "latency_ms": latency,
                    "error": "exa_empty_results",
                },
                status,
                data,
            )
        return (
            {
                "engine": "exa",
                "endpoint": "/search",
                "http": status,
                "latency_ms": latency,
                "error": None,
            },
            status,
            data,
        )
    except ExaPermanentError as exc:
        label = "exa_auth_error" if exc.http_status in {401, 403} else "exa_4xx_nonretryable"
        return (
            {
                "engine": "exa",
                "endpoint": "/search",
                "http": exc.http_status,
                "latency_ms": exc.latency_ms,
                "error": label,
            },
            None,
            None,
        )
    except ExaTransientError as exc:
        label = "exa_network_timeout" if exc.http_status is None else "exa_5xx_retryable"
        return (
            {
                "engine": "exa",
                "endpoint": "/search",
                "http": exc.http_status,
                "latency_ms": exc.latency_ms,
                "error": label,
            },
            None,
            None,
        )
    except ExaMalformedResponseError as exc:
        return (
            {
                "engine": "exa",
                "endpoint": "/search",
                "http": None,
                "latency_ms": exc.latency_ms,
                "error": "exa_malformed_json",
            },
            None,
            None,
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
    """Run /search with optional one-retry policy. Returns (envelope, exit_code)."""
    attempts: list[dict[str, Any]] = []
    last_data: dict[str, Any] | None = None
    cumulative_sleep = 0.0
    max_attempts = 2 if retry else 1

    for index in range(max_attempts):
        attempt, _status, data = _classify_attempt_from_call(body, api_key)
        attempts.append(attempt)
        if data is not None:
            last_data = data
        error = attempt["error"]

        if error is None:
            break
        if error in ("exa_auth_error", "exa_4xx_nonretryable", "exa_malformed_json"):
            break
        if index == max_attempts - 1:
            break

        backoff = RETRY_BACKOFF_SECONDS.get(error, 1.0)
        if cumulative_sleep + backoff > RETRY_BUDGET_SECONDS:
            break
        sleep_with_jitter(backoff)
        cumulative_sleep += backoff

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
    method: str = "POST",
) -> tuple[int, dict[str, Any], int]:
    """POST/GET to Exa and return (http_status, response_json, latency_ms)."""
    data = None if method == "GET" else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{_EXA_API}{endpoint}",
        data=data,
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"exa_search.py/{__version__} (h2t-ops:research)",
        },
        method=method,
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = int((time.monotonic() - start) * 1000)
            raw = resp.read().decode("utf-8")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ExaMalformedResponseError(
                    f"non-JSON body from Exa (first 120 chars): {raw[:120]!r}",
                    latency_ms=latency,
                ) from exc
            if not isinstance(data, dict):
                raise ExaMalformedResponseError(
                    f"non-object JSON body from Exa: {type(data).__name__}",
                    latency_ms=latency,
                )
            return resp.status, data, latency
    except urllib.error.HTTPError as exc:
        latency = int((time.monotonic() - start) * 1000)
        try:
            err_body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            err_body = {"error": "non_json_error_response"}
        if exc.code == 429 or 500 <= exc.code < 600:
            raise ExaTransientError(
                f"http {exc.code}",
                http_status=exc.code,
                latency_ms=latency,
                body=err_body,
            ) from exc
        raise ExaPermanentError(
            f"http {exc.code}",
            http_status=exc.code,
            latency_ms=latency,
            body=err_body,
        ) from exc
    except urllib.error.URLError as exc:
        latency = int((time.monotonic() - start) * 1000)
        raise ExaTransientError(
            f"{exc.reason}",
            http_status=None,
            latency_ms=latency,
        ) from exc


def preflight(api_key: str) -> None:
    """Validate Exa API credentials with a tiny authenticated search."""
    body = {
        "query": "h2t research connector preflight",
        "type": "fast",
        "numResults": 1,
        "contents": {"highlights": {"maxCharacters": 1}},
    }
    try:
        call_exa("/search", body, api_key, timeout=10)
    except ExaPermanentError as exc:
        if exc.http_status in {401, 403}:
            raise AuthError(
                f"EXA_ERROR:AUTH preflight failed: http {exc.http_status}",
                details={"http_status": exc.http_status},
            ) from exc
        raise ProviderError(
            f"EXA_ERROR:PROVIDER preflight failed: http {exc.http_status}",
            details={"http_status": exc.http_status},
        ) from exc
    except ExaTransientError as exc:
        if exc.http_status is None:
            raise NetworkError(f"EXA_ERROR:NETWORK cannot reach {_EXA_API}: {exc}") from exc
        raise ProviderError(
            f"EXA_ERROR:PROVIDER preflight failed: http {exc.http_status}",
            details={"http_status": exc.http_status},
        ) from exc
    except ExaMalformedResponseError as exc:
        raise ProviderError(
            f"EXA_ERROR:PROVIDER malformed preflight response: {exc}",
            details={"latency_ms": exc.latency_ms},
        ) from exc


def load_system_prompt(mode: str) -> tuple[str, dict[str, Any]]:
    """Read systemprompts/{mode}.md and return (body_text, output_schema_or_empty)."""
    path = SYSTEMPROMPTS_DIR / f"{mode}.md"
    if not path.is_file():
        raise ConfigError(f"EXA_ERROR:ARGS systemprompt file missing: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"EXA_ERROR:CONFIG cannot read systemprompt file: {path}") from exc

    schema: dict[str, Any] = {}
    body = raw
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end < 0:
            raise ConfigError(f"EXA_ERROR:CONFIG malformed frontmatter in systemprompt: {path}")
        frontmatter = raw[4:end]
        body = raw[end + 5 :].lstrip()
        for line in frontmatter.splitlines():
            stripped = line.strip()
            if stripped.startswith("output_schema:"):
                val = stripped.split(":", 1)[1].strip()
                if val.startswith("{"):
                    try:
                        schema = json.loads(val)
                    except json.JSONDecodeError as exc:
                        raise ConfigError(
                            f"EXA_ERROR:CONFIG malformed output_schema JSON in systemprompt: {path}"
                        ) from exc
    return body.strip(), schema


def build_body(
    args: Any,
    system_prompt: str,
    output_schema: dict[str, Any],
) -> dict[str, Any]:
    """Compose Exa /search request body."""
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


def _split_csv(raw: str | None) -> list[str] | None:
    return [x.strip() for x in raw.split(",") if x.strip()] if raw else None


def find_similar(
    url: str,
    *,
    api_key: str,
    num_results: int = 10,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> tuple[dict[str, Any], int]:
    """Call Exa /findSimilar. Returns (envelope, exit_code)."""
    body: dict[str, Any] = {
        "url": url,
        "numResults": num_results,
        "contents": {"highlights": {"maxCharacters": 4000}},
    }
    if include_domains:
        body["includeDomains"] = include_domains
    if exclude_domains:
        body["excludeDomains"] = exclude_domains

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        http_status, data, latency = call_exa("/findSimilar", body, api_key)
    except ExaPermanentError as exc:
        exit_code = 4 if exc.http_status in {401, 403} else 1
        return {
            "status": "FAILED",
            "primary_engine": "exa",
            "results": [],
            "telemetry": {
                "attempts": [{"engine": "exa", "endpoint": "/findSimilar", "http": exc.http_status, "latency_ms": exc.latency_ms, "error": "exa_auth_error" if exc.http_status in {401, 403} else "exa_4xx"}],
                "total_latency_ms": exc.latency_ms,
                "total_cost_usd": 0.0,
            },
            "meta": {"source_url": url, "envelope_version": ENVELOPE_VERSION, "timestamp": timestamp},
        }, exit_code
    except (ExaTransientError, ExaMalformedResponseError) as exc:
        latency_ms = getattr(exc, "latency_ms", 0)
        return {
            "status": "FAILED",
            "primary_engine": "exa",
            "results": [],
            "telemetry": {
                "attempts": [{"engine": "exa", "endpoint": "/findSimilar", "http": getattr(exc, "http_status", None), "latency_ms": latency_ms, "error": "exa_network"}],
                "total_latency_ms": latency_ms,
                "total_cost_usd": 0.0,
            },
            "meta": {"source_url": url, "envelope_version": ENVELOPE_VERSION, "timestamp": timestamp},
        }, 6

    results = data.get("results", [])
    cost = float((data.get("costDollars") or {}).get("total", 0.0))
    status = "OK" if results else "DEGRADED"
    return {
        "status": status,
        "primary_engine": "exa",
        "results": results,
        "telemetry": {
            "attempts": [{"engine": "exa", "endpoint": "/findSimilar", "http": http_status, "latency_ms": latency, "error": None}],
            "total_latency_ms": latency,
            "total_cost_usd": cost,
        },
        "meta": {
            "source_url": url,
            "num_results_requested": num_results,
            "num_results_returned": len(results),
            "envelope_version": ENVELOPE_VERSION,
            "timestamp": timestamp,
        },
    }, 0


def answer(
    query: str,
    *,
    api_key: str,
) -> tuple[dict[str, Any], int]:
    """Call Exa /answer. Returns (envelope, exit_code)."""
    body: dict[str, Any] = {"query": query, "text": True}
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        http_status, data, latency = call_exa("/answer", body, api_key)
    except ExaPermanentError as exc:
        exit_code = 4 if exc.http_status in {401, 403} else 1
        return {
            "status": "FAILED",
            "primary_engine": "exa",
            "answer_text": "",
            "citations": [],
            "telemetry": {"attempts": [{"engine": "exa", "endpoint": "/answer", "http": exc.http_status, "latency_ms": exc.latency_ms, "error": "exa_auth_error" if exc.http_status in {401, 403} else "exa_4xx"}], "total_latency_ms": exc.latency_ms, "total_cost_usd": 0.0},
            "meta": {"query": query, "envelope_version": ENVELOPE_VERSION, "timestamp": timestamp},
        }, exit_code
    except (ExaTransientError, ExaMalformedResponseError) as exc:
        latency_ms = getattr(exc, "latency_ms", 0)
        return {
            "status": "FAILED",
            "primary_engine": "exa",
            "answer_text": "",
            "citations": [],
            "telemetry": {"attempts": [{"engine": "exa", "endpoint": "/answer", "http": getattr(exc, "http_status", None), "latency_ms": latency_ms, "error": "exa_network"}], "total_latency_ms": latency_ms, "total_cost_usd": 0.0},
            "meta": {"query": query, "envelope_version": ENVELOPE_VERSION, "timestamp": timestamp},
        }, 6

    answer_text = data.get("answer", "")
    citations = data.get("citations", [])
    return {
        "status": "OK",
        "primary_engine": "exa",
        "answer_text": answer_text,
        "citations": citations,
        "telemetry": {
            "attempts": [{"engine": "exa", "endpoint": "/answer", "http": http_status, "latency_ms": latency, "error": None}],
            "total_latency_ms": latency,
            "total_cost_usd": 0.0,
        },
        "meta": {
            "query": query,
            "envelope_version": ENVELOPE_VERSION,
            "timestamp": timestamp,
        },
    }, 0


def create_research(
    instructions: str,
    *,
    model: str,
    output_schema: dict[str, Any] | None,
    api_key: str,
) -> dict[str, Any]:
    """POST /research/v1 to create an async research task."""
    body: dict[str, Any] = {"instructions": instructions, "model": model}
    if output_schema:
        body["outputSchema"] = output_schema
    _status, data, _latency = call_exa("/research/v1", body, api_key)
    return data


def get_research(research_id: str, *, api_key: str) -> dict[str, Any]:
    """GET /research/v1/{id} to poll a research task."""
    _status, data, _latency = call_exa(
        f"/research/v1/{research_id}", {}, api_key, method="GET"
    )
    return data


def _research_cost(data: dict[str, Any]) -> tuple[float, int | None, int | None, int | None]:
    """Extract cost breakdown defensively (may be absent without events=true)."""
    output = data.get("output")
    cost_block = output.get("costDollars", {}) if isinstance(output, dict) else {}
    if not isinstance(cost_block, dict):
        cost_block = {}
    try:
        total = float(cost_block.get("total", 0.0) or 0.0)
    except (TypeError, ValueError):
        total = 0.0
    return (
        total,
        cost_block.get("numSearches"),
        cost_block.get("numPages"),
        cost_block.get("reasoningTokens"),
    )


def build_research_envelope(
    *,
    status: str,
    research_id: str,
    model: str,
    instructions: str,
    output: Any,
    citations: list[Any],
    attempts: list[dict[str, Any]],
    cost: float,
    num_searches: int | None,
    num_pages: int | None,
    reasoning_tokens: int | None,
    reason_for_fallback: str | None = None,
) -> dict[str, Any]:
    """Assemble the research provider envelope (artifact-writer compatible)."""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    total_latency_ms = sum(a.get("latency_ms", 0) for a in attempts)
    return {
        "status": status,
        "primary_engine": "exa",
        "research_id": research_id,
        "model": model,
        "output": output,
        "citations": citations,
        "results": citations,  # artifact writer treats these as sources
        "telemetry": {
            "attempts": attempts,
            "reason_for_fallback": reason_for_fallback,
            "total_latency_ms": total_latency_ms,
            "total_cost_usd": cost,
            "num_searches": num_searches,
            "num_pages": num_pages,
            "reasoning_tokens": reasoning_tokens,
        },
        "meta": {
            "query": instructions,
            "instructions": instructions,
            "model": model,
            "timestamp": timestamp,
            "envelope_version": ENVELOPE_VERSION,
        },
    }


def research_task(
    instructions: str,
    *,
    api_key: str,
    model: str = RESEARCH_DEFAULT_MODEL,
    output_schema: dict[str, Any] | None = None,
    wait: bool = True,
    poll_interval: float = RESEARCH_POLL_INTERVAL_SECONDS,
    timeout_s: float = RESEARCH_TIMEOUT_SECONDS,
) -> tuple[dict[str, Any], int]:
    """Create an Exa research task and (optionally) poll to completion."""
    attempts: list[dict[str, Any]] = []
    try:
        created = create_research(
            instructions, model=model, output_schema=output_schema, api_key=api_key
        )
    except ExaPermanentError as exc:
        attempts.append(
            {
                "engine": "exa",
                "endpoint": "/research/v1",
                "http": exc.http_status,
                "latency_ms": exc.latency_ms,
                "error": "exa_auth_error" if exc.http_status in {401, 403} else "exa_4xx",
            }
        )
        env = build_research_envelope(
            status="FAILED", research_id="", model=model, instructions=instructions,
            output=None, citations=[], attempts=attempts, cost=0.0,
            num_searches=None, num_pages=None, reasoning_tokens=None,
            reason_for_fallback="exa_create_failed",
        )
        return env, (4 if exc.http_status in {401, 403} else 1)
    except (ExaTransientError, ExaMalformedResponseError) as exc:
        attempts.append(
            {
                "engine": "exa",
                "endpoint": "/research/v1",
                "http": getattr(exc, "http_status", None),
                "latency_ms": getattr(exc, "latency_ms", 0),
                "error": "exa_network",
            }
        )
        env = build_research_envelope(
            status="FAILED", research_id="", model=model, instructions=instructions,
            output=None, citations=[], attempts=attempts, cost=0.0,
            num_searches=None, num_pages=None, reasoning_tokens=None,
            reason_for_fallback="exa_create_failed",
        )
        return env, 6

    research_id = str(created.get("researchId", ""))
    attempts.append(
        {"engine": "exa", "endpoint": "/research/v1", "http": 201, "latency_ms": 0, "error": None}
    )

    if not wait:
        env = build_research_envelope(
            status="RUNNING", research_id=research_id, model=model, instructions=instructions,
            output=None, citations=[], attempts=attempts, cost=0.0,
            num_searches=None, num_pages=None, reasoning_tokens=None,
        )
        return env, 0

    start = time.monotonic()
    current_interval = min(poll_interval, RESEARCH_POLL_INTERVAL_CAP_SECONDS)
    while True:
        try:
            data = get_research(research_id, api_key=api_key)
        except ExaPermanentError as exc:
            if exc.http_status in {401, 403}:
                err_label, code = "exa_auth_error", 4
            else:
                err_label, code = "exa_poll_failed", 1
            attempts.append(
                {
                    "engine": "exa",
                    "endpoint": f"/research/v1/{research_id}",
                    "http": exc.http_status,
                    "latency_ms": exc.latency_ms,
                    "error": err_label,
                }
            )
            env = build_research_envelope(
                status="FAILED", research_id=research_id, model=model, instructions=instructions,
                output=None, citations=[], attempts=attempts, cost=0.0,
                num_searches=None, num_pages=None, reasoning_tokens=None,
                reason_for_fallback=err_label,
            )
            return env, code
        except (ExaTransientError, ExaMalformedResponseError) as exc:
            attempts.append(
                {
                    "engine": "exa",
                    "endpoint": f"/research/v1/{research_id}",
                    "http": getattr(exc, "http_status", None),
                    "latency_ms": getattr(exc, "latency_ms", 0),
                    "error": "exa_network",
                }
            )
            env = build_research_envelope(
                status="FAILED", research_id=research_id, model=model, instructions=instructions,
                output=None, citations=[], attempts=attempts, cost=0.0,
                num_searches=None, num_pages=None, reasoning_tokens=None,
                reason_for_fallback="exa_network",
            )
            return env, 6

        state = str(data.get("status", "running"))
        attempts.append(
            {
                "engine": "exa",
                "endpoint": f"/research/v1/{research_id}",
                "http": 200,
                "latency_ms": 0,
                "error": None,
            }
        )
        if state == "completed":
            cost, n_search, n_pages, r_tokens = _research_cost(data)
            env = build_research_envelope(
                status="OK", research_id=research_id, model=model, instructions=instructions,
                output=data.get("output"), citations=data.get("citations", []), attempts=attempts,
                cost=cost, num_searches=n_search, num_pages=n_pages, reasoning_tokens=r_tokens,
            )
            return env, 0
        if state == "failed":
            env = build_research_envelope(
                status="FAILED", research_id=research_id, model=model, instructions=instructions,
                output=data.get("output"), citations=[], attempts=attempts, cost=0.0,
                num_searches=None, num_pages=None, reasoning_tokens=None,
                reason_for_fallback=str(data.get("error") or "research_failed"),
            )
            return env, 1
        if time.monotonic() - start > timeout_s:
            env = build_research_envelope(
                status="FAILED", research_id=research_id, model=model, instructions=instructions,
                output=None, citations=[], attempts=attempts, cost=0.0,
                num_searches=None, num_pages=None, reasoning_tokens=None,
                reason_for_fallback="research_timeout",
            )
            return env, 1
        sleep_with_jitter(current_interval)
        current_interval = min(
            current_interval * RESEARCH_POLL_BACKOFF_FACTOR, RESEARCH_POLL_INTERVAL_CAP_SECONDS
        )


__all__ = [
    "__version__",
    "SCRIPT_DIR",
    "SYSTEMPROMPTS_DIR",
    "MODE_CONFIG",
    "CATEGORY_BLOCKS",
    "MODES",
    "ExaTransientError",
    "ExaPermanentError",
    "ExaMalformedResponseError",
    "sleep_with_jitter",
    "ENVELOPE_VERSION",
    "build_envelope",
    "RETRY_BACKOFF_SECONDS",
    "RETRY_BUDGET_SECONDS",
    "search_with_retry",
    "call_exa",
    "preflight",
    "load_system_prompt",
    "build_body",
    "validate_args",
    "find_similar",
    "answer",
    "RESEARCH_MODELS",
    "RESEARCH_DEFAULT_MODEL",
    "create_research",
    "get_research",
    "build_research_envelope",
    "research_task",
]
