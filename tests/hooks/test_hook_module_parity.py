"""The ported hook modules must not drift from the 3.x handlers they copy.

3.x hooks.json still runs plugins/h2t-core/hooks-handlers/*.py, and the behaviour tests in
tests/hooks/ load those originals; `h2t-hook` runs h2t_ops/hooks/*. A fix landed in one and
not the other would pass every test that loads the wrong one.

Compared by AST, per top-level name: every function and constant of the original must be
in the copy and identical, except the names enumerated in `PAIRS` as dropped (the stdin and
stdout plumbing the emitter replaced); the copy may add only the names enumerated as added.
Task 12 deletes the originals and this test.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ORIGINALS = ROOT / "plugins" / "h2t-core" / "hooks-handlers"
COPIES = ROOT / "h2t_ops" / "hooks"

# copy -> (dropped from the original, added in the copy)
PAIRS = {
    "structure_guard.py": ({"_load_payload", "main"}, {"handle"}),
    "grade_guard.py": ({"main"}, {"handle", "warning", "log", "LOG_PATH"}),
    "plain_guard.py": ({"main"}, {"handle"}),
    "plan_closer.py": ({"_load_payload", "main"}, {"handle"}),
    "new_repo_hint.py": ({"main"}, {"handle", "NOTICE"}),
    "reap_codex.py": ({"_load_payload", "main"}, {"handle", "summary"}),
}


def top_level(path: Path) -> dict[str, str]:
    """name -> ast.dump of each top-level def, class and assignment."""
    out = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = ast.dump(node)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = ast.dump(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out[node.target.id] = ast.dump(node.value) if node.value else ""
    return out


@pytest.mark.parametrize("copy", sorted(PAIRS))
def test_copy_keeps_every_function_of_the_original(copy):
    dropped, added = PAIRS[copy]
    original = top_level(ORIGINALS / copy)
    ported = top_level(COPIES / copy)
    assert dropped <= set(original), "an enumerated drop no longer exists in the original"
    assert set(ported) - set(original) == added
    for name in sorted(set(original) - dropped):
        assert name in ported, f"{copy}: {name} is in the original and not in the copy"
        assert ported[name] == original[name], (
            f"h2t_ops/hooks/{copy}: {name} differs from hooks-handlers/{copy}. "
            "Apply the change to both; Task 12 deletes the originals with this test.")


def test_every_ported_copy_is_paired():
    """A module named like a 3.x handler file must be paired here, or it escapes the check."""
    copies = {p.name for p in COPIES.glob("*.py") if (ORIGINALS / p.name).is_file()}
    assert copies == set(PAIRS)
