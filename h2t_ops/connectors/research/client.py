"""Research connector helper substrate.

T2 intentionally contains only local helper plumbing: secret resolution,
artifact path/JSON helpers, details redaction, telemetry append, and an empty
ResearchClient facade. Provider calls land in later tasks.
"""
from __future__ import annotations

import json
import ipaddress
import os
import re
import uuid
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from h2t_ops.connectors.research import maintenance, navigation, provider_routing, store
from h2t_ops.core.errors import (
    AuthError,
    ConfigError,
    NetworkError,
    ProviderError,
    UsageError,
)

DEFAULT_OUTPUT_DIR = Path.home() / ".h2t" / "research"
REDACTED = "[REDACTED]"

_SENSITIVE_KEY_PARTS = (
    "authorization",
    "x-api-key",
    "api-key",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "key",
    "secret",
)
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_ENV_KEY_VALUE_RE = re.compile(
    r"\b(?:EXA_API_KEY|JINA_API_KEY)\s*=\s*([\"']?)[^\s\"']+\1",
    re.IGNORECASE,
)
_TOKEN_VALUE_RE = re.compile(r"\bsecret" + r"_[A-Za-z0-9._-]+", re.IGNORECASE)
_AUTH_HEADER_RE = re.compile(
    r"\b(Authorization\s*:\s*)Bearer\s+[A-Za-z0-9._~+/=-]+",
    re.IGNORECASE,
)
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?P<prefix>\b(?:access_token|refresh_token|api[_-]?key|apikey|token|key|secret|authorization)\s*=\s*)"
    r"(?P<quote>[\"']?)"
    r"(?P<value>[^&\s\"'#]+)"
    r"(?P=quote)",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s<>'\")]+", re.IGNORECASE)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _read_env_file(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE env files without mutating os.environ."""
    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def resolve_secret(name: str) -> str:
    """Resolve a secret from env, configured env file, canonical, then legacy path."""
    env_value = os.getenv(name)
    if env_value:
        return env_value

    candidates: list[Path] = []
    secrets_file = os.getenv("H2T_SECRETS_FILE")
    if secrets_file:
        candidates.append(Path(secrets_file).expanduser())
    home = Path.home()
    candidates.extend(
        [
            home / ".dor" / "secrets" / "secrets.env",
            home / ".dor" / "secrets.env",
        ]
    )

    for path in candidates:
        value = _read_env_file(path).get(name)
        if value:
            return value

    raise ConfigError(
        f"Research secret not found: {name}",
        hint=(
            f"Set {name} in the environment, H2T_SECRETS_FILE, "
            "~/.dor/secrets/secrets.env, or ~/.dor/secrets.env."
        ),
    )


def slugify(text: str, max_len: int = 60) -> str:
    """Return a lowercase filesystem-safe slug."""
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    slug = slug[:max_len].strip("-")
    return slug or "research"


def artifact_id(prefix: str = "research") -> str:
    """Return a compact unique artifact id."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{slugify(prefix, max_len=24)}_{stamp}_{uuid.uuid4().hex[:8]}"


def validate_public_http_url(url: str) -> str:
    """Accept only public http(s) URLs for provider fetch/crawl surfaces."""
    raw = str(url or "").strip()
    parts = urlsplit(raw)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc or not parts.hostname:
        raise UsageError(
            "Research fetch URL must be an absolute http(s) URL",
            hint="Use a public https://... or http://... URL.",
        )
    if parts.username or parts.password:
        raise UsageError(
            "Research fetch URL must not contain embedded credentials",
            hint="Remove userinfo from the URL before passing it to research fetch/crawl.",
        )

    host = parts.hostname.strip("[]").lower()
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if host == "localhost" or host.endswith(".localhost") or "." not in host:
            raise UsageError(
                "Research fetch URL must target a public host",
                hint="Localhost, single-label hosts, file paths, and private network URLs are blocked.",
            )
        return raw

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        raise UsageError(
            "Research fetch URL must target a public host",
            hint="Localhost, single-label hosts, file paths, and private network URLs are blocked.",
        )
    return raw


def artifact_paths(
    *,
    output_dir: Path,
    project: str,
    slug_source: str,
    kind: str,
) -> dict[str, Path]:
    """Create artifact directory and return the canonical output paths."""
    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    nonce = uuid.uuid4().hex[:8]
    base = f"{slugify(project)}-{slugify(slug_source)}-{slugify(kind)}-{stamp}-{nonce}"
    return {
        "partial_md": output_dir / f"{base}.partial.md",
        "sources_json": output_dir / f"{base}.sources.json",
        "artifact_json": output_dir / f"{base}.artifact.json",
        "raw_html": output_dir / f"{base}.raw.html",
    }


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("_", "-")
    return any(part.replace("_", "-") in normalized for part in _SENSITIVE_KEY_PARTS)


def _sanitize_url_query(value: str) -> str:
    parts = urlsplit(value)
    netloc = parts.netloc
    if parts.username or parts.password:
        host = parts.hostname or ""
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        netloc = host
        if parts.port:
            netloc = f"{netloc}:{parts.port}"
    if not parts.query:
        return urlunsplit((parts.scheme, netloc, parts.path, "", parts.fragment))

    query = parse_qsl(parts.query, keep_blank_values=True)
    sanitized_query = [
        (key, REDACTED if _is_sensitive_key(key) else item)
        for key, item in query
    ]
    return urlunsplit(
        (
            parts.scheme,
            netloc,
            parts.path,
            urlencode(sanitized_query, doseq=True, quote_via=quote),
            parts.fragment,
        )
    )


def _sanitize_string(value: str) -> str:
    value = _URL_RE.sub(lambda m: _sanitize_url_query(m.group(0)), value)
    value = _SENSITIVE_ASSIGNMENT_RE.sub(
        lambda m: f"{m.group('prefix')}{m.group('quote')}{REDACTED}{m.group('quote')}",
        value,
    )
    value = _AUTH_HEADER_RE.sub(r"\1" + REDACTED, value)
    value = _BEARER_RE.sub(f"Bearer {REDACTED}", value)
    value = _ENV_KEY_VALUE_RE.sub(
        lambda m: m.group(0).split("=", 1)[0] + "=" + REDACTED,
        value,
    )
    value = _TOKEN_VALUE_RE.sub(REDACTED, value)
    return value


def sanitize_details(value: Any) -> Any:
    """Recursively redact provider headers, API keys, tokens, and secret values."""
    if isinstance(value, dict):
        sanitized: dict[Any, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                sanitized["[REDACTED_KEY]"] = REDACTED
            else:
                safe_key = _sanitize_string(str(key))
                sanitized[safe_key] = sanitize_details(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_details(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_details(item) for item in value)
    if isinstance(value, str):
        return _sanitize_string(value)
    return value


def _json_safe(value: Any) -> Any:
    """Coerce values into JSON-safe primitives for best-effort telemetry."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(_json_safe(k)): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def build_research_artifact(
    *,
    artifact_id: str,
    provider_status: str,
    tool: str,
    artifact_refs: dict[str, Any],
    telemetry: dict[str, Any],
) -> dict[str, Any]:
    """Build the stable research artifact envelope."""
    return {
        "kind": "research_artifact",
        "version": "v1",
        "artifact_id": artifact_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "provider_status": provider_status,
        "artifact_refs": artifact_refs,
        "telemetry": sanitize_details(telemetry),
    }


def _artifact_ref_for_path(
    path: str | None,
    *,
    output_dir: Path,
) -> str | None:
    """Return a relative artifact ref only for files under output_dir."""
    if not path:
        return None
    try:
        target = Path(path).expanduser().resolve()
        base = Path(output_dir).expanduser().resolve()
        return target.relative_to(base).as_posix()
    except (OSError, ValueError):
        return None


def write_json(path: Path, payload: Any) -> None:
    """Write UTF-8 JSON with deterministic formatting."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def append_telemetry(path: Path, record: dict[str, Any]) -> bool:
    """Best-effort JSONL telemetry append."""
    if os.getenv("H2T_RESEARCH_TELEMETRY_DISABLE") == "1":
        return False

    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            payload = _json_safe(sanitize_details(record))
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return True
    except (OSError, TypeError, ValueError):
        return False

def _content_hash(*parts: Any) -> str:
    payload = "||".join(str(part).strip() for part in parts if str(part).strip())
    return store.sha256_text(payload)


def _raise_for_provider_failure(
    message: str,
    provider_envelope: dict[str, Any],
    exit_code: int,
) -> None:
    """Map a failed provider envelope to a typed public error."""
    details = sanitize_details({"provider_envelope": provider_envelope})
    attempts = provider_envelope.get("telemetry", {}).get("attempts", [])
    last_error = None
    if attempts and isinstance(attempts[-1], dict):
        last_error = attempts[-1].get("error")

    if exit_code == 3 or last_error == "exa_network_timeout":
        raise NetworkError(message, details=details)
    if last_error == "exa_auth_error":
        raise AuthError(message, details=details)
    if exit_code == 1 or last_error == "exa_usage_error" or message.startswith("EXA_ERROR:ARGS"):
        raise UsageError(message, details=details)
    raise ProviderError(message, details=details)


class ResearchClient:
    """Facade for provider-backed research operations."""

    def __init__(self, *, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR

    def _research_root(self) -> Path:
        return self.output_dir

    def _require_research_route(
        self,
        capability: str,
        *,
        provider: str | None = None,
    ) -> dict[str, Any]:
        """Require a configured local provider route before side effects."""
        return provider_routing.select_route(capability, provider=provider)

    def _persist_document_object(
        self,
        *,
        project: str,
        provider: str,
        canonical_url: str,
        source_url: str,
        title: str,
        fetched_at: str,
        content_hash: str,
        artifact_refs: dict[str, Any],
    ) -> dict[str, str]:
        root = self._research_root()
        document = store.build_research_document(
            canonical_url=canonical_url,
            source_url=source_url,
            provider=provider,
            title=title,
            fetched_at=fetched_at,
            content_hash=content_hash,
            artifact_refs=artifact_refs,
            project_ids=[f"project:{project}"],
            thread_ids=[],
            entity_ids=[],
        )
        document_path = store.write_object(root, "documents", document["document_id"], document)
        store.upsert_document_index(root, document)
        store.upsert_alias_index(
            root,
            [
                {
                    "alias_type": "url",
                    "alias_value": alias_value,
                    "target_object_type": "document",
                    "target_id": document["document_id"],
                    "confidence": "high",
                }
                for alias_value in _dedupe_alias_values([canonical_url, source_url])
            ]
        )
        return {"document_id": document["document_id"], "document_json": str(document_path)}

    def _persist_thread_run(
        self,
        *,
        project: str,
        query: str,
        provider: str,
        topics: list[str],
        document_ids: list[str],
        created_at: str,
    ) -> dict[str, str]:
        root = self._research_root()
        thread = store.build_research_thread(
            question=query,
            created_at=created_at,
            context_type="project",
            context_id=f"project:{project}",
            domain="research",
            topics=topics,
        )
        run = store.build_research_run(
            thread_id=thread["thread_id"],
            created_at=created_at,
            query=query,
            provider_set=[provider],
            document_ids=document_ids,
        )
        thread_path = store.write_object(root, "threads", thread["thread_id"], thread)
        run_path = store.write_object(root, "runs", run["run_id"], run)
        store.upsert_thread_index(root, thread)
        return {
            "thread_id": thread["thread_id"],
            "thread_json": str(thread_path),
            "run_id": run["run_id"],
            "run_json": str(run_path),
        }

    def _persist_synthesis(
        self,
        *,
        thread_id: str,
        run_id: str,
        summary: str,
        created_at: str,
        project: str,
    ) -> dict[str, str]:
        root = self._research_root()
        synthesis = store.build_research_synthesis(
            thread_id=thread_id,
            run_ids=[run_id],
            summary=summary,
            created_at=created_at,
        )
        path = store.write_object(root, "syntheses", synthesis["synthesis_id"], synthesis)
        store.upsert_synthesis_index(root, synthesis, project_ids=[f"project:{project}"])
        thread_path = store.object_path(root, "threads", thread_id)
        if thread_path.exists():
            thread = json.loads(thread_path.read_text(encoding="utf-8"))
            if isinstance(thread, dict):
                thread["latest_synthesis_id"] = synthesis["synthesis_id"]
                store.write_object(root, "threads", thread_id, thread)
                store.upsert_thread_index(root, thread)
        return {"synthesis_id": synthesis["synthesis_id"], "synthesis_json": str(path)}

    def _attach_research_refs(
        self,
        artifact: dict[str, Any],
        research_refs: dict[str, str],
    ) -> dict[str, Any]:
        if not research_refs:
            return artifact
        artifact["research_refs"] = research_refs
        artifact_json = artifact.get("artifact_refs", {}).get("artifact_json")
        if isinstance(artifact_json, str) and artifact_json:
            write_json(self.output_dir / artifact_json, artifact)
        return artifact

    def visual_ocr(
        self,
        *,
        fetch_sidecar: str,
        image_path: str,
        project: str = "default",
    ) -> dict[str, Any]:
        """Build a review-required visual OCR rescue artifact from one image."""
        from h2t_ops.connectors.research import visual_ocr

        sidecar = visual_ocr.load_fetch_sidecar(fetch_sidecar)
        fetch_envelope = visual_ocr.load_fetch_envelope(sidecar)
        visual_ocr.validate_visual_ocr_trigger(fetch_envelope)

        extracted_text, visible_headings, ocr_confidence = visual_ocr.extract_text_from_image(
            image_path
        )
        reason = (
            fetch_envelope.get("telemetry", {}).get("reason_for_failed")
            or fetch_envelope.get("telemetry", {}).get("reason_for_degraded")
        )
        captured_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        ocr_envelope = visual_ocr.build_visual_ocr_envelope(
            url=str(fetch_envelope.get("url") or ""),
            source_fetch_status=str(fetch_envelope.get("status") or "UNKNOWN"),
            source_fetch_reason=str(reason) if reason is not None else None,
            captured_at=captured_at,
            image_path=image_path,
            extracted_text=extracted_text,
            visible_headings=visible_headings,
            ocr_confidence=ocr_confidence,
        )
        telemetry = {
            "calls": 1,
            "providers": ["visual_ocr"],
            "estimated_cost_usd": 0.0,
            "cost_basis": "local_ocr",
            "captured_at": captured_at,
        }
        artifact = self._write_visual_ocr_artifacts(
            slug_source=str(fetch_envelope.get("url") or image_path),
            project=project,
            ocr_envelope=ocr_envelope,
            telemetry=telemetry,
        )
        safe_ocr_envelope = sanitize_details(ocr_envelope)
        return {
            "kind": "research_visual_ocr_envelope",
            **safe_ocr_envelope,
            "artifact": artifact,
        }

    def visual_ocr_auto(self, url: str, *, project: str = "default") -> dict[str, Any]:
        """Auto-capture a screenshot of url, run OCR, and persist artifacts."""
        from h2t_ops.connectors.research import visual_ocr

        output_dir = self.output_dir
        envelope, _exit_code = visual_ocr.capture_and_ocr(
            url, output_dir=output_dir, project=project
        )
        captured_at = envelope.get("provenance", {}).get("captured_at", "")
        telemetry = {
            "calls": 1,
            "providers": ["visual_ocr"],
            "estimated_cost_usd": 0.0,
            "cost_basis": "local_ocr",
            "captured_at": captured_at,
        }
        artifact = self._write_visual_ocr_artifacts(
            slug_source=url,
            project=project,
            ocr_envelope=envelope,
            telemetry=telemetry,
        )
        safe_ocr_envelope = sanitize_details(envelope)
        return {
            "kind": "research_visual_ocr_envelope",
            **safe_ocr_envelope,
            "artifact": artifact,
        }

    def preflight(self) -> dict[str, Any]:
        """Validate Exa credential resolution and provider connectivity."""
        from h2t_ops.connectors.research import exa

        self._require_research_route("preflight", provider="exa")
        exa.preflight(resolve_secret("EXA_API_KEY"))
        return {"status": "OK", "provider": "exa"}

    def crawl(self, url: str, *, project: str = "default") -> dict[str, Any]:
        """Fetch URL contents through Exa /contents and persist provider artifacts."""
        from h2t_ops.connectors.research import exa

        url = validate_public_http_url(url)
        self._require_research_route("crawl", provider="exa")
        api_key = resolve_secret("EXA_API_KEY")
        body = {"urls": [url], "text": {"maxCharacters": 15000}}
        try:
            status, data, latency_ms = exa.call_exa("/contents", body, api_key)
        except exa.ExaPermanentError as exc:
            details = sanitize_details(
                {
                    "http_status": exc.http_status,
                    "latency_ms": exc.latency_ms,
                    "provider_error": exc.body,
                }
            )
            if exc.http_status in {401, 403}:
                raise AuthError(
                    f"Exa crawl auth failed: http {exc.http_status}",
                    details=details,
                ) from exc
            raise ProviderError(
                f"Exa crawl failed: http {exc.http_status}",
                details=details,
            ) from exc
        except exa.ExaTransientError as exc:
            details = sanitize_details(
                {
                    "http_status": exc.http_status,
                    "latency_ms": exc.latency_ms,
                    "provider_error": exc.body,
                }
            )
            if exc.http_status is None:
                raise NetworkError(
                    f"Exa crawl network failed: {exc}",
                    details=details,
                ) from exc
            raise ProviderError(
                f"Exa crawl failed: http {exc.http_status}",
                details=details,
            ) from exc
        except exa.ExaMalformedResponseError as exc:
            raise ProviderError(
                f"Exa crawl malformed response: {exc}",
                details=sanitize_details({"latency_ms": exc.latency_ms}),
            ) from exc

        results = data.get("results", [])
        if not isinstance(results, list):
            raise ProviderError(
                "Exa crawl malformed response: results must be a list",
                details=sanitize_details({"results_type": type(results).__name__}),
            )

        statuses = data.get("statuses")
        if not results and statuses:
            _raise_for_crawl_statuses(
                url=url,
                http_status=status,
                latency_ms=latency_ms,
                statuses=statuses,
                cost=_cost_from_exa_response(data),
                build_envelope=exa.build_envelope,
            )

        reason = None if results else "exa_empty_results"
        cost = _cost_from_exa_response(data)
        provider_envelope = exa.build_envelope(
            status="OK" if results else "DEGRADED",
            results=results,
            attempts=[
                {
                    "engine": "exa",
                    "endpoint": "/contents",
                    "http": status,
                    "latency_ms": latency_ms,
                    "error": reason,
                }
            ],
            meta={
                "query": url,
                "mode": "crawl",
                "num_results_requested": 1,
                "num_results_returned": len(results),
            },
            total_cost_usd=cost,
            reason_for_fallback=reason,
        )
        telemetry = _artifact_telemetry(provider_envelope)
        artifact = self._write_provider_artifacts(
            kind="crawl",
            slug_source=url,
            project=project,
            provider_envelope=provider_envelope,
            telemetry=telemetry,
            ledger_provider="exa",
            ledger_endpoint="/contents",
            ledger_mode="crawl",
        )
        artifact = self._attach_research_refs(
            artifact,
            self._persist_provider_document(
                project=project,
                provider_envelope=sanitize_details(provider_envelope),
                artifact=artifact,
                provider="exa",
            ),
        )
        safe_provider_envelope = sanitize_details(provider_envelope)
        return {
            "kind": "research_provider_envelope",
            **safe_provider_envelope,
            "artifact": artifact,
        }

    def _write_provider_artifacts(
        self,
        *,
        kind: str,
        slug_source: str,
        project: str,
        provider_envelope: dict[str, Any],
        telemetry: dict[str, Any],
        ledger_provider: str,
        ledger_endpoint: str,
        ledger_mode: str,
        raw_html_path: str | None = None,
    ) -> dict[str, Any]:
        """Write provider result artifacts and best-effort telemetry."""
        safe_project = str(sanitize_details(project))
        paths = artifact_paths(
            output_dir=self.output_dir,
            project=safe_project,
            slug_source=sanitize_details(slug_source),
            kind=kind,
        )
        safe_provider_envelope = sanitize_details(provider_envelope)
        results = safe_provider_envelope.get("results", [])
        if not isinstance(results, list):
            results = []

        write_json(paths["sources_json"], results)
        paths["partial_md"].write_text(
            _render_partial_markdown(safe_provider_envelope),
            encoding="utf-8",
        )
        raw_html_ref = _artifact_ref_for_path(
            raw_html_path,
            output_dir=self.output_dir,
        )

        artifact = build_research_artifact(
            artifact_id=artifact_id(f"research-{kind}"),
            provider_status=str(provider_envelope.get("status", "FAILED")),
            tool="h2t-ops research",
            artifact_refs={
                "sources_json": paths["sources_json"].name,
                "partial_md": paths["partial_md"].name,
                "artifact_json": paths["artifact_json"].name,
                "raw_html": raw_html_ref,
            },
            telemetry=telemetry,
        )
        write_json(paths["artifact_json"], artifact)

        append_telemetry(
            self.output_dir / "telemetry.jsonl",
            {
                "kind": "research_telemetry",
                "version": "v1",
                "provider": ledger_provider,
                "endpoint": ledger_endpoint,
                "mode": ledger_mode,
                "status": provider_envelope.get("status"),
                "latency_ms": provider_envelope.get("telemetry", {}).get("total_latency_ms"),
                "result_count": len(results),
                "estimated_cost_usd": telemetry.get("estimated_cost_usd"),
                "cost_basis": telemetry.get("cost_basis"),
                "artifact_id": artifact["artifact_id"],
            },
        )
        return artifact

    def _write_visual_ocr_artifacts(
        self,
        *,
        slug_source: str,
        project: str,
        ocr_envelope: dict[str, Any],
        telemetry: dict[str, Any],
    ) -> dict[str, Any]:
        """Write visual OCR artifacts with a non-canonical review-required summary."""
        from h2t_ops.connectors.research import visual_ocr

        safe_project = str(sanitize_details(project))
        paths = visual_ocr.build_visual_ocr_artifact_paths(
            output_dir=self.output_dir,
            project=safe_project,
            slug_source=str(sanitize_details(slug_source)),
        )
        safe_ocr_envelope = sanitize_details(ocr_envelope)
        write_json(paths["sources_json"], safe_ocr_envelope)
        paths["partial_md"].parent.mkdir(parents=True, exist_ok=True)
        paths["partial_md"].write_text(
            _render_visual_ocr_partial_markdown(safe_ocr_envelope),
            encoding="utf-8",
        )
        artifact = build_research_artifact(
            artifact_id=artifact_id("research-visual-ocr"),
            provider_status=str(ocr_envelope.get("status", "FAILED")),
            tool="h2t-ops research visual-ocr",
            artifact_refs={
                "sources_json": paths["sources_json"].name,
                "partial_md": paths["partial_md"].name,
                "artifact_json": paths["artifact_json"].name,
                "raw_html": None,
            },
            telemetry=telemetry,
        )
        write_json(paths["artifact_json"], artifact)
        artifact = self._attach_research_refs(
            artifact,
            self._persist_visual_ocr_document(
                project=project,
                ocr_envelope=safe_ocr_envelope,
                artifact=artifact,
            ),
        )
        append_telemetry(
            self.output_dir / "telemetry.jsonl",
            {
                "kind": "research_telemetry",
                "version": "v1",
                "provider": "visual_ocr",
                "endpoint": "visual_ocr",
                "mode": "single_image",
                "status": ocr_envelope.get("status"),
                "artifact_id": artifact["artifact_id"],
                "source_fetch_status": ocr_envelope.get("provenance", {}).get("source_fetch_status"),
                "source_fetch_reason": ocr_envelope.get("provenance", {}).get("source_fetch_reason"),
                "captured_at": ocr_envelope.get("provenance", {}).get("captured_at"),
                "latency_ms": None,
                "result_count": 1 if ocr_envelope.get("body_text_visual_ocr") else 0,
                "estimated_cost_usd": telemetry.get("estimated_cost_usd"),
                "cost_basis": telemetry.get("cost_basis"),
            },
        )
        return artifact

    def _persist_provider_document(
        self,
        *,
        project: str,
        provider_envelope: dict[str, Any],
        artifact: dict[str, Any],
        provider: str,
    ) -> dict[str, str]:
        if str(provider_envelope.get("status") or "").upper() != "OK":
            return {}
        results = provider_envelope.get("results", [])
        first: dict[str, Any] = {}
        source_url = str(provider_envelope.get("url") or provider_envelope.get("final_url") or "").strip()
        title = str(provider_envelope.get("title") or source_url)
        body_text = str(provider_envelope.get("body_text") or provider_envelope.get("body_markdown") or "")

        if isinstance(results, list) and results:
            candidate = results[0]
            if isinstance(candidate, dict):
                first = candidate
                source_url = str(first.get("url") or provider_envelope.get("meta", {}).get("query") or source_url).strip()
                title = str(first.get("title") or title or source_url)
                body_text = str(first.get("text") or first.get("answer") or body_text)

        canonical_url = str(provider_envelope.get("final_url") or source_url).strip()
        if not canonical_url:
            return {}
        content_hash = _content_hash(canonical_url, title, body_text)
        artifact_refs = {
            "metadata": artifact["artifact_refs"]["artifact_json"],
            "normalized_text": artifact["artifact_refs"]["sources_json"],
            "citation_bundle": None,
            "markdown_mirror": artifact["artifact_refs"]["partial_md"],
        }
        return self._persist_document_object(
            project=project,
            provider=provider,
            canonical_url=canonical_url,
            source_url=source_url,
            title=title,
            fetched_at=str(artifact["created_at"]),
            content_hash=content_hash,
            artifact_refs=artifact_refs,
        )

    def _persist_visual_ocr_document(
        self,
        *,
        project: str,
        ocr_envelope: dict[str, Any],
        artifact: dict[str, Any],
    ) -> dict[str, str]:
        source_url = str(ocr_envelope.get("url") or "").strip()
        if not source_url:
            return {}
        canonical_url = source_url
        headings = ocr_envelope.get("visible_headings", [])
        title = str(headings[0]) if isinstance(headings, list) and headings else canonical_url
        body_text = str(ocr_envelope.get("body_text_visual_ocr") or "")
        fetched_at = str(ocr_envelope.get("provenance", {}).get("captured_at") or artifact["created_at"])
        content_hash = _content_hash(canonical_url, title, body_text)
        artifact_refs = {
            "metadata": artifact["artifact_refs"]["artifact_json"],
            "normalized_text": artifact["artifact_refs"]["sources_json"],
            "citation_bundle": None,
            "markdown_mirror": artifact["artifact_refs"]["partial_md"],
        }
        return self._persist_document_object(
            project=project,
            provider="visual_ocr",
            canonical_url=canonical_url,
            source_url=source_url,
            title=title,
            fetched_at=fetched_at,
            content_hash=content_hash,
            artifact_refs=artifact_refs,
        )

    def fetch_url(
        self,
        url: str,
        *,
        provider: str = "auto",
        keep_raw: bool = False,
        timeout_ms: int = 15000,
        min_body_chars: int = 200,
        user_agent: str | None = None,
        project: str = "default",
        config_path: str | None = None,
    ) -> dict[str, Any]:
        """Fetch one URL through the research provider ladder."""
        from h2t_ops.connectors.research import fetch

        url = validate_public_http_url(url)
        config = fetch.load_config(config_path)
        config["ladder"]["per_provider_timeout_ms"] = timeout_ms
        config["ladder"]["min_body_chars"] = min_body_chars
        for provider_config in (config.get("providers") or {}).values():
            if (
                isinstance(provider_config, dict)
                and "timeout_ms" in provider_config
            ):
                provider_config["timeout_ms"] = timeout_ms
        safe_slug_source = str(sanitize_details(url))
        safe_project = str(sanitize_details(project))
        provider_envelope = fetch.fetch_via_ladder(
            url=url,
            provider_choice=provider,
            config=config,
            user_agent=user_agent or fetch.DEFAULT_USER_AGENT,
            keep_raw=keep_raw,
            min_body_chars=min_body_chars,
            output_paths=artifact_paths(
                output_dir=self.output_dir,
                project=safe_project,
                slug_source=safe_slug_source,
                kind="fetch",
            ),
        )

        attempts = provider_envelope.get("telemetry", {}).get("attempts", [])
        if not isinstance(attempts, list):
            attempts = []
        providers = sorted(
            {
                str(attempt.get("provider") or attempt.get("engine"))
                for attempt in attempts
                if isinstance(attempt, dict)
                and (attempt.get("provider") or attempt.get("engine"))
            }
        )
        provider_used = provider_envelope.get("provider_used")
        if provider_used and provider_used != "none" and provider_used not in providers:
            providers.append(str(provider_used))

        telemetry = {
            "calls": len(attempts),
            "providers": providers,
            "estimated_cost_usd": 0.0
            if provider_envelope.get("provider_used") == "direct"
            else None,
            "cost_basis": "zero"
            if provider_envelope.get("provider_used") == "direct"
            else "unknown",
        }
        metadata = provider_envelope.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        artifact = self._write_provider_artifacts(
            kind="fetch",
            slug_source=url,
            project=project,
            provider_envelope=provider_envelope,
            telemetry=telemetry,
            ledger_provider=provider_envelope.get("provider_used") or provider,
            ledger_endpoint="fetch_ladder",
            ledger_mode=provider,
            raw_html_path=metadata.get("raw_html_path"),
        )
        artifact = self._attach_research_refs(
            artifact,
            self._persist_provider_document(
                project=project,
                provider_envelope=sanitize_details(provider_envelope),
                artifact=artifact,
                provider=str(provider_envelope.get("provider_used") or provider),
            ),
        )
        safe_provider_envelope = sanitize_details(provider_envelope)
        result = {"kind": "research_fetch_envelope", **safe_provider_envelope, "artifact": artifact}
        if provider_envelope.get("status") != "FAILED":
            return result

        details = sanitize_details({"provider_envelope": provider_envelope})
        gate = provider_envelope.get("content_gate")
        if gate in {"login_required", "paid"}:
            raise AuthError(f"Fetch gated: {gate}", details=details)

        last_attempt = attempts[-1] if attempts and isinstance(attempts[-1], dict) else {}
        if last_attempt.get("error") == "fetch_network_timeout":
            raise NetworkError("Fetch failed: network timeout", details=details)
        raise ProviderError("Fetch failed", details=details)

    def search(
        self,
        *,
        query: str,
        mode: str = "generic",
        depth: str | None = None,
        num_results: int | None = None,
        additional_queries: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        include_text: list[str] | None = None,
        exclude_text: list[str] | None = None,
        country: str | None = None,
        full_text: bool = False,
        project: str = "default",
        no_retry: bool = False,
    ) -> dict[str, Any]:
        """Run Exa search and persist provider artifacts."""
        from h2t_ops.connectors.research import exa

        self._require_research_route("search", provider="exa")
        api_key = resolve_secret("EXA_API_KEY")
        args = Namespace(
            query=query,
            mode=mode,
            depth=depth,
            num_results=num_results,
            additional_queries=additional_queries,
            start_date=start_date,
            end_date=end_date,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            include_text=include_text,
            exclude_text=exclude_text,
            country=country,
            full_text=full_text,
        )

        exa.validate_args(args)
        system_prompt, output_schema = exa.load_system_prompt(mode)
        body = exa.build_body(args, system_prompt, output_schema)
        provider_envelope, exit_code = exa.search_with_retry(
            body=body,
            api_key=api_key,
            retry=not no_retry,
            mode=mode,
        )
        telemetry = _artifact_telemetry(provider_envelope)
        artifact = self._write_provider_artifacts(
            kind="search",
            slug_source=query,
            project=project,
            provider_envelope=provider_envelope,
            telemetry=telemetry,
            ledger_provider="exa",
            ledger_endpoint="/search",
            ledger_mode=mode,
        )
        research_refs = self._persist_thread_run(
            project=project,
            query=query,
            provider="exa",
            topics=[mode],
            document_ids=[],
            created_at=artifact["created_at"],
        )
        artifact = self._attach_research_refs(artifact, research_refs)

        if provider_envelope.get("status") == "FAILED":
            _raise_for_provider_failure(
                "Exa search failed",
                provider_envelope,
                exit_code,
            )

        safe_provider_envelope = sanitize_details(provider_envelope)
        return {
            "kind": "research_provider_envelope",
            **safe_provider_envelope,
            "artifact": artifact,
        }

    def similar(
        self,
        url: str,
        *,
        num_results: int | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> dict[str, Any]:
        """Find pages similar to a URL via Exa /findSimilar."""
        from h2t_ops.connectors.research.exa import find_similar

        url = validate_public_http_url(url)
        self._require_research_route("similar", provider="exa")
        api_key = resolve_secret("EXA_API_KEY")
        provider_envelope, exit_code = find_similar(
            url,
            api_key=api_key,
            num_results=num_results or 10,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
        )
        telemetry = _artifact_telemetry(provider_envelope)
        artifact = self._write_provider_artifacts(
            kind="similar",
            slug_source=url,
            project="default",
            provider_envelope=provider_envelope,
            telemetry=telemetry,
            ledger_provider="exa",
            ledger_endpoint="/findSimilar",
            ledger_mode="similar",
        )
        research_refs = self._persist_thread_run(
            project="default",
            query=url,
            provider="exa",
            topics=["similar"],
            document_ids=[],
            created_at=artifact["created_at"],
        )
        artifact = self._attach_research_refs(artifact, research_refs)

        if provider_envelope.get("status") == "FAILED":
            _raise_for_provider_failure(
                "Exa findSimilar failed",
                provider_envelope,
                exit_code,
            )

        safe_provider_envelope = sanitize_details(provider_envelope)
        return {
            "kind": "research_provider_envelope",
            **safe_provider_envelope,
            "artifact": artifact,
        }

    def answer(self, query: str) -> dict[str, Any]:
        """Get a direct LLM-grounded answer from Exa /answer."""
        from h2t_ops.connectors.research.exa import answer as _answer

        self._require_research_route("answer", provider="exa")
        api_key = resolve_secret("EXA_API_KEY")
        envelope, exit_code = _answer(query, api_key=api_key)
        telemetry = _artifact_telemetry(envelope)
        artifact = self._write_provider_artifacts(
            kind="answer",
            slug_source=query,
            project="default",
            provider_envelope=envelope,
            telemetry=telemetry,
            ledger_provider="exa",
            ledger_endpoint="/answer",
            ledger_mode="answer",
        )
        run_refs = self._persist_thread_run(
            project="default",
            query=query,
            provider="exa",
            topics=["answer"],
            document_ids=[],
            created_at=artifact["created_at"],
        )
        safe_results = sanitize_details(envelope).get("results") or [{}]
        first_result = safe_results[0] if isinstance(safe_results, list) and safe_results else {}
        summary_text = str(first_result.get("answer") or "") if isinstance(first_result, dict) else ""
        synthesis_refs = self._persist_synthesis(
            thread_id=run_refs["thread_id"],
            run_id=run_refs["run_id"],
            summary=summary_text,
            created_at=artifact["created_at"],
            project="default",
        )
        artifact = self._attach_research_refs(artifact, {**run_refs, **synthesis_refs})

        if envelope.get("status") == "FAILED":
            _raise_for_provider_failure(
                "Exa answer failed",
                envelope,
                exit_code,
            )

        safe_envelope = sanitize_details(envelope)
        return {
            "kind": "research_answer_envelope",
            **safe_envelope,
            "artifact": artifact,
        }

    def resolve_author(
        self,
        name: str,
        *,
        keywords: list[str] | None = None,
        hint: str | None = None,
    ) -> dict[str, Any]:
        """Resolve an author name to a channel URL."""
        from h2t_ops.connectors.research.author_resolve import resolve_author as _resolve

        self._require_research_route("author", provider="exa")
        api_key = resolve_secret("EXA_API_KEY")
        result = _resolve(name, api_key=api_key, keywords=keywords, hint=hint)
        return sanitize_details(result)

    def list_research_index(self, index_name: str, *, project: str | None = None) -> dict[str, Any]:
        """List a research index through local navigation cache helpers."""
        return navigation.list_index(self.output_dir, index_name, project=project)

    def show_research_object(self, object_type: str, object_id: str) -> dict[str, Any]:
        """Load a canonical research object by object type and id."""
        return navigation.show_object(self.output_dir, object_type, object_id)

    def resolve_research_alias(
        self,
        alias_value: str,
        *,
        alias_type: str = "url",
    ) -> dict[str, Any]:
        """Resolve aliases through the local aliases index."""
        return navigation.resolve_alias(
            self.output_dir,
            alias_value=alias_value,
            alias_type=alias_type,
        )

    def research_provider_status(
        self,
        *,
        capability: str | None = None,
    ) -> dict[str, Any]:
        """Return local provider/key readiness without network calls."""
        return provider_routing.provider_status(capability=capability)

    def research_route(
        self,
        capability: str,
        *,
        provider: str | None = None,
    ) -> dict[str, Any]:
        """Select a configured provider route for a research capability."""
        return provider_routing.select_route(capability, provider=provider)

    def research_doctor(self) -> dict[str, Any]:
        """Inspect local research store health without writing files."""
        return maintenance.doctor(self.output_dir)

    def rebuild_research_indexes(self) -> dict[str, Any]:
        """Rebuild research navigation indexes from canonical object JSON."""
        return maintenance.rebuild_indexes(self.output_dir)

    def cleanup_research(self, *, dry_run: bool = True) -> dict[str, Any]:
        """Return a cleanup plan for non-canonical research artifacts."""
        return maintenance.cleanup(self.output_dir, dry_run=dry_run)


def _artifact_telemetry(provider_envelope: dict[str, Any]) -> dict[str, Any]:
    provider_telemetry = provider_envelope.get("telemetry", {})
    attempts = provider_telemetry.get("attempts", [])
    providers = sorted(
        {
            str(attempt.get("engine"))
            for attempt in attempts
            if isinstance(attempt, dict) and attempt.get("engine")
        }
    )
    return {
        "calls": len(attempts) if isinstance(attempts, list) else 0,
        "providers": providers or [str(provider_envelope.get("primary_engine", "exa"))],
        "estimated_cost_usd": provider_telemetry.get("total_cost_usd"),
        "cost_basis": "provider_reported",
    }


def _dedupe_alias_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _cost_from_exa_response(data: dict[str, Any]) -> float:
    cost = data.get("costDollars", {})
    if isinstance(cost, dict):
        raw = cost.get("total", 0.0)
    else:
        raw = cost
    try:
        return float(raw or 0.0)
    except (TypeError, ValueError):
        return 0.0


_GATE_STATUS_TOKENS = (
    "login",
    "paywall",
    "paid",
    "subscription",
    "subscriber",
    "auth_required",
    "login_required",
    "payment_required",
    "unauthorized",
)
_NETWORK_STATUS_TOKENS = (
    "timeout",
    "timed out",
    "network",
    "connection",
    "dns",
    "unreachable",
    "reset",
)
_STATUS_ERROR_TOKENS = (
    "error",
    "fail",
    "failed",
    "forbidden",
    "unauthorized",
    "not_found",
    "not found",
    "missing",
    "timeout",
    "timed out",
    "network",
)


def _raise_for_crawl_statuses(
    *,
    url: str,
    http_status: int,
    latency_ms: int,
    statuses: Any,
    cost: float,
    build_envelope: Any,
) -> None:
    failure = _classify_crawl_status_failure(statuses)
    if failure is None:
        return

    error, status_code = failure
    provider_envelope = build_envelope(
        status="FAILED",
        results=[],
        attempts=[
            {
                "engine": "exa",
                "endpoint": "/contents",
                "http": status_code or http_status,
                "latency_ms": latency_ms,
                "error": error,
            }
        ],
        meta={
            "query": url,
            "mode": "crawl",
            "num_results_requested": 1,
            "num_results_returned": 0,
        },
        total_cost_usd=cost,
        reason_for_fallback=error,
    )
    provider_envelope["statuses"] = statuses
    details = sanitize_details({"provider_envelope": provider_envelope})

    if error == "exa_contents_status_gated":
        raise AuthError("Exa crawl gated", details=details)
    if error == "exa_contents_status_network":
        raise NetworkError("Exa crawl network failed", details=details)
    raise ProviderError("Exa crawl failed", details=details)


def _classify_crawl_status_failure(statuses: Any) -> tuple[str, int | None] | None:
    status_items: list[Any]
    if isinstance(statuses, list):
        status_items = statuses
    else:
        status_items = [statuses]

    saw_provider_error: int | None = None
    for item in status_items:
        status_code = _status_code_from_item(item)
        text = _status_text_from_item(item)
        if status_code is None and not any(token in text for token in _STATUS_ERROR_TOKENS):
            continue
        if status_code == 401:
            return "exa_contents_status_gated", status_code
        if any(token in text for token in _GATE_STATUS_TOKENS):
            return "exa_contents_status_gated", status_code
        if status_code in {408} or any(token in text for token in _NETWORK_STATUS_TOKENS):
            return "exa_contents_status_network", status_code
        if status_code is not None and status_code >= 400:
            return "exa_contents_status_4xx" if status_code < 500 else "exa_contents_status_5xx", status_code
        saw_provider_error = status_code

    if saw_provider_error is not None or status_items:
        has_error_text = any(
            any(token in _status_text_from_item(item) for token in _STATUS_ERROR_TOKENS)
            for item in status_items
        )
        if has_error_text:
            return "exa_contents_status_error", saw_provider_error
    return None


def _status_code_from_item(item: Any) -> int | None:
    if not isinstance(item, dict):
        return None
    for key in ("statusCode", "status_code", "httpStatus", "http_status", "http", "code"):
        raw = item.get(key)
        if isinstance(raw, int):
            return raw
        if isinstance(raw, str) and raw.isdigit():
            return int(raw)
    raw_status = item.get("status")
    if isinstance(raw_status, int):
        return raw_status
    if isinstance(raw_status, str) and raw_status.isdigit():
        return int(raw_status)
    return None


def _status_text_from_item(item: Any) -> str:
    if isinstance(item, dict):
        parts = [
            str(value)
            for key, value in item.items()
            if key not in {"url", "id"} and value is not None
        ]
        return " ".join(parts).lower()
    return str(item).lower()


def _render_partial_markdown(provider_envelope: dict[str, Any]) -> str:
    lines = [
        "# Research Provider Results",
        "",
        f"- status: {provider_envelope.get('status')}",
        f"- primary_engine: {provider_envelope.get('primary_engine')}",
        f"- query: {provider_envelope.get('meta', {}).get('query', '')}",
        "",
        "## Sources",
    ]
    results = provider_envelope.get("results", [])
    if not isinstance(results, list) or not results:
        lines.append("")
        lines.append("_No sources returned._")
        return "\n".join(lines) + "\n"

    for index, result in enumerate(results, start=1):
        if not isinstance(result, dict):
            continue
        title = result.get("title") or result.get("url") or f"Source {index}"
        url = result.get("url") or ""
        lines.extend(["", f"{index}. {title}", f"   {url}"])
    return "\n".join(lines) + "\n"


def _render_visual_ocr_partial_markdown(ocr_envelope: dict[str, Any]) -> str:
    provenance = ocr_envelope.get("provenance", {})
    lines = [
        "# Visual OCR Review Required",
        "",
        "This is non-canonical OCR recovery from a supplied page image. Review before quoting or reuse.",
        "",
        f"- status: {ocr_envelope.get('status')}",
        f"- url: {ocr_envelope.get('url', '')}",
        f"- source_fetch_status: {provenance.get('source_fetch_status', '')}",
        f"- source_fetch_reason: {provenance.get('source_fetch_reason', '')}",
        f"- captured_at: {provenance.get('captured_at', '')}",
        f"- ocr_confidence: {ocr_envelope.get('ocr_confidence', '')}",
        "",
        "## Visible Headings",
    ]
    headings = ocr_envelope.get("visible_headings", [])
    if isinstance(headings, list) and headings:
        for heading in headings:
            lines.append(f"- {heading}")
    else:
        lines.extend(["", "_No headings recovered._"])

    lines.extend(["", "## OCR Text", ""])
    body_text = str(ocr_envelope.get("body_text_visual_ocr") or "").strip()
    if body_text:
        lines.append(body_text)
    else:
        lines.append("_No OCR text recovered._")
    return "\n".join(lines) + "\n"
