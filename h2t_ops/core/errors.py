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


# The remedy for a missing runtime dependency, in one place because it was wrong in six.
#
# Every one of them said `pip install <package>`, and `h2t-ops` runs from a uv tool
# environment which ships without pip — measured 2026-08-27:
# `~/.local/share/uv/tools/h2t-ops/bin/python -m pip` answers "No module named pip".
# So the instruction fired at the moment of failure and could not be followed there.
#
# The second half said "(or run /h2t-core:setup)", a slash command inside Claude Code,
# offered to somebody reading a traceback in a terminal.
#
# And all six named packages that pyproject already declares and that are installed.
# A missing one is a broken install, not an absent extra, so the remedy is to repair the
# install rather than to add a package to it.
def broken_install_hint(*packages: str) -> str:
    """Name what is missing, then how to repair the install it is missing from."""
    named = " ".join(packages)
    return (
        f"{named} is declared in pyproject, so a missing one means a broken install "
        "rather than an absent extra. Repair it: "
        "uv tool install --editable <h2t-skills checkout>. `pip` is unavailable here — "
        "the uv tool environment ships without it; for one package use "
        f"`uv pip install --python <the h2t-ops interpreter> {named}`."
    ).strip()


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
