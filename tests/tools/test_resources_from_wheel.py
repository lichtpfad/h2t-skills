"""The tools find their data from a wheel installed outside the repository (spec §5, §9.8).

A tool that reads `Path(__file__).parent / "base"` works from the checkout and from the
plugin cache, which are the only two places it was ever run. The wheel is the third, and
the only one a stranger without either gets. So the check is a wheel built from this tree,
installed into a directory that is neither the repository nor a plugin cache, run from a
foreign working directory with an empty HOME.

The install is `pip install --no-deps --target`: CI installs with pip and has no uv, and the
third-party dependencies are already importable from the interpreter running this suite.
The package itself must come from the target, not from the editable checkout — the first
test below proves that before any other one is believed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESOURCES = ROOT / "h2t_ops" / "resources"

COMMANDS = [
    "h2t-docs-lint",
    "h2t-docs-sync-labels",
    "h2t-milestone-closure",
    "h2t-drawio",
    "h2t-creative",
    "h2t-agent-profile",
]


def _run(cmd, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300, **kwargs)


@pytest.fixture(scope="module")
def installed(tmp_path_factory):
    base = tmp_path_factory.mktemp("wheel-install")
    wheel_dir = base / "wheel"
    built = _run([sys.executable, "-m", "pip", "wheel", ROOT, "--no-deps", "-w", wheel_dir])
    if built.returncode != 0:
        pytest.fail(f"wheel build failed:\n{built.stdout[-2000:]}\n{built.stderr[-2000:]}")
    wheel = next(wheel_dir.glob("h2t_ops-*.whl"))

    site = base / "site"
    done = _run([sys.executable, "-m", "pip", "install", "--no-deps", "--target", site, wheel])
    if done.returncode != 0:
        pytest.fail(f"wheel install failed:\n{done.stdout[-2000:]}\n{done.stderr[-2000:]}")

    home = base / "home"
    elsewhere = base / "elsewhere"
    home.mkdir()
    elsewhere.mkdir()
    env = {k: v for k, v in os.environ.items()
           if k not in {"H2T_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "H2T_DEV_ROOT",
                        "CLAUDE_CONFIG_DIR", "PYTHONHOME"}}
    env.update(HOME=str(home), USERPROFILE=str(home), APPDATA=str(home / "AppData"),
               PYTHONPATH=str(site), PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
    bindir = site / ("Scripts" if sys.platform == "win32" else "bin")
    return SimpleNamespace(wheel=wheel, site=site.resolve(), env=env, cwd=elsewhere,
                           bindir=bindir)


def _command(installed, name: str) -> Path:
    for candidate in (installed.bindir / name, installed.bindir / f"{name}.exe"):
        if candidate.is_file():
            return candidate
    pytest.fail(f"{name} is not among the installed console scripts: "
                f"{sorted(p.name for p in installed.bindir.iterdir())}")


def _python(installed, code: str) -> subprocess.CompletedProcess:
    return _run([sys.executable, "-c", code], cwd=installed.cwd, env=installed.env)


def test_the_package_is_imported_from_the_install_not_the_checkout(installed):
    """Control: without it every test below could be reading the editable checkout."""
    r = _python(installed, "import h2t_ops; print(h2t_ops.__file__)")
    assert r.returncode == 0, r.stderr
    assert Path(r.stdout.strip()).resolve().is_relative_to(installed.site), r.stdout


def test_the_wheel_carries_every_resource_file(installed):
    names = set(zipfile.ZipFile(installed.wheel).namelist())
    expected = {p.relative_to(ROOT).as_posix() for p in RESOURCES.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts}
    assert expected, "h2t_ops/resources/ is empty in the checkout"
    assert expected - names == set()


@pytest.mark.parametrize("name", COMMANDS)
def test_help_runs_from_a_foreign_cwd(installed, name):
    r = _run([_command(installed, name), "--help"], cwd=installed.cwd, env=installed.env)
    assert r.returncode == 0, f"{name} --help exited {r.returncode}:\n{r.stderr[-2000:]}"
    assert "Traceback" not in r.stderr


_RESOURCE_PROBE = """
import json
from h2t_ops.resources import known_secrets_path
from h2t_ops.tools.agent_profile import apply_agent_profile
from h2t_ops.tools.creative import assembler
from h2t_ops.tools.docs.common import standards_dir
from h2t_ops.tools.drawio import export, generate
print(json.dumps({
    "creative/base": str(assembler.BASE_DIR),
    "creative/profiles": str(assembler.PROFILES_DIR),
    "creative/shared": str(assembler.SHARED_DIR),
    "drawio/defaults (export)": str(export.DEFAULT_CONFIG),
    "drawio/defaults (generate)": str(generate.DEFAULT_CONFIG),
    "drawio/shapes": str(generate.DEFAULT_SHAPES),
    "docs/standards/labels.json": str(standards_dir() / "labels.json"),
    "agent_profile/catalog": str(apply_agent_profile._DEFAULT_CATALOG),
    "known_secrets": str(known_secrets_path()),
}))
"""


def test_each_tool_finds_its_resources_inside_the_install(installed):
    r = _python(installed, _RESOURCE_PROBE)
    assert r.returncode == 0, r.stderr[-3000:]
    paths = {k: Path(v) for k, v in json.loads(r.stdout).items()}
    missing = {k: str(v) for k, v in paths.items() if not v.exists()}
    assert not missing, missing
    outside = {k: str(v) for k, v in paths.items()
               if not v.resolve().is_relative_to(installed.site)}
    assert not outside, outside


def test_generate_does_not_need_drawpyo_to_import(installed):
    """`h2t-drawio --help` must work on a base install, where drawpyo is an extra."""
    r = _python(installed, "import sys\nimport h2t_ops.tools.drawio.cli\n"
                           "import h2t_ops.tools.drawio.generate\n"
                           "print('drawpyo' in sys.modules)")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "False"


def test_creative_root_names_the_installed_resources(installed):
    """The skills read `$(h2t-creative root)/profiles/` — the same contract as the plugin bin."""
    r = _run([_command(installed, "h2t-creative"), "root"], cwd=installed.cwd, env=installed.env)
    assert r.returncode == 0, r.stderr
    root = Path(r.stdout.strip())
    assert root.resolve() == installed.site / "h2t_ops" / "resources" / "creative"
    assert (root / "profiles" / "h2t-default" / "DESIGN.md").is_file()


def test_docs_lint_doctor_on_an_empty_repository(installed, tmp_path):
    repo = tmp_path / "empty-repo"
    repo.mkdir()
    assert _run(["git", "init", "-q", repo]).returncode == 0
    r = _run([_command(installed, "h2t-docs-lint"), "doctor", "--json"], cwd=repo,
             env=installed.env)
    # doctor exits 1 whenever it has findings, and an empty repository has eight.
    assert r.returncode in (0, 1), r.stderr[-2000:]
    assert "Traceback" not in r.stderr, r.stderr[-2000:]
    report = json.loads(r.stdout)
    assert report["schema"] == "h2t_lifecycle_report/v0.1"
    assert Path(report["repo_root"]).resolve() == repo.resolve()
