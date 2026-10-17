import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("exec_map", ROOT / "scripts" / "exec_map.py")
exec_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exec_map)

# Measured on the commit that adds this test; may only decrease (spec §2.2).
RUNTIME_PY_CEILING = 61  # 62 at Task 4; detect_project.py moved into the package (Task 12b)
AUTHOR_LITERALS = ["beabac7bf4314952a9327759c638d89f", "Asia/Jerusalem",
                   "Projects/DOR|Projects/newsengine"]
AUTHOR_LITERAL_CEILING = 7  # measured 2026-10-17 over plugins/ and h2t_ops/, non-test files


def test_runtime_python_in_plugins_does_not_grow():
    found = exec_map.shipped_runtime_python(ROOT)
    assert len(found) <= RUNTIME_PY_CEILING, found[RUNTIME_PY_CEILING:]


def test_author_literals_do_not_grow():
    hits = exec_map.literal_hits(ROOT, AUTHOR_LITERALS)
    assert len(hits) <= AUTHOR_LITERAL_CEILING, hits
