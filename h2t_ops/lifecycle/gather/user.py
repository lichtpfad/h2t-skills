"""User context gathering — about-me files, domain-dependent deep context."""

from pathlib import Path

from h2t_ops.core import paths, settings


def gather_user_context(
    domain: str | None = None,
    config_root: str | None = None,
) -> dict:
    """Gather user context files.

    Always includes core.md path.
    Domain-specific files are those `context.by_domain` names in user.yaml (none by default).

    Returns paths only — caller reads content if needed (progressive disclosure).
    """
    root = Path(config_root) if config_root else paths.config_dir()
    about_me = root / "about-me"

    core_path = about_me / "core.md"
    available = [str(f) for f in about_me.glob("*.md")] if about_me.exists() else []

    result = {
        "core_path": str(core_path) if core_path.exists() else "",
        "language": settings.resolve("language").value,
        "available_contexts": available,
        "deep_paths": [],
    }

    if domain:
        extra_files = (settings.resolve("context.by_domain").value or {}).get(domain, [])
        for filename in extra_files:
            path = about_me / filename
            if path.exists():
                result["deep_paths"].append(str(path))

    strategy = settings.resolve("context.strategy").value
    if strategy:
        strategy_path = root / strategy
        if strategy_path.exists():
            result["strategy_path"] = str(strategy_path)

    return result
