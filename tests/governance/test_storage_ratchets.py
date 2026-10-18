"""Ratchets for #548 §7.3: paths, writes and secret reads outside the three modules.

A ceiling equals the measured count. Going up is a regression; going down means you
removed a bypass — write the new number here so it cannot come back. Target: 0.
"""
import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("storage_map", ROOT / "scripts" / "storage_map.py")
storage_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(storage_map)

CEILINGS = {  # measured 2026-10-18 on ab078f4f
    "home": 74, "legacy_roots": 40, "path_env": 20, "dotenv": 3,
    "secret_readers": 17, "writes": 203, "sqlite": 1,
}


@pytest.mark.parametrize("name", sorted(storage_map.PATTERNS))
def test_ratchet_equals_measured(name):
    found = storage_map.hits(ROOT, name)
    assert len(found) == CEILINGS[name], (
        f"{name}: {len(found)} found, ceiling {CEILINGS[name]}. Up = a new bypass "
        f"(route it through core/paths, core/store or core/secrets); down = write the "
        f"new number into CEILINGS.\n" + "\n".join(found[:40]))


def test_scanner_sees_a_planted_bypass(tmp_path):
    """Control: the scanner must report a known-positive line (verification.md)."""
    (tmp_path / "h2t_ops").mkdir()
    (tmp_path / "h2t_ops" / "x.py").write_text(
        'p = Path.home() / ".dor"\nopen(p, "w")\nos.environ.get("H2T_DEV_ROOT")\n'
        'os.environ.get("H2T_LAKE_ROOT")\n')
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    # Not staged on purpose: an untracked module counts as well.
    assert storage_map.hits(tmp_path, "home") == ["h2t_ops/x.py:1"]
    assert storage_map.hits(tmp_path, "legacy_roots") == ["h2t_ops/x.py:1"]
    assert storage_map.hits(tmp_path, "writes") == ["h2t_ops/x.py:2"]   # open() at column 0
    assert storage_map.hits(tmp_path, "path_env") == ["h2t_ops/x.py:4"]  # not H2T_DEV_ROOT


def test_scanner_skips_docstrings_and_dotted_names_but_not_paths(tmp_path):
    """R21 both ways: what it stops counting, and that real spellings still count."""
    (tmp_path / "h2t_ops").mkdir()
    (tmp_path / "h2t_ops" / "y.py").write_text(
        '"""Reads ~/.dor/secrets.env and H2T_LAKE_ROOT, once."""\n'   # 1 docstring
        'def f():\n'
        '    """H2T_SECRETS_FILE is not read; ~/.config/telegram is a fallback."""\n'  # 3 docstring
        '    return legacy("secrets.dor"), legacy("lake.dor")\n'      # 4 dotted keys
        'A = home / ".dor" / "x"\n'                                   # 5 path
        'B = "~/.dor/vault"\n'                                        # 6 path
        'C = home / ".config" / "gmail"\n'                            # 7 path
        'D = "x/.config/y"\n')                                        # 8 path
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    assert storage_map.hits(tmp_path, "legacy_roots") == [f"h2t_ops/y.py:{n}" for n in (5, 6, 7, 8)]
    assert storage_map.hits(tmp_path, "path_env") == []
    assert storage_map.hits(tmp_path, "home") == ["h2t_ops/y.py:6"]


BASELINE = Path(__file__).with_name("writers_baseline.txt")


def test_no_new_module_writes_outside_store():
    """A count can stay equal while one module stops writing and another starts (R27)."""
    baseline = set(BASELINE.read_text(encoding="utf-8").split())
    assert set(storage_map.files(ROOT, "writes")) <= baseline
