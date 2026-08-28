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

# The author's sixteen, kept only as the answer when the operator has no registry of
# their own. Nothing here should depend on a stranger having these repositories.
_BUNDLED_MANIFEST = [
    "h2t-ai", "h2t-business", "h2t-client", "h2t-content", "h2t-dcc",
    "h2t-evals", "h2t-factory", "h2t-graphs", "h2t-landings", "h2t-skills",
    "h2t-snap", "h2t-staging", "h2t-tools", "h2t-transcription",
    "h2t-vision", "h2t-voice",
]


def _manifest() -> list[str]:
    """Repository names, from the operator's registry when there is one.

    `~/.h2t/config/repo-mapping.yaml` already lists every repository this user has —
    31 entries here against the bundled 16 — and it is keyed by repository name, which
    is exactly what the manifest is. Reading it means a stranger's repositories are
    known to the tooling and the author's are not assumed.

    The bundled list remains the fallback rather than an empty one: dropping to nothing
    would silently turn off cross-repo behaviour for the machine that has the file
    missing for an unrelated reason.
    """
    path = Path.home() / ".h2t" / "config" / "repo-mapping.yaml"
    try:
        import yaml
    except ImportError:
        return list(_BUNDLED_MANIFEST)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return list(_BUNDLED_MANIFEST)
    mappings = data.get("mappings")
    if not isinstance(mappings, dict) or not mappings:
        return list(_BUNDLED_MANIFEST)
    return sorted(str(k) for k in mappings)


REPO_MANIFEST = _manifest()

REQUIRED_CORE_DIRS = [
    "docs/superpowers/specs",
    "docs/superpowers/plans",
    "docs/adr",
    "docs/reports",
]

# Extra dirs allowed per repo. Superseded by the `extra_doc_dirs` key in a repository's
# own docs-lint config, which is where a repository can answer for itself; this dict is
# the answer for the three that predate the key.
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

# `issue` is what makes `status` checkable. Written once by the generator and never again
# by anything that knows whether the work happened, `status` is unfalsifiable: no check can
# call a value wrong, because there is nothing to compare it against. Measured over the 42
# legacy documents reviewed by hand 2026-08-26 — 41 carried `status: draft`, 29 had shipped
# in full and 10 in part, and the field had never moved (#421).
#
# Accepted values: an issue number, or the literal `none` paired with a `reason:` line.
# ADRs are unaffected — they record a decision, not work with a state.
FRONTMATTER_RULES = {
    "superpowers/specs": ["title", "status", "owner", "date", "milestone", "issue"],
    "superpowers/plans": ["title", "status", "date", "milestone", "issue"],
    "adr": ["title", "status", "date"],
}

LINKED_DOC_DIRS = ("docs/superpowers/plans", "docs/superpowers/specs")


def issue_link_problem(fields: dict) -> str | None:
    """One rule, one place: what makes a plan's `issue` an address rather than a key.

    Returns a message, or None when the document is linked. Presence of the key is not
    enough — `issue: ""` is what `fix-safe --only=frontmatter` leaves behind after the
    field was introduced, and it is exactly the state the checks exist to catch (#421).

    Callers: docs-lint's `check_issue_link` and the CI ratchet. The PreToolUse hook in
    h2t-core carries its own copy because a plugin cannot import another plugin's lib;
    keep the two in step.
    """
    raw = str(fields.get("issue", "")).strip().strip('"').strip("'")
    if not raw:
        return "no issue — use a number, or 'none' with a reason"
    if raw.lower() == "none":
        reason = str(fields.get("reason", "")).strip().strip('"').strip("'")
        return None if reason else "issue is 'none' without a reason"
    if not raw.lstrip("#").isdigit():
        return f"issue {raw!r} is neither a number nor 'none'"
    return None


# `gh` or nothing. The fallback here used to name a Windows install directory, so on a
# machine without gh the callers received a path that cannot exist and failed on exec
# rather than on the missing tool.
GH = shutil.which("gh")


def repo_path(name: str) -> Path:
    return DEV_ROOT / name


def git_repo_root(start: Path | None = None) -> Path | None:
    """The repository containing `start`, from git rather than from a list of names.

    Callers used to walk up looking for a directory whose *name* appears in
    REPO_MANIFEST — sixteen of the author's repositories. Measured 2026-08-27: inside a
    repository that is not on that list, running from `docs/sub` resolved the repo root
    to `docs/sub`, so the linter treated a subdirectory as the whole repository. Not
    "some checks are off" — the wrong root, silently.

    Returns None when there is no repository or no git, which is a real answer and the
    caller decides what to do with it.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(start or Path.cwd()), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    path = out.stdout.strip()
    return Path(path) if path else None


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
