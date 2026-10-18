"""Ratchets for #548 §7.3: paths, writes and secret reads outside the three modules.

A ceiling equals the measured count. Going up is a regression; going down means you
removed a bypass — write the new number here so it cannot come back. Target: 0.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("storage_map", ROOT / "scripts" / "storage_map.py")
storage_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(storage_map)

CEILINGS = {  # measured 2026-10-18 on ab078f4f; lowered after Task 6, Task 8 (Google), Task 9
    # (Telegram), Task 10 (every connector and setup through core.secrets), Task 11 (lake, round 1),
    # Task 12 (downloads, research, evals, creative profiles)
    "home": 43, "legacy_roots": 4, "path_env": 7, "dotenv": 0,
    "secret_readers": 0, "writes": 121, "sqlite": 0,
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


def test_bom_and_crlf_do_not_turn_docstrings_into_bypasses(tmp_path):
    """A file saved on Windows: UTF-8 BOM and CRLF. A BOM breaks ast.parse, and with no
    docstring set every docstring line would count as a real bypass."""
    (tmp_path / "h2t_ops").mkdir()
    (tmp_path / "h2t_ops" / "w.py").write_bytes(
        b'\xef\xbb\xbf"""Reads ~/.dor/x via Path.home()."""\r\n'
        b'p = Path.home()\r\n')
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    assert storage_map.hits(tmp_path, "home") == ["h2t_ops/w.py:2"]
    assert storage_map.hits(tmp_path, "legacy_roots") == []


def test_check_round_trip_with_ceilings(tmp_path):
    """--check and CEILINGS are two halves of one contract (verification.md)."""
    script = str(ROOT / "scripts" / "storage_map.py")
    ok = subprocess.run([sys.executable, script, "--check"], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout
    (tmp_path / "h2t_ops").mkdir()
    (tmp_path / "h2t_ops" / "p.py").write_text("p = Path.home()\n" * (CEILINGS["home"] + 1))
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    bad = subprocess.run([sys.executable, script, "--check", "--root", str(tmp_path)],
                         capture_output=True, text=True)
    assert bad.returncode != 0
    assert f"ceiling home: {CEILINGS['home']} -> {CEILINGS['home'] + 1}" in bad.stdout
