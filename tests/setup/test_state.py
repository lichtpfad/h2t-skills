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


def test_interrupt_between_json_and_env_reads_as_absent(home, monkeypatch):
    state.commit(_install())
    state.begin_update("4.1.0")
    real = state._write_env
    monkeypatch.setattr(state, "_write_env", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        state.commit(_install(version="4.1.0", generation="g2"))
    monkeypatch.setattr(state, "_write_env", real)
    assert state.read() is None
