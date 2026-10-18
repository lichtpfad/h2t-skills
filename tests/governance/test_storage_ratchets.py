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
    # Task 12 (downloads, research, evals, creative profiles; round 1: the NTFS-stream branch),
    # Task 13 (session records and activity under records/); Task 14 (the index) held them
    # and opens its base only through store.connect_sqlite, so sqlite stays 0; Task 15 (the
    # ontology through the index, registration through store, H2T_CONFIG_ROOT not read),
    # Task 16 (the 3.x session roots through paths.legacy), Task 17 (writes into a repository
    # through store.repo, user-named paths with dest=True; 6 of the 36 are store.mkdir and
    # RepoWriter.mkdir calls the .mkdir( pattern counts), Task 18 (install state, snapshots,
    # hook logs, the gather lock, the deploy input, setup's paths; 2 of the 8 are store.mkdir);
    # Task 19 (paths and index commands) held them: the variable names `paths list` reports
    # are spelled in paths.source, the index lock is opened by store.locked; Task 21 (the
    # migration journal) adds one: its store.mkdir of run/rollback/<id> with mode 0700 (R36);
    # Task 24: zero. The scanner stopped counting calls on core.store and the RepoWriter it
    # returns (the 9 writes), and user-named paths go through paths.expand_user_dest (the 19)
    "home": 0, "legacy_roots": 0, "path_env": 0, "dotenv": 0,
    "secret_readers": 0, "writes": 0, "sqlite": 0,
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


def test_scanner_skips_calls_through_store_but_not_raw_writes(tmp_path):
    """A call on core.store, or on the RepoWriter store.repo() returns, is the door, not a
    bypass. A raw write still counts — beside a door call too, and on a name that is not
    core.store (research has a module of its own called store)."""
    (tmp_path / "h2t_ops").mkdir()
    (tmp_path / "h2t_ops" / "z.py").write_text(
        'from h2t_ops.core import paths, store\n'                 # 1
        'from h2t_ops.connectors.research import store as rs\n'   # 2
        'store.mkdir(d, place="run", mode=0o700)\n'               # 3 door
        'store.repo(r, "x").mkdir(p)\n'                           # 4 door
        'rw = store.repo(r, "x")\n'                               # 5
        'rw.mkdir(d)\n'                                           # 6 door
        'Path(d).mkdir(parents=True)\n'                           # 7 raw
        'p.write_text("x")\n'                                     # 8 raw
        'open(p, "w")\n'                                          # 9 raw
        'store.mkdir(d, place="run"); d.mkdir()\n'                # 10 raw beside a door
        'rs.mkdir(d)\n')                                          # 11 not core.store
    (tmp_path / "h2t_ops" / "zz.py").write_text(
        'from h2t_ops.connectors.research import store\n'
        'store.mkdir(d)\n')
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    assert storage_map.hits(tmp_path, "writes") == (
        [f"h2t_ops/z.py:{n}" for n in (7, 8, 9, 10, 11)] + ["h2t_ops/zz.py:2"])


def test_the_door_is_the_bound_name_in_its_scope_not_the_spelling(tmp_path):
    """A call is the door only on the name the core.store import binds, where nothing in the
    enclosing scope rebinds it, or on a name assigned from `<store>.repo(...)` in the same
    scope. Every other `store.` / `rw.` spelling is a raw write (codex review, Task 24)."""
    (tmp_path / "h2t_ops").mkdir()
    (tmp_path / "h2t_ops" / "s.py").write_text(
        'from h2t_ops.core import store\n'                         # 1
        'obj.store.mkdir(d)\n'                                     # 2 attribute named store
        'def a(store):\n'                                          # 3
        '    store.mkdir(d)\n'                                     # 4 parameter shadows
        'def b():\n'                                               # 5
        '    store = Path("x")\n'                                  # 6
        '    store.mkdir()\n'                                      # 7 local shadows
        'def c():\n'                                               # 8
        '    rw = store.repo(r, "x")\n'                            # 9
        '    rw.mkdir(d)\n'                                        # 10 door: same scope
        'def e(rw):\n'                                             # 11
        '    rw.mkdir(d)\n'                                        # 12 another scope's rw
        'def f():\n'                                               # 13
        '    rw = Path("x")\n'                                     # 14
        '    rw.mkdir()\n'                                         # 15 rw rebound to a Path
        'def g():\n'                                               # 16
        '    store.mkdir(d, place="run")\n'                        # 17 door: module import
        'def h():\n'                                               # 18
        '    from h2t_ops.core import store as s\n'               # 19
        '    s.replace(p, "x", place="state"); s.mkdir(d, place="run")\n'  # 20 door: local import
        'def i():\n'                                               # 21
        '    def inner():\n'                                       # 22
        '        store.mkdir(d, place="run")\n'                    # 23 door: inherited
        '    return inner\n'                                       # 24
        'def j(store):\n'                                          # 25
        '    def inner():\n'                                       # 26
        '        store.mkdir(d)\n'                                 # 27 enclosing param shadows
        '    return inner\n')                                      # 28
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    assert storage_map.hits(tmp_path, "writes") == [
        f"h2t_ops/s.py:{n}" for n in (2, 4, 7, 12, 15, 27)]


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
