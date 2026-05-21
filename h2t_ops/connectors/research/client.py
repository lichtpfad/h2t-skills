"""Research connector helper substrate.

T2 intentionally contains only local helper plumbing: secret resolution,
artifact path/JSON helpers, details redaction, telemetry append, and an empty
ResearchClient facade. Provider calls land in later tasks.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from h2t_ops.core.errors import ConfigError

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
    "secret",
)
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_ENV_SECRET_RE = re.compile(
    r"\b(?:EXA_API_KEY|JINA_API_KEY)\s*=\s*([\"']?)[^\s\"']+\1",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(r"\bsecret_[A-Za-z0-9._-]+", re.IGNORECASE)
_AUTH_HEADER_RE = re.compile(
    r"\b(Authorization\s*:\s*)Bearer\s+[A-Za-z0-9._~+/=-]+",
    re.IGNORECASE,
)
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


def _sanitize_string(value: str) -> str:
    value = _AUTH_HEADER_RE.sub(r"\1" + REDACTED, value)
    value = _BEARER_RE.sub(f"Bearer {REDACTED}", value)
    value = _ENV_SECRET_RE.sub(
        lambda m: m.group(0).split("=", 1)[0] + "=" + REDACTED,
        value,
    )
    value = _SECRET_VALUE_RE.sub(REDACTED, value)
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


class ResearchClient:
    """Empty facade for later provider-backed research operations."""

    def __init__(self, *, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
