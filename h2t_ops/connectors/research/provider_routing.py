from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from h2t_ops.core.errors import UsageError


CAPABILITIES = {
    "preflight",
    "search",
    "answer",
    "similar",
    "crawl",
    "author",
    "fetch",
    "visual_ocr",
    "research",
}


@dataclass(frozen=True)
class ProviderCapability:
    provider: str
    capability: str
    required_secrets: tuple[str, ...] = ()
    optional_secrets: tuple[str, ...] = ()
    priority: int = 100
    notes: str = ""


PROVIDER_CAPABILITIES: tuple[ProviderCapability, ...] = (
    ProviderCapability("exa", "preflight", required_secrets=("EXA_API_KEY",), priority=10),
    ProviderCapability("exa", "search", required_secrets=("EXA_API_KEY",), priority=10),
    ProviderCapability("exa", "answer", required_secrets=("EXA_API_KEY",), priority=10),
    ProviderCapability("exa", "similar", required_secrets=("EXA_API_KEY",), priority=10),
    ProviderCapability("exa", "crawl", required_secrets=("EXA_API_KEY",), priority=10),
    ProviderCapability("exa", "author", required_secrets=("EXA_API_KEY",), priority=10),
    ProviderCapability("exa", "research", required_secrets=("EXA_API_KEY",), priority=10),
    ProviderCapability("direct", "fetch", priority=10),
    ProviderCapability(
        "jina",
        "fetch",
        optional_secrets=("JINA_API_KEY",),
        priority=20,
        notes="Jina Reader can run without a key in the current fetch ladder.",
    ),
    ProviderCapability("youtube_transcript", "fetch", priority=30),
    ProviderCapability("visual_ocr", "visual_ocr", priority=10),
)


def _secret_available(name: str) -> bool:
    try:
        from h2t_ops.connectors.research.client import resolve_secret

        return bool(resolve_secret(name))
    except Exception:
        return False


def _row(capability: ProviderCapability) -> dict[str, Any]:
    missing_required = [
        name for name in capability.required_secrets if not _secret_available(name)
    ]
    missing_optional = [
        name for name in capability.optional_secrets if not _secret_available(name)
    ]
    configured = not missing_required
    if missing_required:
        reason = "missing_required_secret"
    elif missing_optional:
        reason = "available_optional_secret_missing"
    else:
        reason = "available"
    return {
        "provider": capability.provider,
        "capability": capability.capability,
        "configured": configured,
        "required_secrets": list(capability.required_secrets),
        "optional_secrets": list(capability.optional_secrets),
        "missing_secrets": missing_required,
        "optional_missing_secrets": missing_optional,
        "priority": capability.priority,
        "reason": reason,
        "notes": capability.notes,
    }


def provider_status(*, capability: str | None = None) -> dict[str, Any]:
    if capability is not None and capability not in CAPABILITIES:
        raise UsageError(f"unknown research capability: {capability}")
    rows = [
        _row(item)
        for item in sorted(
            PROVIDER_CAPABILITIES,
            key=lambda item: (item.capability, item.priority, item.provider),
        )
        if capability is None or item.capability == capability
    ]
    return {
        "kind": "research_provider_status",
        "capability": capability,
        "providers": rows,
    }


def select_route(capability: str, *, provider: str | None = None) -> dict[str, Any]:
    if capability not in CAPABILITIES:
        raise UsageError(f"unknown research capability: {capability}")
    rows = provider_status(capability=capability)["providers"]
    if provider:
        rows = [row for row in rows if row["provider"] == provider]
        if not rows:
            raise UsageError(
                f"research provider {provider!r} does not support capability {capability!r}"
            )
    configured = [row for row in rows if row["configured"]]
    if not configured:
        missing = sorted(
            {
                secret
                for row in rows
                for secret in row.get("missing_secrets", [])
            }
        )
        hint = (
            f"Set {', '.join(missing)} in env, H2T_SECRETS_FILE, "
            "~/.dor/secrets/secrets.env, or ~/.dor/secrets.env."
            if missing
            else "Enable or configure a provider for this capability."
        )
        raise UsageError(
            f"no configured research provider for capability: {capability}",
            hint=hint,
        )
    selected = sorted(configured, key=lambda row: (row["priority"], row["provider"]))[0]
    return {
        "kind": "research_provider_route",
        "capability": capability,
        "requested_provider": provider,
        "selected_provider": selected["provider"],
        "configured": True,
        "route": selected,
        "candidates": rows,
    }
