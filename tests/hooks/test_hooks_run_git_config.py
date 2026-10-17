"""Repository settings the wrapper depends on, checked through git itself.

- `*.env` is ignored for secrets; each plugin's `release.env` must still be committable.
- Git for Windows defaults to `autocrlf=true`; a bash script checked out with CRLF does
  not run, so the wrapper and the bash handlers are pinned to LF.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")

PLUGINS = sorted(p.name for p in (ROOT / "plugins").iterdir() if (p / ".claude-plugin").is_dir())


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)


@pytest.mark.parametrize("plugin", PLUGINS)
def test_release_env_is_not_ignored(plugin):
    result = _git("check-ignore", "--no-index", f"plugins/{plugin}/release.env")
    assert result.returncode == 1, f"ignored: {result.stdout.strip()}"


def test_the_ignore_control_still_ignores_a_secret_env():
    """Control: the negation must not have reopened *.env everywhere."""
    assert _git("check-ignore", "--no-index", "plugins/h2t-core/secrets.env").returncode == 0


def _bash_handlers():
    handlers = ROOT / "plugins" / "h2t-core" / "hooks-handlers"
    return sorted(f"plugins/h2t-core/hooks-handlers/{p.name}" for p in handlers.iterdir()
                  if p.is_file() and not p.suffix
                  and p.read_text(encoding="utf-8", errors="replace").startswith("#!/usr/bin/env bash"))


@pytest.mark.parametrize("path", ["plugins/h2t-core/hooks/run", *_bash_handlers()])
def test_bash_scripts_check_out_with_lf(path):
    result = _git("check-attr", "eol", "--", path)
    assert result.stdout.strip() == f"{path}: eol: lf", result.stdout


def test_the_handler_list_is_not_empty():
    assert len(_bash_handlers()) >= 10
