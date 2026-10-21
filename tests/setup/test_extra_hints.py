"""Install hints name h2t-setup, never a package index (final review I2).

`h2t-ops` is not on PyPI. A hint of the form `uv tool install 'h2t-ops[drawio]'` resolves the
name there, so whoever registers it gets code execution from the hint. An extra is added by
`h2t-setup sync --extra <name>`, which records it in install.json `user_options.extras` and
reinstalls with it; in a checkout, by `h2t-setup dev-sync --extra <name>`.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

import h2t_ops
from h2t_ops.core import errors
from h2t_ops.setup import _release, cli, harness_claude, hints, manifest, state, sync
from tests.setup.test_sync_converges import TARGET, Machine, V, _converged

ROOT = Path(__file__).resolve().parents[2]
BOOT = "uvx --isolated --from W h2t-setup"


@pytest.fixture
def released(monkeypatch):
    monkeypatch.setattr(hints, "checkout", lambda: None)
    monkeypatch.setattr(_release, "BOOTSTRAP_COMMAND", BOOT)


@pytest.fixture
def unreleased(monkeypatch):
    monkeypatch.setattr(hints, "checkout", lambda: None)
    monkeypatch.setattr(_release, "BOOTSTRAP_COMMAND", "")


@pytest.fixture
def in_checkout(monkeypatch, tmp_path):
    monkeypatch.setattr(hints, "checkout", lambda: tmp_path)
    monkeypatch.setattr(_release, "BOOTSTRAP_COMMAND", BOOT)


# --- the hint texts ------------------------------------------------------------------------

def test_extra_hint_in_a_release_is_its_bootstrap(released):
    assert hints.add_extra("drawio") == f"{BOOT} sync --extra drawio"


def test_extra_hint_without_a_bootstrap_is_the_installed_setup(unreleased):
    assert hints.add_extra("drawio") == "h2t-setup sync --extra drawio"


def test_extra_hint_in_a_checkout_is_dev_sync(in_checkout):
    assert hints.add_extra("drawio") == "h2t-setup dev-sync --extra drawio"


def test_repair_hints(released):
    assert hints.repair() == f"{BOOT} sync"


def test_repair_hint_in_a_checkout_is_dev_sync(in_checkout):
    assert hints.repair() == "h2t-setup dev-sync"


def test_the_checkout_probe_sees_this_checkout():
    """Control for the fixtures above: positive from this repository, negative from a wheel.

    The release workflow runs tests/setup against the installed wheel with the source
    package moved away, so there `import h2t_ops` is the wheel and the probe must say None.
    """
    from_checkout = Path(h2t_ops.__file__).resolve().is_relative_to(ROOT)
    assert hints.checkout() == (ROOT if from_checkout else None)


def test_drawio_generate_without_drawpyo_prints_the_setup_hint(released, monkeypatch, capsys):
    from h2t_ops.tools.drawio import cli as drawio_cli
    monkeypatch.setattr(drawio_cli.importlib.util, "find_spec", lambda name: None)
    assert drawio_cli.main(["generate", "graph.json", "out.drawio"]) == 3
    err = capsys.readouterr().err
    assert f"{BOOT} sync --extra drawio" in err
    assert "uv tool install" not in err


def test_broken_install_hint_names_setup_not_an_editable_install(released):
    hint = errors.broken_install_hint("requests")
    assert f"{BOOT} sync" in hint and "uv tool install --editable" not in hint


# --- --extra lands in user_options and in the uv argv --------------------------------------

def test_sync_extra_is_recorded_and_installed(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.run()
    assert m.install_json()["user_options"]["extras"] == []
    report = sync.run("sync", TARGET, ["--extra", "drawio"], uv=m.uv, execute=m.uv.run,
                      claude=harness_claude.Claude(exe="claude", run=m.claude),
                      confirm=m.confirm, which=lambda n: None, fetch=None)
    assert report.failed == [], report.failed
    assert len(m.uv.installs) == 2
    assert f"h2t-ops[drawio] @ {TARGET['wheel']}" in m.uv.installs[-1]
    assert m.install_json()["user_options"] == {"extras": ["drawio"], "with": []}
    _converged(m)
    # A later plain sync keeps it: the option is the user's, not the run's.
    m.run()
    assert m.install_json()["user_options"]["extras"] == ["drawio"]


def test_sync_extra_already_there_is_not_doubled(tmp_path, monkeypatch):
    m = Machine(tmp_path, monkeypatch)
    m.uv.write_env("0.2.1", extras=["drawio"])
    sync.run("sync", TARGET, ["--extra=drawio"], uv=m.uv, execute=m.uv.run,
             claude=harness_claude.Claude(exe="claude", run=m.claude),
             confirm=m.confirm, which=lambda n: None, fetch=None)
    assert m.install_json()["user_options"]["extras"] == ["drawio"]


def test_cli_passes_extra_through_the_relaunch_and_refuses_an_unknown_one(tmp_path, monkeypatch,
                                                                          capsys):
    Machine(tmp_path, monkeypatch)
    monkeypatch.setattr(manifest, "current", lambda: TARGET)
    monkeypatch.setattr(sync, "receipt_editable", lambda *a, **k: None)
    relaunched, ran = [], []
    monkeypatch.setattr(sync, "ensure_executor",
                        lambda target, mode, argv, **k: relaunched.append(list(argv)))
    monkeypatch.setattr(sync, "run",
                        lambda mode, target, argv: ran.append(list(argv)) or sync.Report())
    assert cli.main(["sync", "--extra", "drawio", "--json"]) == 0, capsys.readouterr().err
    assert relaunched == [["--extra", "drawio", "--json"]] == ran
    assert cli.main(["sync", "--extra", "no-such-extra", "--json"]) == 3
    err = json.loads(capsys.readouterr().err)["error"]
    assert err["details"]["reason"] == "unknown_extra" and "drawio" in err["hint"]


def test_dev_sync_extra_lands_in_the_editable_spec(tmp_path, monkeypatch):
    from tests.setup.test_update_devsync import DevUv
    m = Machine(tmp_path, monkeypatch)
    m.uv = DevUv(tmp_path)
    checkout = tmp_path / "work" / "h2t-skills"
    checkout.mkdir(parents=True)
    (checkout / "pyproject.toml").write_text(f'[project]\nname = "h2t-ops"\nversion = "{V}"\n')
    monkeypatch.chdir(checkout)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    report = sync.run("dev-sync", None, ["--extra", "drawio"], uv=m.uv, execute=m.uv.run,
                      claude=harness_claude.Claude(exe="claude", run=m.claude))
    assert report.failed == [], report.failed
    (install,) = m.uv.installs
    assert install[3] == f"{checkout}[drawio]"
    assert state.read().user_options["extras"] == ["drawio"]


# --- no hint anywhere names a package index -------------------------------------------------

SHIPPED = [p for d in ("plugins", "h2t_ops") for p in (ROOT / d).rglob("*")
           if p.is_file() and p.suffix in (".md", ".py", ".json", ".yaml", ".toml")]
# `h2t-ops` by name, with or without extras, and NOT followed by `@ <url>` (a direct reference
# to a release wheel is the supported form and resolves nothing on an index).
PYPI_FORM = re.compile(
    r"""(uv tool install|uvx|pip install)\s+(--\S+\s+)*['"]?h2t-ops(\[[^\]]*\])?['"]?"""
    r"""(?!\s*@)(?=[\s'")`]|$)""", re.M)


def test_the_scan_covers_the_shipped_trees():
    assert len(SHIPPED) > 100


def test_no_shipped_text_installs_h2t_ops_from_an_index():
    hits = [f"{p.relative_to(ROOT)}: {m.group(0)}" for p in SHIPPED
            for m in PYPI_FORM.finditer(p.read_text(encoding="utf-8", errors="replace"))]
    assert hits == []


def test_the_pypi_form_pattern_catches_the_old_hints():
    """Control: the two hints this test exists for, as they were."""
    assert PYPI_FORM.search("(uv tool install 'h2t-ops[drawio]')")
    assert PYPI_FORM.search("pip install h2t-ops")
    assert PYPI_FORM.search("uvx h2t-ops")
    # The direct reference to a wheel is not an index lookup.
    assert not PYPI_FORM.search('uv tool install --reinstall "h2t-ops[x] @ https://w/h.whl"')
    assert not PYPI_FORM.search('uvx --isolated --from "h2t-ops @ https://w/h.whl" h2t-setup')


def test_no_skill_tells_a_stranger_to_install_editable():
    """`uv tool install --editable .` makes an install `sync` then refuses; a skill names the
    version check or h2t-setup instead."""
    hits = [str(p.relative_to(ROOT)) for p in (ROOT / "plugins").rglob("SKILL.md")
            if "uv tool install --editable" in p.read_text(encoding="utf-8")]
    assert hits == []
