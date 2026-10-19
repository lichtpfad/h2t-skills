import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("exec_map", ROOT / "scripts" / "exec_map.py")
exec_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exec_map)

# Measured on the commit that adds this test; may only decrease (spec §2.2).
RUNTIME_PY_CEILING = 0  # 62 at Task 4; Task 12 moved the last of it into the package
# Shipped programs that are not Python and not allowlisted (exec_map.ALLOWLIST). Two at
# Task 12: the `root` helpers plugins/h2t-dev/bin/h2t-dev and plugins/h2t-arch/bin/h2t-arch,
# POSIX sh, which the skills call to find their own reference text.
EXECUTABLE_CEILING = 2
AUTHOR_LITERALS = ["beabac7bf4314952a9327759c638d89f", "Asia/Jerusalem",
                   "Projects/DOR|Projects/newsengine"]
AUTHOR_LITERAL_CEILING = 0  # 7 on 2026-10-17 over plugins/ and h2t_ops/, non-test files; Task 24 (#548 R45): user.yaml


def test_runtime_python_in_plugins_does_not_grow():
    found = exec_map.shipped_runtime_python(ROOT)
    assert len(found) <= RUNTIME_PY_CEILING, found[RUNTIME_PY_CEILING:]


def test_shipped_executables_do_not_grow():
    found = exec_map.shipped_executables(ROOT)
    assert len(found) <= EXECUTABLE_CEILING, found


def test_the_executable_probe_sees_the_bins_and_skips_the_allowlist():
    """Control: the two bins are found, and hooks/run, which carries the bit, is not."""
    found = exec_map.shipped_executables(ROOT)
    assert "plugins/h2t-dev/bin/h2t-dev" in found
    assert not any(p.endswith("/hooks/run") for p in found)


def test_author_literals_do_not_grow():
    hits = exec_map.literal_hits(ROOT, AUTHOR_LITERALS)
    assert len(hits) <= AUTHOR_LITERAL_CEILING, hits
