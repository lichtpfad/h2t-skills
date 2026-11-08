"""Shared utilities for h2t-dev documentation skills."""

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from h2t_ops.core import paths as _paths
from h2t_ops.resources import resource_dir


def _dev_root() -> Path:
    """Where sibling h2t repositories live (#434).

    The default was a drive-letter dev root, right on exactly one machine and wrong everywhere
    else — including a Mac, where checkouts are under ~/Projects. Resolution
    order, each step failing over to the next:

    1. `H2T_DEV_ROOT` — the explicit answer, unchanged and still first.
    2. Derived: if this file sits inside a checkout (a `pyproject.toml` three levels up),
       sibling repositories are that checkout's parent. Correct on both machines with no
       configuration — `~/Projects/h2t-skills` gives `~/Projects`.
    3. `~/dev` — the conventional guess, used only when running from the installed plugin
       cache, where the checkout layout is absent and nothing better is knowable.

    Step 2 is why this is a function and not a constant: a constant would have to pick one
    of the three at import time, and the cache case cannot be distinguished then.
    """
    override = os.environ.get("H2T_DEV_ROOT")
    if override:
        return Path(override)
    checkout = Path(__file__).resolve().parents[3]
    if (checkout / "pyproject.toml").is_file():
        return checkout.parent
    return _paths.home() / "dev"


DEV_ROOT = _dev_root()



def standards_dir() -> Path:
    """Where the eight STANDARDS_FILES live (#439).

    Bundled first. Until this change the only answer was `DEV_ROOT/docs/standards`, a
    directory that exists on exactly one machine — and not on a Mac, where
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
    return resource_dir("docs") / "standards"

def _manifest() -> list[str]:
    """Repository names from the operator's repo mapping (#548 Task 15, #581).

    The mapping lists every repository this user has, keyed by repository name, which is
    exactly what the manifest is. It is asked of the index, the one parser of the ontology.

    There is no fallback list. The one that stood here named sixteen fixed
    repositories, so a stranger's `docs-sync-labels --apply` wrote into repositories that
    were never theirs. Without a mapping the answer is a ConfigError that says how to give
    one — or to name `owner/repo` on the command line instead.
    """
    import sqlite3

    from h2t_ops.core.errors import ConfigError, H2TError
    from h2t_ops.lifecycle import index
    hint = "register repositories in your repo mapping (see `h2t-ops settings list`, key repos), or pass owner/repo"
    try:
        mappings = index.ontology()[0].get("mappings")
    except (H2TError, OSError, sqlite3.Error) as exc:
        raise ConfigError(f"the repo mapping cannot be read: {exc}", hint=hint) from exc
    if not isinstance(mappings, dict) or not mappings:
        raise ConfigError("no repositories are registered in the repo mapping", hint=hint)
    return sorted(str(k) for k in mappings)


_REMOTE = re.compile(r"^(?:https?://[^/]+/|git@[^:]+:|ssh://git@[^/]+/)([^/]+)/(.+?)(?:\.git)?/?$")


def target(arg: str | None, repo_root: Path) -> str:
    """`owner/repo` for a GitHub call, without ever naming an owner of our own (#581).

    `owner/repo` is taken as given. A bare name needs `github.owner`; the remote of
    `repo_root` is deliberately not consulted for it, because that checkout is another
    repository and its owner is not the answer for a name. `None` means the current
    checkout, which is the one case its own origin is right.
    """
    from h2t_ops.core import settings
    from h2t_ops.core.errors import ConfigError

    if arg and "/" in arg:
        return arg
    if arg:
        owner = settings.resolve("github.owner").value
        if not owner:
            settings.require("github.owner")  # raises ConfigError naming the env var and file
        return f"{owner}/{arg}"
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        out = None
    m = _REMOTE.match(out.stdout.strip()) if out is not None and out.returncode == 0 else None
    if not m:
        raise ConfigError(
            f"{repo_root} has no GitHub remote named origin",
            hint="pass owner/repo, or add the remote: git remote add origin <url>",
        )
    return f"{m.group(1)}/{m.group(2)}"


def exits_on_config_error(fn):
    """Entry-point guard: a typed error leaves as its exit code with the hint, not a traceback."""
    import functools

    from h2t_ops.core.errors import H2TError, exit_code_for

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except H2TError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            if exc.hint:
                print(f"  hint: {exc.hint}", file=sys.stderr)
            sys.exit(exit_code_for(exc))

    return wrapper


class _Manifest(Sequence):
    """REPO_MANIFEST, read on first use rather than at import. The index it comes from is
    built in state/ on first open; at import every process that loads the docs tools would
    build it, whether or not it ever asks for the manifest."""

    def __init__(self) -> None:
        self._names: list[str] | None = None

    def _get(self) -> list[str]:
        if self._names is None:
            self._names = _manifest()
        return self._names

    def __getitem__(self, i):
        return self._get()[i]

    def __len__(self) -> int:
        return len(self._get())

    def __contains__(self, name) -> bool:
        """Membership is a question about names, and "no mapping" answers it: not known.
        The walks that ask it (which directory is a repository?) must not die on a
        machine that has registered nothing."""
        from h2t_ops.core.errors import ConfigError
        try:
            return name in self._get()
        except ConfigError:
            return False


REPO_MANIFEST = _Manifest()

REQUIRED_CORE_DIRS = [
    "docs/superpowers/specs",
    "docs/superpowers/plans",
    "docs/adr",
    "docs/reports",
]

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
    REPO_MANIFEST — sixteen fixed repository names. Measured 2026-08-27: inside a
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


def ensure_dir(writer, rel_dir: str) -> bool:
    """rel_dir with a .gitkeep, through the command's store.repo writer; False if it exists."""
    if (writer.root / rel_dir).exists():
        return False
    writer.create(f"{rel_dir}/.gitkeep", "")
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
