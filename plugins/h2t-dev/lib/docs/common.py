"""Shared utilities for h2t-dev documentation skills."""

import os
import re
import shutil
import subprocess
from pathlib import Path

DEV_ROOT = Path(os.environ.get("H2T_DEV_ROOT", "C:/dev"))

REPO_MANIFEST = [
    "h2t-ai", "h2t-business", "h2t-client", "h2t-content", "h2t-dcc",
    "h2t-evals", "h2t-factory", "h2t-graphs", "h2t-landings", "h2t-skills",
    "h2t-snap", "h2t-staging", "h2t-tools", "h2t-transcription",
    "h2t-vision", "h2t-voice",
]

TIER_A = ["h2t-evals", "h2t-transcription", "h2t-graphs", "h2t-ai", "h2t-vision", "h2t-skills"]
TIER_B = ["h2t-factory", "h2t-snap", "h2t-staging", "h2t-landings", "h2t-dcc", "h2t-voice"]
TIER_C = ["h2t-business", "h2t-client", "h2t-content", "h2t-tools"]

REQUIRED_CORE_DIRS = [
    "docs/superpowers/specs",
    "docs/superpowers/plans",
    "docs/adr",
    "docs/reports",
]

# Extra dirs allowed per repo — not flagged by check_legacy_dirs or structure checks
REPO_EXTRA_DIRS: dict[str, list[str]] = {
    "h2t-evals":         ["ops", "contracts"],
    "h2t-transcription": ["methodology", "diagrams"],
    "h2t-vision":        ["presentation"],
}

STANDARDS_FILES = [
    "naming-conventions.md", "git-naming-conventions.md",
    "documentation-structure.md", "code-organization.md",
    "api-contracts.md", "adr-process.md", "linting.md", "labels.json",
]

FRONTMATTER_RULES = {
    "superpowers/specs": ["title", "status", "owner", "date", "milestone"],
    "superpowers/plans": ["title", "status", "date", "milestone"],
    "adr": ["title", "status", "date"],
}

GH = shutil.which("gh") or "C:/Program Files/GitHub CLI/gh.exe"


def repo_path(name: str) -> Path:
    return DEV_ROOT / name


def git_add_commit(repo: Path, paths: list[str], message: str) -> bool:
    for p in paths:
        subprocess.run(["git", "-C", str(repo), "add", p], check=True)
    result = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--quiet"],
        capture_output=True,
    )
    if result.returncode == 0:
        return False
    subprocess.run(["git", "-C", str(repo), "commit", "-m", message], check=True)
    return True


def ensure_dir(path: Path, gitkeep: bool = True) -> bool:
    if path.exists():
        return False
    path.mkdir(parents=True, exist_ok=True)
    if gitkeep:
        (path / ".gitkeep").touch()
    return True


def print_header(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def parse_frontmatter(text: str) -> dict | None:
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        import yaml
        return yaml.safe_load(parts[1]) or {}
    except ImportError:
        # yaml not available — use basic regex for simple key: value pairs only
        fm: dict = {}
        for line in parts[1].strip().splitlines():
            m = re.match(r"^(\w+):\s*([^[\n{]+)$", line)
            if m:
                fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
        return fm if fm else None
    except Exception:
        return None
