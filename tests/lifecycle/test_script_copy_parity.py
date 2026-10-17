"""The package copies of the plugin scripts must not drift from their originals.

The console scripts run `h2t_ops/lifecycle/<copy>.py`, while most behavioural tests (and
the 3.x skills) still load the plugin originals. A fix landed in one and not the other
would pass every test that loads the wrong one. Task 12 deletes the originals and this test.

The differences a copy may carry are enumerated below as data, per pair: each `EDITS`
entry is an exact text replacement that must occur exactly once in the original. Imports
of the shared lib are rewritten by one rule, `IMPORT_PREFIX`. Anything else is drift.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "plugins" / "h2t-core" / "skills"
LIFECYCLE = ROOT / "h2t_ops" / "lifecycle"

# `from eval.x` / `from gather.x` / `from activity.x` -> `from h2t_ops.lifecycle.<same>`
IMPORT_PREFIX = (re.compile(r"^(\s*)from (eval|gather|activity)([. ])", re.M),
                 r"\1from h2t_ops.lifecycle.\2\3")

_GATHER_BOOTSTRAP = '''# lib/ is co-located in plugin cache root (4 levels up from this file).
# In dev/smoke-test mode, PLUGIN_ROOT/lib doesn't exist yet (before update-plugin.sh);
# fall back to repo_root/lib (PLUGIN_ROOT is plugins/h2t-core/ → repo is 2 levels up).
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_cache_lib = PLUGIN_ROOT / "lib"
_repo_lib = PLUGIN_ROOT.parent.parent / "lib"
for _lib in [_cache_lib, _repo_lib]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

'''
_WRITER_BOOTSTRAP = '''# lib/ path: cache root (4 levels up) or repo root (6 levels up) fallback
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_cache_lib = PLUGIN_ROOT / "lib"
_repo_lib = PLUGIN_ROOT.parent.parent / "lib"
for _lib in [_cache_lib, _repo_lib]:
    if _lib.exists():
        sys.path.insert(0, str(_lib))
        break

'''
_SCAFFOLD_TYPES = '''# lib path: source sibling plugins/h2t-dev/lib OR cache lichtpfad/h2t-dev/{latest}/lib
_SCAFFOLD_SCRIPT = Path(__file__).resolve()
_PLUGIN_ROOT_EARLY = _SCAFFOLD_SCRIPT.parents[3]
_H2T_DEV_LIB = _PLUGIN_ROOT_EARLY.parent / "h2t-dev" / "lib"  # source
if not _H2T_DEV_LIB.exists():
    # Cache: go up to lichtpfad/, find latest h2t-dev version
    _cache_base = _PLUGIN_ROOT_EARLY.parent.parent / "h2t-dev"
    if _cache_base.exists():
        _versions = sorted([p for p in _cache_base.iterdir() if p.is_dir()], reverse=True)
        for _v in _versions:
            if (_v / "lib").exists():
                _H2T_DEV_LIB = _v / "lib"
                break
if _H2T_DEV_LIB.exists() and str(_H2T_DEV_LIB) not in sys.path:
    sys.path.insert(0, str(_H2T_DEV_LIB))

try:
    from docs.project_types import PROJECT_TYPES, SCAFFOLD_TYPE_TO_TEMPLATE
    _PROJECT_TYPES_AVAILABLE = True
except ImportError:
    _PROJECT_TYPES_AVAILABLE = False
    PROJECT_TYPES = {}
    SCAFFOLD_TYPE_TO_TEMPLATE = {}
'''
_SCAFFOLD_TYPES_FROM_PACKAGE = '''from h2t_ops.lifecycle import plugin_script_anchor
from h2t_ops.tools.docs.project_types import PROJECT_TYPES, SCAFFOLD_TYPE_TO_TEMPLATE

# The project types ship in the package (h2t_ops.tools.docs). docs-init does not, and is
# still looked up in the h2t-dev plugin tree, anchored where the 3.x entry point found it.
_SCAFFOLD_SCRIPT = plugin_script_anchor(
    "skills/scaffold-project/scripts/scaffold_project.py", Path(__file__).resolve())
_PROJECT_TYPES_AVAILABLE = True
'''
_SYNC_LABELS_FROM_PLUGIN = '''    if _H2T_DEV_ROOT is None:
        return {"status": "skip", "reason": "h2t-dev plugin not found"}
    sync_script = _H2T_DEV_ROOT / "skills" / "docs-sync-labels" / "scripts" / "sync_labels.py"
    if not sync_script.exists():
        return {"status": "skip", "reason": "sync_labels script not found"}
    r = subprocess.run(
        [sys.executable, str(sync_script), repo_name, "--apply"],
'''
_SYNC_LABELS_FROM_PACKAGE = '''    r = subprocess.run(
        [sys.executable, "-m", "h2t_ops.tools.docs.sync_labels", repo_name, "--apply"],
'''

# copy -> (original, rewrite imports?, [(old, new), ...])
PAIRS = {
    "session_start.py": ("session-start/scripts/gather.py", True, [(_GATHER_BOOTSTRAP, "")]),
    "handoff.py": ("handoff/scripts/writer.py", True, [(_WRITER_BOOTSTRAP, "")]),
    "apply_registration.py": ("init-project/scripts/apply_registration.py", False, []),
    "project_audit_report.py": ("project-audit/scripts/report.py", False, []),
    # docs-lint is the package tool now (Task 10): no plugin tree to find it in.
    "project_audit_scan.py": ("project-audit/scripts/scan.py", False, [
        ('''    _self = Path(__file__).resolve()
    candidates = [
        _self.parents[3].parent / "h2t-dev" / "skills" / "docs-lint" / "scripts" / "lint.py",
        _self.parents[5] / "plugins" / "h2t-dev" / "skills" / "docs-lint" / "scripts" / "lint.py",
    ]
    lint_script = next((p for p in candidates if p.exists()), None)
    if lint_script is None:
        return None
    try:
        r = subprocess.run(
            [sys.executable, str(lint_script), "doctor", "--root", str(repo), "--json"],
''', '''    try:
        r = subprocess.run(
            [sys.executable, "-m", "h2t_ops.tools.docs.lint", "doctor", "--root", str(repo),
             "--json"],
'''),
    ]),
    # The project types and the label sync come from the package (Task 10); docs-init is
    # not in it, so the h2t-dev lookup stays — anchored where the 3.x entry point was.
    "scaffold_project.py": ("scaffold-project/scripts/scaffold_project.py", False, [
        (_SCAFFOLD_TYPES, _SCAFFOLD_TYPES_FROM_PACKAGE),
        (_SYNC_LABELS_FROM_PLUGIN, _SYNC_LABELS_FROM_PACKAGE),
        # The dropped comment records the original's own #434 history; in h2t_ops/ it
        # would be a new C:/dev hit for tests/dev/test_no_author_paths_ship.py.
        ('''_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
# There was a `_DEV_ROOT = Path(os.environ.get("H2T_DEV_ROOT", "C:/dev"))` here, defined and
# never read — the sibling-plugin lookup below uses _H2T_DEV_ROOT, which is derived rather
# than configured. Removed in the #434 sweep: a hardcoded path nothing uses still answers grep,
# and it sized part of that issue against code that could not run.
''', "_PLUGIN_ROOT = _SCAFFOLD_SCRIPT.parents[3]\n"),
    ]),
}


def expected_copy(original: str, rewrite_imports: bool, edits) -> str:
    for old, new in edits:
        assert original.count(old) == 1, (
            f"an enumerated edit no longer matches the original exactly once "
            f"({original.count(old)} matches): {old.splitlines()[0]!r}")
        original = original.replace(old, new)
    if rewrite_imports:
        pattern, repl = IMPORT_PREFIX
        original = pattern.sub(repl, original)
    return original


def first_difference(expected: str, actual: str) -> str:
    exp, act = expected.splitlines(), actual.splitlines()
    for number, (e, a) in enumerate(zip(exp, act), 1):
        if e != a:
            return f"line {number}: expected {e!r}, copy has {a!r}"
    return f"length differs: expected {len(exp)} lines, copy has {len(act)}"


@pytest.mark.parametrize("copy", sorted(PAIRS))
def test_copy_matches_original_up_to_enumerated_edits(copy):
    original_rel, rewrite_imports, edits = PAIRS[copy]
    original_path = SKILLS / original_rel
    expected = expected_copy(original_path.read_text(encoding="utf-8"), rewrite_imports, edits)
    actual = (LIFECYCLE / copy).read_text(encoding="utf-8")
    assert actual == expected, (
        f"h2t_ops/lifecycle/{copy} drifted from plugins/h2t-core/skills/{original_rel} "
        f"beyond the edits enumerated in this test — {first_difference(expected, actual)}. "
        "Apply the change to both copies. Task 12 deletes the originals together with this test."
    )


def test_every_lifecycle_script_copy_is_paired():
    """A new copy added to h2t_ops/lifecycle/ must be paired here, or it escapes the check."""
    copies = {p.name for p in LIFECYCLE.glob("*.py") if p.name != "__init__.py"}
    assert copies == set(PAIRS)


def test_first_difference_names_the_line():
    """Control for the message: it must point at the line, not just say 'differs'."""
    assert first_difference("a\nb\n", "a\nc\n") == "line 2: expected 'b', copy has 'c'"
