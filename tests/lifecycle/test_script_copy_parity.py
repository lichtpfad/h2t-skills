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
_SCAFFOLD_TYPES_FROM_PACKAGE = '''from h2t_ops.tools.docs.project_types import PROJECT_TYPES, SCAFFOLD_TYPE_TO_TEMPLATE

# The project types and docs-init ship in the package (h2t_ops.tools.docs): no h2t-dev
# plugin tree to find them in.
_PROJECT_TYPES_AVAILABLE = True
'''
# The h2t-dev lookup and the script path go with docs-init moving into the package (Task
# 12); a span, because the copy keeps none of it. The rest of run_docs_init is compared.
_DOCS_INIT_SPAN = ("_PLUGIN_ROOT = Path(__file__).resolve().parents[3]\n",
                   "            str(init_script),\n", '''def run_docs_init(repo_name: str, project_dir: Path, *, template: str = "code_repo") -> dict:
    """Scaffold docs/ in a new project through docs-init, which ships in this package.

    The plugin original skipped when h2t-dev was not installed and failed when it was
    installed without the script (#458). Neither absence exists here: the module is part of
    the package, so the call always runs, and a failure is reported as an error.
    """
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "h2t_ops.tools.docs.docs_init",
''')
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
    # The project types, the label sync (Task 10) and docs-init (Task 12) come from the
    # package. The dropped span also holds the original's #434 comment; in h2t_ops/ it
    # would be a new C:/dev hit for tests/dev/test_no_author_paths_ship.py.
    "scaffold_project.py": ("scaffold-project/scripts/scaffold_project.py", False, [
        (_SCAFFOLD_TYPES, _SCAFFOLD_TYPES_FROM_PACKAGE),
        (_SYNC_LABELS_FROM_PLUGIN, _SYNC_LABELS_FROM_PACKAGE),
        _DOCS_INIT_SPAN,
    ]),
}

# Moved, not copied: the plugin original is gone, so there is nothing to compare against.
MOVED = {"detect_project.py"}
# Written for the package, with no plugin original (fix round 1 of Task 12b).
AUTHORED = {"rule_scan.py"}


def expected_copy(original: str, rewrite_imports: bool, edits) -> str:
    for edit in edits:
        if len(edit) == 3:  # (start, end, new): the span from start through end
            start, end, new = edit
            assert original.count(start) == 1, f"span start matches {original.count(start)} times"
            head, _, rest = original.partition(start)
            assert rest.count(end) >= 1, f"span end not found after {start.strip()!r}"
            original = head + new + rest.split(end, 1)[1]
            continue
        old, new = edit
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
    copies = {p.name for p in LIFECYCLE.glob("*.py") if p.name not in {"__init__.py", *MOVED, *AUTHORED}}
    assert copies == set(PAIRS)


def test_first_difference_names_the_line():
    """Control for the message: it must point at the line, not just say 'differs'."""
    assert first_difference("a\nb\n", "a\nc\n") == "line 2: expected 'b', copy has 'c'"
