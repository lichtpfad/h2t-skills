# tests/setup/test_state.py
import json

import pytest

from h2t_ops.setup import state


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def _install(**kw):
    base = dict(version="4.0.0", generation="g1", tool_root="C:\\uv\\tools\\h2t-ops",
                entrypoints={"h2t-hook": "C:\\Users\\Лидия Иванова\\.local\\bin\\h2t-hook.exe"},
                editable=None, user_options={"extras": [], "with": []},
                plugins=["h2t-core", "h2t-ops"])
    base.update(kw)
    return state.Install(**base)


def test_commit_then_read_round_trips():
    state.commit(_install())
    assert state.read().version == "4.0.0"


def test_env_written_last_with_forward_slashes_and_lf(home):
    state.commit(_install())
    raw = (home / ".h2t/run/install.env").read_bytes()
    assert b"\r" not in raw
    assert b"H2T_HOOK=C:/Users/\xd0\x9b" in raw  # Лидия, forward slashes
    assert raw.splitlines()[0] == b"STATE=ready"


def test_updating_state_reads_as_absent():
    state.commit(_install())
    state.begin_update("4.1.0")
    assert state.read() is None


def test_generation_mismatch_reads_as_absent(home):
    state.commit(_install())
    data = json.loads((home / ".h2t/run/install.json").read_text(encoding="utf-8"))
    data["generation"] = "other"
    (home / ".h2t/run/install.json").write_text(json.dumps(data), encoding="utf-8")
    assert state.read() is None


def test_read_hides_mixed_generations_after_interrupt(home, monkeypatch):
    """Guards read()'s two-guard rule, not the write order.

    Both guards must fail for this to go red; each covers the case alone.
    The write order itself is pinned by test_commit_writes_json_before_env.
    """
    state.commit(_install())
    state.begin_update("4.1.0")
    real = state._write_env
    monkeypatch.setattr(state, "_write_env", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        state.commit(_install(version="4.1.0", generation="g2"))
    monkeypatch.setattr(state, "_write_env", real)
    assert state.read() is None


def test_commit_writes_json_before_env(home, monkeypatch):
    state.commit(_install())  # committed g1: both files hold generation g1
    real = state._atomic_write
    writes = []

    def recording(path, data):
        writes.append(path.name)
        if path.name == "install.json":
            raise OSError("disk full")
        real(path, data)

    monkeypatch.setattr(state, "_atomic_write", recording)
    with pytest.raises(OSError):
        state.commit(_install(version="4.1.0", generation="g2"))
    assert writes == ["install.json"]
    env = (home / ".h2t/run/install.env").read_bytes().splitlines()
    assert env[:3] == [b"STATE=ready", b"VERSION=4.0.0", b"GENERATION=g1"]
    assert state.read().generation == "g1"


def test_failed_replace_leaves_no_temp_file(home, monkeypatch):
    def refuse(src, dst):
        raise OSError("replace refused")

    monkeypatch.setattr(state.os, "replace", refuse)
    with pytest.raises(OSError):
        state.commit(_install())
    assert list(state.run_dir().iterdir()) == []


def test_read_ignores_unknown_install_json_keys(home):
    state.commit(_install())
    path = home / ".h2t/run/install.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(state="ready", future="x")
    path.write_text(json.dumps(data), encoding="utf-8")
    assert state.read().version == "4.0.0"
