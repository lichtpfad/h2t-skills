"""User context gathering — about-me files, domain-dependent deep context."""

from pathlib import Path

DOMAIN_CONTEXT_MAP = {
    "personal": ["psychology.md"],
    "personal-os": ["psychology.md"],
    "hou2touch": [],
    "crypto": [],
    "art": [],
}


def gather_user_context(
    domain: str | None = None,
    config_root: str | None = None,
) -> dict:
    """Gather user context files.

    Always includes core.md path.
    Domain-specific files added based on DOMAIN_CONTEXT_MAP.

    Returns paths only — caller reads content if needed (progressive disclosure).
    """
    root = Path(config_root) if config_root else Path.home() / ".h2t" / "config"
    about_me = root / "about-me"

    core_path = about_me / "core.md"
    available = [str(f) for f in about_me.glob("*.md")] if about_me.exists() else []

    core_content = ""
    if core_path.exists():
        try:
            core_content = core_path.read_text(encoding="utf-8")
        except Exception:
            pass

    result = {
        "core_path": str(core_path) if core_path.exists() else "",
        "core_content": core_content,
        "language": "ru",
        "available_contexts": available,
        "deep_paths": [],
    }

    if domain:
        extra_files = DOMAIN_CONTEXT_MAP.get(domain, [])
        for filename in extra_files:
            path = about_me / filename
            if path.exists():
                result["deep_paths"].append(str(path))

    strategy_path = root / "docs" / "strategy-summary.md"
    if strategy_path.exists():
        result["strategy_path"] = str(strategy_path)

    return result
