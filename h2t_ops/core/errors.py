"""Typed error hierarchy + exit-code mapping (spec §5)."""
from __future__ import annotations


class H2TError(Exception):
    """Base. Carries an optional install/fix hint and public diagnostic details.
    Always raise a typed subclass; do not raise H2TError directly."""
    kind: str = "provider"

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        details: object | None = None,
    ) -> None:
        super().__init__(message)
        self.hint = hint
        self.details = details


class UsageError(H2TError):
    kind = "usage"


class ConfigError(H2TError):
    kind = "config"


class AuthError(H2TError):
    kind = "auth"


class ProviderError(H2TError):
    kind = "provider"


class NotFoundError(H2TError):
    kind = "not_found"


class NetworkError(H2TError):
    kind = "network"


EXIT_CODES: dict[str, int] = {
    "ok": 0, "provider": 1, "usage": 2,
    "config": 3, "auth": 4, "not_found": 5, "network": 6,
}


def exit_code_for(exc: BaseException) -> int:
    """Map an exception to its exit code. Unknown → 1 (provider/runtime)."""
    if isinstance(exc, H2TError):
        return EXIT_CODES.get(exc.kind, EXIT_CODES["provider"])
    return 1
