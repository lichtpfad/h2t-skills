"""The whole suite runs under its own HOME (#548 R5): conftest._isolate_home_writes moves it
before every test, so a test that forgets its own isolation still never reaches the real
~/.dor/secrets.env, ~/.h2t or ~/.config/google-calendar-mcp."""
import sys
from pathlib import Path

from h2t_ops.core import secrets


def _root_conftest():
    mod = sys.modules["conftest"]
    assert Path(mod.__file__).resolve() == Path(__file__).resolve().parents[2] / "conftest.py"
    return mod


def test_home_is_not_the_real_one():
    assert Path.home() != _root_conftest().REAL_HOME


def test_every_legacy_secrets_source_lies_under_the_test_home():
    home = Path.home()
    sources = secrets.legacy_sources()
    assert sources
    assert all(home in p.parents for _, p in sources), sources


def test_the_harness_place_is_under_the_test_home():
    """CLAUDE_CONFIG_DIR from the developer's shell must not point the suite at ~/.claude."""
    from h2t_ops.core import paths
    assert Path.home() in paths.dir_of("harness").parents


def test_the_real_home_tripwire_sees_a_same_second_same_size_rewrite(tmp_path):
    """Positive control for conftest's tripwire, on a temporary tree, never the real home."""
    import os
    snapshot = _root_conftest()._real_home_artifacts
    layout = tmp_path / ".h2t" / "layout.json"
    record = tmp_path / ".h2t" / "records" / "sessions" / "a.json"
    record.parent.mkdir(parents=True)
    for f in (layout, record):
        f.write_text("aaaa")
        os.utime(f, ns=(1_700_000_000_000_000_100, 1_700_000_000_000_000_100))
    before = snapshot(tmp_path)
    assert str(layout) in before and str(record.parents[1]) in before
    for f in (layout, record):          # same size, same second, other nanoseconds
        f.write_text("bbbb")
        os.utime(f, ns=(1_700_000_000_000_000_200, 1_700_000_000_000_000_200))
    after = snapshot(tmp_path)
    assert after[str(layout)] != before[str(layout)]
    assert after[str(record.parents[1])] != before[str(record.parents[1])]
    (record.parent / "b.json").write_text("")
    assert snapshot(tmp_path)[str(record.parents[1])] != after[str(record.parents[1])]


def test_the_real_home_tripwire_watches_every_area_but_the_live_logs(tmp_path):
    """Task 12 wrote into ~/.h2t/research, which the tripwire did not watch. Every entry of
    ~/.h2t (logs/, run/ and venv/ aside: live hooks write there), ~/.dor and the 3.x ~/.config
    dirs are watched now — on a temporary tree, never the real home."""
    snapshot = _root_conftest()._real_home_artifacts
    areas = [tmp_path / ".h2t" / "research", tmp_path / ".h2t" / "creative" / "profiles",
             tmp_path / ".h2t" / "evals", tmp_path / ".h2t" / "config",
             tmp_path / ".dor" / "lake", tmp_path / ".config" / "telegram",
             tmp_path / ".h2t" / "logs", tmp_path / ".h2t" / "run",
             tmp_path / ".h2t" / "venv" / "__pycache__"]   # the hooks' interpreter
    for d in areas:
        d.mkdir(parents=True)
    import time
    since = time.time_ns()
    before = snapshot(tmp_path)
    for d in areas:
        (d / "x.json").write_text("{}")
    after = snapshot(tmp_path)
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    assert changed == {str(tmp_path / ".h2t" / "research"), str(tmp_path / ".h2t" / "creative"),
                       str(tmp_path / ".h2t" / "evals"), str(tmp_path / ".h2t" / "config"),
                       str(tmp_path / ".dor" / "lake"), str(tmp_path / ".config" / "telegram")}
    # a red names the files, not only the area tuple
    files = _root_conftest()._changed_files(str(tmp_path / ".h2t" / "research"), since)
    assert files == [str(tmp_path / ".h2t" / "research" / "x.json")]
