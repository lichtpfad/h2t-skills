"""Universal command result/error envelope (spec §6)."""
from __future__ import annotations

from typing import Any

from h2t_ops.core.errors import H2TError


def success_envelope(provider: str, result: Any) -> dict[str, Any]:
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
