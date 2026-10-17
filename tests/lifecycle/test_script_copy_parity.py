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
_ANCHOR_IMPORT = ("from pathlib import Path\n",
                  "from pathlib import Path\n\nfrom h2t_ops.lifecycle import plugin_script_anchor\n")

# copy -> (original, rewrite imports?, [(old, new), ...])
PAIRS = {
    "session_start.py": ("session-start/scripts/gather.py", True, [(_GATHER_BOOTSTRAP, "")]),
    "handoff.py": ("handoff/scripts/writer.py", True, [(_WRITER_BOOTSTRAP, "")]),
    "apply_registration.py": ("init-project/scripts/apply_registration.py", False, []),
    "project_audit_report.py": ("project-audit/scripts/report.py", False, []),
    "project_audit_scan.py": ("project-audit/scripts/scan.py", False, [
        _ANCHOR_IMPORT,
        ("    _self = Path(__file__).resolve()\n",
         '    _self = plugin_script_anchor("skills/project-audit/scripts/scan.py",\n'
         "                                 Path(__file__).resolve())\n"),
    ]),
    "scaffold_project.py": ("scaffold-project/scripts/scaffold_project.py", False, [
        _ANCHOR_IMPORT,
        ("_SCAFFOLD_SCRIPT = Path(__file__).resolve()\n",
         "_SCAFFOLD_SCRIPT = plugin_script_anchor(\n"
         '    "skills/scaffold-project/scripts/scaffold_project.py", Path(__file__).resolve())\n'),
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
