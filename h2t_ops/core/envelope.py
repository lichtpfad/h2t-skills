"""Universal command result/error envelope (spec §6)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from h2t_ops.core.errors import H2TError


@dataclass
class Paged:
    """A list result plus what the provider said about the rest of it.

    Handlers return this instead of a bare list when the provider can report
    truncation. Without it a full page is indistinguishable from a complete
    result, and every caller has to guess (#351).
    """

    items: list[Any]
    truncated: bool = False
    limit: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    # Human/md text when the connector has its own formatter; json ignores it.
    rendered: str | None = None

    def meta(self) -> dict[str, Any]:
        meta: dict[str, Any] = {"count": len(self.items), "truncated": self.truncated}
        if self.limit is not None:
            meta["limit"] = self.limit
        meta.update(self.extra)
        return meta


def success_envelope(provider: str, result: Any) -> dict[str, Any]:
    if isinstance(result, Paged):
        return {"ok": True, "provider": provider,
                "result": result.items, "meta": result.meta()}
    return {"ok": True, "provider": provider, "result": result}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def error_envelope(provider: str, exc: BaseException) -> dict[str, Any]:
    kind = exc.kind if isinstance(exc, H2TError) else "provider"
    hint = exc.hint if isinstance(exc, H2TError) else None
    error = {"type": kind, "message": str(exc), "hint": hint}
    if isinstance(exc, H2TError) and exc.details is not None:
        error["details"] = _json_safe(exc.details)
    return {"ok": False, "provider": provider, "error": error}
