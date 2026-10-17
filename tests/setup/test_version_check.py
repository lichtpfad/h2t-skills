import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import h2t_ops
from h2t_ops.setup import state, version_check


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


def _commit(tool_root, version=None):
    names = ["h2t-ops", "h2t-gather", "h2t-hook"]
    state.commit(state.Install(version=version or h2t_ops.__version__, generation="g",
                               tool_root=str(tool_root),
                               entrypoints={n: str(tool_root / "bin" / n) for n in names}))
    return names


def test_not_installed():
    r = version_check.check(h2t_ops.__version__, which=lambda n: None)
    assert (r["ok"], r["reason"]) == (False, "not_installed")
    assert "h2t-setup" in r["hint"] and "sync" in r["hint"]


def test_version_mismatch_hints_sync(tmp_path):
    _commit(tmp_path / "tools", version="0.0.1")
    r = version_check.check("9.9.9", which=lambda n: str(tmp_path / "tools/bin" / n))
    assert r["reason"] == "version" and "h2t-setup" in r["hint"] and "sync" in r["hint"]


def test_expect_matches_but_install_version_differs(tmp_path):
    _commit(tmp_path / "tools", version="0.0.1")
    r = version_check.check(h2t_ops.__version__, which=lambda n: str(tmp_path / "tools/bin" / n))
    assert r["reason"] == "version"


def test_entry_point_outside_tool_root_is_path(tmp_path):
    _commit(tmp_path / "tools")

    def which(n):
        return str(tmp_path / "other/bin" / n) if n == "h2t-gather" else str(tmp_path / "tools/bin" / n)
    r = version_check.check(h2t_ops.__version__, which=which)
    assert r["reason"] == "path"
    assert "uv tool update-shell" in r["hint"] and str(tmp_path / "tools" / "bin") in r["hint"]
    assert "перезапусти харнесс" in r["hint"]


def test_missing_entry_point_is_path(tmp_path):
    _commit(tmp_path / "tools")
    r = version_check.check(h2t_ops.__version__, which=lambda n: None)
    assert r["reason"] == "path"


def test_sibling_prefix_is_not_inside_tool_root(tmp_path):
    _commit(tmp_path / "tools")
    r = version_check.check(h2t_ops.__version__, which=lambda n: str(tmp_path / "tools2/bin" / n))
    assert r["reason"] == "path"


def test_all_match_is_ok(tmp_path):
    _commit(tmp_path / "tools")
    r = version_check.check(h2t_ops.__version__, which=lambda n: str(tmp_path / "tools/bin" / n))
    assert r == {"ok": True, "version": h2t_ops.__version__, "reason": None, "hint": None}


def _console_script():
    exe = Path(sys.executable).parent
    for d in (exe, exe / "Scripts"):
        for name in ("h2t-ops", "h2t-ops.exe"):
            if (d / name).is_file():
                return str(d / name)
    found = shutil.which("h2t-ops")
    if not found:
        pytest.skip("h2t-ops console script not found next to the interpreter or on PATH")
    return found


def _cli(tmp_path, *args):
    env = {"HOME": str(tmp_path), "USERPROFILE": str(tmp_path), "PATH": str(tmp_path)}
    for key in ("SYSTEMROOT", "SystemRoot"):
        if key in os.environ:
            env[key] = os.environ[key]
    return subprocess.run([_console_script(), *args], capture_output=True, text=True,
                          encoding="utf-8", env=env)


def test_cli_version_expect_json_exit_3(tmp_path):
    p = _cli(tmp_path, "version", "--expect", "0.0.0", "--json")
    assert p.returncode == 3, p.stderr
    out = json.loads(p.stdout)
    assert out["ok"] is False and out["result"]["reason"] == "not_installed"
    assert out["error"]["type"] == "config"
    assert out["error"]["message"]
    assert "h2t-setup" in out["error"]["hint"]
    assert out["error"]["hint"] == out["result"]["hint"]


def test_cli_dash_dash_version_still_works(tmp_path):
    p = _cli(tmp_path, "--version")
    assert p.returncode == 0 and h2t_ops.__version__ in p.stdout
