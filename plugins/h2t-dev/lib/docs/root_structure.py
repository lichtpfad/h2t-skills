"""Root structure validation for docs-lint project-layer (v1 — deterministic, no LLM)."""
from __future__ import annotations
import fnmatch
from pathlib import Path

STANDARD_ALLOWLIST: frozenset[str] = frozenset({
    # VCS
    ".git", ".gitignore", ".gitattributes", ".github",
    # Agent/tool config
    ".claude", ".editorconfig", ".h2t",
    # Standard project dirs (required or near-universal)
    "docs", "data", "src", "tests", "test", "scripts", "assets",
    "dist", "build", "lib", "plugins", "tools", "evals", "hooks",
    # Tool config files required by check_structure / docs-lint itself
    ".pymarkdown.yaml", ".vale.ini",
    # Project docs
    "README.md", "CLAUDE.md", "CHANGELOG.md", "LICENSE", "TODOS.md",
    "docs-lint-plan.yaml",
    # Python
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "uv.lock", ".pytest_cache", "__pycache__",
    # Node
    "package.json", "package-lock.json", "pnpm-lock.yaml", "node_modules",
    ".prettierrc", ".prettierrc.json", ".eslintrc.json",
    "tsconfig.json", "tsconfig.base.json",
    # Rust / Go
    "Cargo.toml", "go.mod",
    # Build / scripts
    "Makefile", "Dockerfile", "docker-compose.yml", "setup.sh",
    # Superpowers / Claude / tool state dirs
    ".worktrees", ".superpowers", ".claude-plugin",
    ".gstack", ".playwright-mcp", ".artifacts",
    # Misc
    ".env.example",
})

TEMP_PATTERNS: tuple[str, ...] = (
    "*.tmp", "*.log", "session_*.txt", "full_messages.txt",
    "cryo_*.txt", "*_analysis.txt", "*_summary.txt",
)

# Items already reported by check_repo_root — skip to avoid duplicate findings.
_LEGACY_BANNED: frozenset[str] = frozenset({"temp", "old", "backup", "tmp", "archive_old"})

_ALWAYS_SKIP: frozenset[str] = frozenset({
    ".git", ".venv", "venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", "node_modules", ".ruff_cache", ".vscode", ".idea",
})

# Glob patterns for items that are always build/tool artifacts — checked with fnmatch.
_ALWAYS_SKIP_GLOBS: tuple[str, ...] = ("*.egg-info", "*.dist-info")


def check_root_structure(
    rp: Path,
    template: str | None = None,
    custom_root_dirs: list[str] | None = None,
) -> list[dict]:
    """Return findings for root items not in allowlist.

    Severity:
    - warn  → matches a TEMP_PATTERNS glob (temp file, should be gitignored)
    - info  → unknown item (may be intentional — add to custom_root_dirs)
    """
    from docs.reporter import finding as make_finding
    from docs.project_types import PROJECT_TYPES

    allowed: set[str] = set(STANDARD_ALLOWLIST)
    if template:
        spec = PROJECT_TYPES.get(template)
        if spec:
            allowed.update(spec.get("root_dirs", []))
    allowed.update(custom_root_dirs or [])

    findings: list[dict] = []
    for item in sorted(rp.iterdir()):
        name = item.name
        if name in _ALWAYS_SKIP:
            continue
        if any(fnmatch.fnmatch(name, pat) for pat in _ALWAYS_SKIP_GLOBS):
            continue
        if name.lower() in _LEGACY_BANNED:
            continue
        if name in allowed:
            continue

        rel = name + ("/" if item.is_dir() else "")
        is_temp = any(fnmatch.fnmatch(name, pat) for pat in TEMP_PATTERNS)
        if is_temp:
            findings.append(make_finding(
                "root_structure", "warn", rel,
                f"temp file at root: {name} — add pattern to .gitignore",
            ))
        else:
            findings.append(make_finding(
                "root_structure", "info", rel,
                f"unknown root item: {name} — add to custom_root_dirs in docs-lint.yaml if intentional",
            ))
    return findings


def check_root_readmes(rp: Path, template: str) -> list[dict]:
    """Return info findings for template root_dirs missing a README.md.

    Only checks dirs that actually exist on disk — missing dirs are
    already reported by check_project_structure_typed.
    """
    from docs.reporter import finding as make_finding
    from docs.project_types import PROJECT_TYPES

    spec = PROJECT_TYPES.get(template)
    if spec is None:
        return []

    findings: list[dict] = []
    for d in spec.get("root_dirs", []):
        dir_path = rp / d
        if not dir_path.is_dir():
            continue
        if not (dir_path / "README.md").exists():
            findings.append(make_finding(
                "root_readmes", "info", f"{d}/README.md",
                f"missing README.md in root dir: {d}/",
            ))
    return findings
