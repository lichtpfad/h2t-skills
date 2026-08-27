"""Shared utilities for h2t-dev documentation skills."""

import os
import re
import shutil
import subprocess
from pathlib import Path


def _dev_root() -> Path:
    """Where sibling h2t repositories live (#434).

    The default was `C:/dev`, which is right on exactly one machine and wrong everywhere
    else — including the author's Mac, where checkouts are under ~/Projects. Resolution
    order, each step failing over to the next:

    1. `H2T_DEV_ROOT` — the explicit answer, unchanged and still first.
    2. Derived: if this file sits inside a checkout (a `pyproject.toml` four levels up),
       sibling repositories are that checkout's parent. Correct on both machines with no
       configuration — `C:/dev/h2t-skills` gives `C:/dev`, `~/Projects/h2t-skills` gives
       `~/Projects`.
    3. `~/dev` — the conventional guess, used only when running from the installed plugin
       cache, where the checkout layout is absent and nothing better is knowable.

    Step 2 is why this is a function and not a constant: a constant would have to pick one
    of the three at import time, and the cache case cannot be distinguished then.
    """
    override = os.environ.get("H2T_DEV_ROOT")
    if override:
        return Path(override)
    checkout = Path(__file__).resolve().parents[4]
    if (checkout / "pyproject.toml").is_file():
        return checkout.parent
    return Path.home() / "dev"


DEV_ROOT = _dev_root()

# The plugin root: this file is plugins/h2t-dev/lib/docs/common.py.
PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def standards_dir() -> Path:
    """Where the eight STANDARDS_FILES live (#439).

    Bundled first. Until this change the only answer was `DEV_ROOT/docs/standards`, a
    directory that exists on exactly one machine — and not the author's Mac, where
    `lint.py h2t-skills` printed eight `FAIL: missing ...` lines while all eight files sat
    in a sibling repository. On a stranger's machine nothing of that constellation exists,
    so the skill reported their tree as violating standards they could not read.

    `H2T_DEV_ROOT/docs/standards` still wins when the operator sets it: someone who keeps
    their own standards keeps pointing at them, and the bundled copy is the seed they
    started from rather than a rule they cannot escape. Resolved per call, not at import,
    so the override is honoured by a process that sets it after this module loads.

    Same precedent as docs-sync-labels, which shipped labels.json beside its script and
    reached for DEV_ROOT only as a fallback.
    """
    override = os.environ.get("H2T_DEV_ROOT")
    if override:
        candidate = Path(override) / "docs" / "standards"
        if candidate.is_dir():
            return candidate
    return PLUGIN_ROOT / "references" / "standards"

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


def excluded_predicate(repo_root: Path, exclude_dirs: list[str] | None):
    """Build `is_excluded(path)` for the config's `exclude_dirs`.

    One definition for every check. It used to live twice — in the orphan walk
    and the naming walk — and the five other walks over docs/ simply did not
    have it, so `exclude_dirs` reached two checks out of seven and a frozen tree
    kept producing findings from the ones it did not reach (#271).
    """
    excluded = {(repo_root / d).resolve() for d in (exclude_dirs or [])}

    def is_excluded(p: Path) -> bool:
        if not excluded:
            return False
        rp = p.resolve()
        return any(rp == ex or ex in rp.parents for ex in excluded)

    return is_excluded
