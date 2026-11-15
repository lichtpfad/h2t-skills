"""The release gates of #583: green CI on the tagged commit, an empty-HOME install.

Each gate is shown failing on a broken input before it is trusted to pass.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ci = _load("release_ci_gate")
home = _load("release_empty_home")


# --- green CI on the tagged commit ----------------------------------------------------------

def _runs(**over):
    """One finished green run per required check, then the overrides as (status, conclusion)."""
    runs = [{"id": i, "name": n, "status": "completed", "conclusion": "success"}
            for i, n in enumerate(ci.REQUIRED, start=1)]
    for i, (name, (status, conclusion)) in enumerate(over.items(), start=100):
        runs.append({"id": i, "name": name, "status": status, "conclusion": conclusion})
    return runs


def test_all_required_green_is_green():
    assert ci.verdict(_runs()) == ("green", [])


def test_a_failed_required_check_is_red():
    state, reasons = ci.verdict(_runs(**{"lib/ unit tests (windows-latest)": ("completed", "failure")}))
    assert state == "red" and reasons == ["lib/ unit tests (windows-latest): failure"]


@pytest.mark.parametrize("conclusion", ["skipped", "cancelled", "neutral", "timed_out"])
def test_anything_but_success_is_red(conclusion):
    assert ci.verdict(_runs(**{"checks / ruff": ("completed", conclusion)}))[0] == "red"


def test_a_running_or_missing_check_is_pending():
    runs = [r for r in _runs() if r["name"] != "checks / gitleaks"]
    assert ci.verdict(runs) == ("pending", ["checks / gitleaks: no run yet"])
    assert ci.verdict(_runs(**{"checks / ruff": ("in_progress", None)}))[0] == "pending"


def test_the_latest_attempt_of_a_check_wins():
    runs = _runs()
    runs.insert(0, {"id": 0, "name": "checks / ruff", "status": "completed", "conclusion": "failure"})
    assert ci.verdict(runs) == ("green", [])


def test_checks_outside_the_list_do_not_count():
    """The release jobs are check runs on the same commit; waiting on them would wait forever."""
    assert ci.verdict(_runs(build=("in_progress", None), other=("completed", "failure")))[0] == "green"


def test_the_gate_reads_what_ci_names_its_checks():
    """REQUIRED must match job names CI actually produces, or the gate waits on a name nobody emits."""
    evals = (ROOT / ".github/workflows/evals.yml").read_text(encoding="utf-8")
    assert "name: lib/ unit tests (${{ matrix.os }})" in evals
    assert "os: [ubuntu-latest, windows-latest]" in evals
    checks = (ROOT / ".github/workflows/checks.yml").read_text(encoding="utf-8")
    assert "jobs:\n  checks:" in checks


def test_main_red_and_timeout_exit_1(monkeypatch):
    monkeypatch.setattr(ci, "fetch", lambda repo, sha: _runs(**{"checks / ruff": ("completed", "failure")}))
    assert ci.main(["abc", "--repo", "o/r"]) == 1
    monkeypatch.setattr(ci, "fetch", lambda repo, sha: _runs(**{"checks / ruff": ("queued", None)}))
    assert ci.main(["abc", "--repo", "o/r", "--timeout", "0"]) == 1
    monkeypatch.setattr(ci, "fetch", lambda repo, sha: _runs())
    assert ci.main(["abc", "--repo", "o/r"]) == 0


# --- an install into an empty HOME ----------------------------------------------------------

GOOD = {"--version": (0, "h2t-ops 4.1.0\n", ""),
        "setup doctor": (0, "h2t setup doctor\n- uv: missing\n", ""),
        "version --json": (3, json.dumps({"ok": False, "error": {"type": "config", "hint": "install"}}), "")}


def test_good_results_pass():
    assert home.check(GOOD) == []


def test_a_traceback_anywhere_fails():
    bad = {**GOOD, "setup doctor": (1, "", "Traceback (most recent call last):\n  File ...")}
    assert home.check(bad) == ["setup doctor: traceback"]


def test_a_missing_install_without_exit_3_and_hint_fails():
    no_hint = {**GOOD, "version --json": (3, json.dumps({"ok": False, "error": {"hint": ""}}), "")}
    wrong_code = {**GOOD, "version --json": (1, GOOD["version --json"][1], "")}
    assert len(home.check(no_hint)) == 1 and len(home.check(wrong_code)) == 1


def test_an_undocumented_doctor_exit_fails():
    assert home.check({**GOOD, "setup doctor": (139, "", "")}) == [
        "setup doctor: exit 139 is not a documented code"]


@pytest.mark.skipif(sys.platform == "win32", reason="the fake CLI is a POSIX script")
def test_main_fails_on_a_cli_that_crashes(tmp_path):
    fake = tmp_path / "h2t-ops"
    fake.write_text(f"#!{sys.executable}\nraise RuntimeError('boom')\n", encoding="utf-8")
    fake.chmod(0o755)
    assert home.main([str(fake)]) == 1


def test_main_passes_on_the_real_cli():
    """Positive control: the h2t-ops of this environment, run with nothing configured."""
    cli = Path(sys.executable).parent / ("h2t-ops.exe" if os.name == "nt" else "h2t-ops")
    if not cli.is_file():
        pytest.skip(f"no h2t-ops next to {sys.executable}")
    assert home.main([str(cli)]) == 0


def test_main_takes_a_relative_path(monkeypatch):
    """The commands run with the empty HOME as cwd; a relative CLI path must still resolve."""
    cli = Path(sys.executable).parent / ("h2t-ops.exe" if os.name == "nt" else "h2t-ops")
    if not cli.is_file():
        pytest.skip(f"no h2t-ops next to {sys.executable}")
    monkeypatch.chdir(cli.parent.parent)
    assert home.main([os.path.join(cli.parent.name, cli.name)]) == 0
