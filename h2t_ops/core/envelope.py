"""Universal command result/error envelope (spec §6)."""
from __future__ import annotations

from typing import Any

from h2t_ops.core.errors import H2TError


def success_envelope(provider: str, result: Any) -> dict[str, Any]:
    return {"ok": True, "provider": provider, "result": result}


def error_envelope(provider: str, exc: BaseException) -> dict[str, Any]:
    kind = exc.kind if isinstance(exc, H2TError) else "provider"
    hint = exc.hint if isinstance(exc, H2TError) else None
    return {"ok": False, "provider": provider,
            "error": {"type": kind, "message": str(exc), "hint": hint}}
