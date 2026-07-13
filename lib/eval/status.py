"""Read-only eval status — offline-safe, no writes, no network."""
from pathlib import Path

# Module-qualified access (not `from .session import ...`) so tests that
# monkeypatch `session._sdk_available` reach the call inside get_status.
import lib.eval.session as sess


def _mode_source(env) -> str:
    raw = (env.get("H2T_EVALS_MODE") or "").strip().lower()
    if raw in ("off", "local", "push", "auto"):
        return "env"
    if env.get("H2T_EVALS_ENABLED") == "1":
        return "legacy"
    return "default"


def _hint(mode: str, sdk: bool, token: bool) -> str:
    if mode == "push":
        return "push active"
    if mode == "local":
        return "local-only (H2T_EVALS_MODE=local)"
    missing = []
    if not sdk:
        missing.append("SDK not importable (see h2t-evals#99)")
    if not token:
        missing.append("H2T_EVALS_TOKEN unset")
    if missing:
        return (
            "auto→off: "
            + "; ".join(missing)
            + ". Provide both to auto-activate push, or set H2T_EVALS_MODE=local."
        )
    return "off (explicit)"


def get_status(env=None, evals_root=None) -> dict:
    # Default view merges ~/.dor/secrets.env (env-wins) so the operator sees the
    # same creds the runtime push path resolves — else status reads 'off' while
    # real runs push (#321). Explicit env (tests, callers) is used verbatim.
    env = env if env is not None else sess._load_secrets()
    mode = sess.resolve_mode(env)
    sdk = sess._sdk_available()
    token = bool(env.get("H2T_EVALS_TOKEN"))
    root = Path(evals_root) if evals_root else Path.home() / ".h2t" / "evals"
    try:
        # Session records live only at <root>/<skill>/sessions/*.json.
        count = sum(1 for _ in root.glob("*/sessions/*.json")) if root.exists() else 0
    except OSError:
        count = 0
    return {
        "mode": mode,
        "source": _mode_source(env),
        "sdk_available": sdk,
        "token_present": token,
        "service_url": env.get("H2T_EVALS_SERVICE_URL", "http://127.0.0.1:8088"),
        "local_dir": str(root),
        "session_count": count,
        "hint": _hint(mode, sdk, token),
    }
